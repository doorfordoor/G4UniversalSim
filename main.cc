#include "Actions/ActionInitialization.hh"
#include "Biasing/BiasingManager.hh"
#include "Core/MacroPreflight.hh"
#include "Core/BackendCapabilities.hh"
#include "Core/SimulationManager.hh"
#include "Config/ConfigManager.hh"
#include "Geometry/GeometryManager.hh"
#include "Materials/MaterialManager.hh"
#include "Utils/StringUtils.hh"
#include "Detector/DetectorConstruction.hh"
#include "G4RunManager.hh"
#include "G4UIExecutive.hh"
#include "G4UIterminal.hh"
#include "G4UIcsh.hh"
#include "G4UImanager.hh"
#include "G4ScoringManager.hh"
#include "G4UIcommand.hh"
#include "G4UIparameter.hh"
#include "G4UIcommandStatus.hh"
#include "G4VModularPhysicsList.hh"
#include "G4VisExecutive.hh"
#include "Output/OutputManager.hh"
#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
#endif

#include <cstdlib>
#include <cctype>
#include <exception>
#include <functional>
#include <filesystem>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <sstream>
#include <initializer_list>
#include <utility>
#include <vector>

#include "Randomize.hh"

namespace {

// G4UIterminal prints unrecognized commands but does not propagate their
// failure to the exit code of the enclosing interactive session.
class FailFastCshShell final : public G4UIcsh {
 public:
  explicit FailFastCshShell(bool& stopAfterFailure) : stopAfterFailure_(stopAfterFailure) {}

  G4String GetCommandLineString(const char* message = nullptr) override {
    if (stopAfterFailure_) return "exit";
    return G4UIcsh::GetCommandLineString(message);
  }

 private:
  bool& stopAfterFailure_;
};

class AuditedCshSession final : public G4UIterminal {
 public:
  AuditedCshSession(bool& stopAfterFailure, std::function<bool()> hasHandlerFailure)
      : G4UIterminal(new FailFastCshShell(stopAfterFailure)),
        stopAfterFailure_(stopAfterFailure), hasHandlerFailure_(std::move(hasHandlerFailure)) {}

  G4int ReceiveG4cerr(const G4String& message) override {
    RecordDiagnostic(message);
    return G4UIterminal::ReceiveG4cerr(message);
  }

  G4int ReceiveG4cout(const G4String& message) override {
    RecordDiagnostic(message);
    return G4UIterminal::ReceiveG4cout(message);
  }

  const std::string& UnrecognizedCommandDiagnostic() const { return unrecognizedCommand_; }
  const std::string& InvalidParameterDiagnostic() const { return invalidParameter_; }
  const std::string& ParameterOutOfRangeDiagnostic() const { return parameterOutOfRange_; }
  const std::string& IllegalApplicationStateDiagnostic() const { return illegalApplicationState_; }
  const std::string& FailedCommand() const { return failedCommand_; }
  G4int FailedCommandStatus() const { return failedCommandStatus_; }

 private:
  // G4UIterminal's own override is private but virtual. Capture the actual
  // ApplyCommand result here: G4UImanager::GetLastReturnCode() remains zero
  // for rejected csh commands in the tested Geant4 11.3.2 installation.
  void ExecuteCommand(const G4String& command) override {
    if (command.length() < 2) return;
    auto* ui = G4UImanager::GetUIpointer();
    if (!ui) return;

    const G4int result = ui->ApplyCommand(command);
    // Finish the current command's diagnostics, then stop reading later input.
    // Messenger failures can occur even when ApplyCommand returns zero.
    if (result != fCommandSucceeded || hasHandlerFailure_()) stopAfterFailure_ = true;
    const G4int parameterIndex = result % 100;
    const G4int status = result - parameterIndex;
    if (status != fCommandSucceeded && failedCommand_.empty()) {
      failedCommand_ = command;
      failedCommandStatus_ = result;
    }

    // Preserve the stock G4UIterminal diagnostics alongside the status audit.
    switch (status) {
      case fCommandSucceeded: break;
      case fCommandNotFound:
        G4cerr << "command <" << ui->SolveAlias(command) << "> not found" << G4endl;
        if (command.find("@@") != G4String::npos) G4cout << "@@G4UIterminal" << G4endl;
        break;
      case fIllegalApplicationState:
        G4cerr << "illegal application state -- command refused" << G4endl;
        break;
      case fParameterOutOfRange:
        break;
      case fParameterOutOfCandidates: {
        if (auto* cmd = FindCommand(command)) {
          G4cerr << "Parameter is out of candidate list (index " << parameterIndex << ")" << G4endl;
          if (parameterIndex < 99 && cmd->GetParameter(parameterIndex)) {
            G4cerr << "Candidates : " << cmd->GetParameter(parameterIndex)->GetParameterCandidates() << G4endl;
          }
        }
        break;
      }
      case fParameterUnreadable:
        G4cerr << "Parameter is wrong type and/or is not omittable (index "
               << parameterIndex << ")" << G4endl;
        break;
      default:
        G4cerr << "command refused (" << status << ")" << G4endl;
        break;
    }
  }

  void RecordDiagnostic(const G4String& message) {
    std::string normalized(message);
    for (char& ch : normalized) {
      ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    if ((normalized.find("command <") != std::string::npos &&
         normalized.find("> not found") != std::string::npos) ||
        normalized.find("command not found:") != std::string::npos) {
      if (unrecognizedCommand_.empty()) unrecognizedCommand_ = message;
    }
    // Keep human-readable native diagnostics in addition to the numeric
    // ApplyCommand result recorded by this session's ExecuteCommand override.
    if (normalized.find("parameter is wrong type and/or is not omittable") != std::string::npos) {
      if (invalidParameter_.empty()) invalidParameter_ = message;
    }
    if (normalized.find("parameter out of range:") != std::string::npos) {
      if (parameterOutOfRange_.empty()) parameterOutOfRange_ = message;
    }
    if (normalized.find("illegal application state -- command refused") != std::string::npos) {
      if (illegalApplicationState_.empty()) illegalApplicationState_ = message;
    }
  }

  bool& stopAfterFailure_;
  std::function<bool()> hasHandlerFailure_;
  std::string unrecognizedCommand_;
  std::string invalidParameter_;
  std::string parameterOutOfRange_;
  std::string illegalApplicationState_;
  std::string failedCommand_;
  G4int failedCommandStatus_ = 0;
};

struct MacroFailureInfo {
  std::string file;
  int line = 0;
  std::string command;
  int code = 0;
  bool codeAvailable = false;
};

struct CommandLineOptions {
  std::string configFile;
  std::string macroFile;
  std::string outputDir;
  std::string runName;
  bool interactive = false;
  std::string uiSession;
  bool dryRun = false;
  std::optional<bool> checkOverlaps;
  std::optional<int> threads;
  std::optional<unsigned long> seed;
  bool help = false;
  bool capabilities = false;
  bool inspectMacro = false;
  bool inspectRun = false;
};

void PrintUsage(const char* program) {
  std::cout
      << "G4UniversalSim - Universal Geant4 Simulation Framework\n\n"
      << "Usage:\n"
      << "  " << program << " macros/run_simple.mac\n"
      << "  " << program
      << " --config config/main.ini --macro macros/run_simple.mac\n"
      << "  " << program << " --config config/main.ini --ui\n"
      << "  " << program
      << " --macro macros/run_simple.mac --threads 4 --seed 12345\n\n"
      << "Options:\n"
      << "  --config, -c <file>  Load main ini configuration through "
         "SimulationManager.\n"
      << "  --macro, -m <file>   Execute a Geant4 macro after initialization "
         "setup.\n"
      << "  --output, -o <dir>   Override output directory.\n"
      << "  --run-name <name>    Override run name in SimulationManager.\n"
      << "  --ui                 Start an interactive Geant4 UI session.\n"
      << "  --ui-session csh   Use the Geant4 command-line UI with --ui.\n"
      << "  --threads, -t <N>    Set requested number of worker threads when "
         "MT "
         "is available.\n"
      << "  --seed <N>           Set random seed in SimulationManager and "
         "CLHEP.\n"
      << "  --check-overlaps <true|false>  Override geometry overlap checks.\n"
      << "  --dry-run            Configure and register Geant4 objects but "
         "skip macro/UI execution.\n"
      << "  --help, -h           Show this help.\n\n"
      << "  --capabilities      Print versioned backend capabilities as JSON; no simulation.\n\n"
      << "  --inspect-macro     Print recursive macro preflight as JSON; requires --macro; does not evaluate --config.\n\n"
      << "  --inspect-run       Configure and preflight inputs as JSON without initialization or execution.\n\n"
      << "If the final configuration has no macro/UI and is not dry-run, "
         "usage is shown.\n";
}

std::string RequireValue(int& index, int argc, char** argv,
                         const std::string& option) {
  if (index + 1 >= argc) {
    throw std::runtime_error("Missing value for command line option '" +
                             option + "'");
  }
  ++index;
  return argv[index];
}

std::string RequireNonEmptyValue(int& index, int argc, char** argv,
                                 const std::string& option) {
  const std::string value = RequireValue(index, argc, argv, option);
  if (value.empty()) {
    throw std::runtime_error("Empty value for command line option '" + option + "'");
  }
  return value;
}

int ParsePositiveInt(const std::string& value, const std::string& option) {
  std::size_t consumed = 0;
  const int parsed = std::stoi(value, &consumed);
  if (consumed != value.size() || parsed <= 0) {
    throw std::runtime_error("Invalid value for " + option + ": '" + value +
                             "'");
  }
  return parsed;
}

unsigned long ParseSeed(const std::string& value) {
  if (value.empty() || value[0] == '-') {
    throw std::runtime_error("Invalid value for --seed: '" + value + "'");
  }
  std::size_t consumed = 0;
  const unsigned long parsed = std::stoul(value, &consumed);
  if (consumed != value.size()) {
    throw std::runtime_error("Invalid value for --seed: '" + value + "'");
  }
  return parsed;
}

bool ParseBoolOption(const std::string& value, const std::string& option) {
  if (value == "true" || value == "1" || value == "on" || value == "yes")
    return true;
  if (value == "false" || value == "0" || value == "off" || value == "no")
    return false;
  throw std::runtime_error("Invalid value for " + option + ": '" + value + "'");
}

CommandLineOptions ParseCommandLine(int argc, char** argv) {
  CommandLineOptions options;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];

    if (arg == "--help" || arg == "-h") {
      options.help = true;
    } else if (arg == "--capabilities") {
      options.capabilities = true;
    } else if (arg == "--inspect-macro") {
      options.inspectMacro = true;
    } else if (arg == "--inspect-run") {
      options.inspectRun = true;
    } else if (arg == "--config" || arg == "-c") {
      options.configFile = RequireNonEmptyValue(i, argc, argv, arg);
    } else if (arg == "--macro" || arg == "-m") {
      options.macroFile = RequireNonEmptyValue(i, argc, argv, arg);
    } else if (arg == "--output" || arg == "-o") {
      options.outputDir = RequireNonEmptyValue(i, argc, argv, arg);
    } else if (arg == "--run-name") {
      options.runName = RequireNonEmptyValue(i, argc, argv, arg);
    } else if (arg == "--ui") {
      options.interactive = true;
    } else if (arg == "--ui-session") {
      options.uiSession = RequireNonEmptyValue(i, argc, argv, arg);
      if (options.uiSession != "csh") {
        throw std::runtime_error("Invalid --ui-session; supported value: csh");
      }
    } else if (arg == "--threads" || arg == "-t") {
      options.threads = ParsePositiveInt(RequireValue(i, argc, argv, arg), arg);
    } else if (arg == "--seed") {
      options.seed = ParseSeed(RequireValue(i, argc, argv, arg));
    } else if (arg == "--dry-run") {
      options.dryRun = true;
    } else if (arg == "--check-overlaps") {
      options.checkOverlaps =
          ParseBoolOption(RequireValue(i, argc, argv, arg), arg);
    } else if (!arg.empty() && arg[0] == '-') {
      throw std::runtime_error("Unknown command line option: '" + arg + "'");
    } else {
      if (!options.macroFile.empty()) {
        throw std::runtime_error(
            "Multiple positional macro files were provided: '" +
            options.macroFile + "' and '" + arg + "'");
      }
      options.macroFile = arg;
    }
  }
  if (!options.uiSession.empty() && !options.interactive) {
    throw std::runtime_error("--ui-session requires --ui");
  }
  return options;
}

std::string JsonEscape(const std::string& value) {
  std::string escaped;
  for (unsigned char ch : value) {
    switch (ch) {
      case '"': escaped += "\\\""; break;
      case '\\': escaped += "\\\\"; break;
      case '\n': escaped += "\\n"; break;
      case '\r': escaped += "\\r"; break;
      case '\t': escaped += "\\t"; break;
      default:
        if (ch < 0x20) {
          constexpr char hex[] = "0123456789abcdef";
          escaped += "\\u00";
          escaped += hex[ch >> 4];
          escaped += hex[ch & 0xf];
        } else {
          escaped += static_cast<char>(ch);
        }
    }
  }
  return escaped;
}

std::string MacroCommandName(const std::string& text) {
  const auto end = text.find_first_of(" \t\r\n");
  std::string name = text.substr(0, end);
  for (char& ch : name) ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
  return name;
}

std::string MacroCommandCategory(const std::string& command) {
  if (command == "/run/beamon") return "beam_on";
  if (command == "/aihl/app/setoutputdir" || command == "/aihl/output/setdir") return "output";
  if (command == "/aihl/app/setnumthreads" || command == "/run/numberofthreads"
      || command == "/run/setnumberofthreads") return "threads";
  if (command == "/aihl/app/setseed" || command.rfind("/random/", 0) == 0) return "seed";
  if (command == "/aihl/app/setmainconfig") return "configuration";
  if (command == "/aihl/app/setcheckoverlaps") return "geometry";
  if (command.rfind("/aihl/material/", 0) == 0) return "materials";
  if (command.rfind("/aihl/geometry/", 0) == 0) return "geometry";
  if (command.rfind("/aihl/physics/", 0) == 0) return "physics";
  if (command.rfind("/aihl/source/", 0) == 0) return "source";
  if (command.rfind("/gps/", 0) == 0 || command.rfind("/gun/", 0) == 0) return "source";
  if (command.rfind("/aihl/scoring/", 0) == 0) return "scoring";
  if (command.rfind("/aihl/bias", 0) == 0) return "biasing";
  if (command.rfind("/vis/", 0) == 0) return "visualization";
  return "other";
}

void WriteMacroPlan(const MacroPreflightResult& plan, std::ostream& out) {
  out << "{\"schema\":\"G4UniversalSimMacroPlan\",\"version\":1,"
      << "\"macro_file\":\"" << JsonEscape(plan.macroPath.u8string()) << "\","
      << "\"status\":\"preflight_passed\",\"configuration_evaluated\":false,"
      << "\"runtime_command_validation_required\":true,"
      << "\"commands\":[";
  bool first = true;
  for (const auto& command : plan.commands) {
    if (!first) out << ',';
    first = false;
    const auto name = MacroCommandName(command.text);
    out << "{\"file\":\"" << JsonEscape(command.sourceFile.u8string())
        << "\",\"line\":" << command.lineNumber
        << ",\"text\":\"" << JsonEscape(command.text)
        << "\",\"command\":\"" << JsonEscape(name)
        << "\",\"category\":\"" << MacroCommandCategory(name) << "\"}";
  }
  out << "]}\n";
}

class ScopedCoutCapture {
public:
  explicit ScopedCoutCapture(std::ostringstream& capture)
      : previous_(std::cout.rdbuf(capture.rdbuf())) {}
  ~ScopedCoutCapture() { std::cout.rdbuf(previous_); }
private:
  std::streambuf* previous_;
};

std::string NativeArgumentToUtf8(const std::string& value) {
#ifdef _WIN32
  return std::filesystem::path(value).u8string();
#else
  return value;
#endif
}

void WriteRunPlan(const SimulationManager& sim, const CommandLineOptions& options,
                  const MacroPreflightResult& macro, std::ostream& out) {
  const auto& context = sim.GetContext();
  const auto* config = sim.GetConfigManager();
  const auto fact = [&](const std::string& name, const std::string& value, bool cli,
                        std::initializer_list<std::pair<std::string, std::string>> keys,
                        bool requireNonEmpty = false) {
    out << "{\"name\":\"" << name << "\",\"value\":\"" << JsonEscape(value) << "\","
        << "\"source\":\"";
    if (cli) {
      out << "cli\"}";
      return;
    }
    if (context.GetMainConfig().empty()) {
      out << "default\"}";
      return;
    }
    for (const auto& key : keys) {
      if (!config->HasKey(key.first, key.second)) continue;
      if (requireNonEmpty && StringUtils::Trim(config->GetString(key.first, key.second)).empty()) continue;
      out << "main_ini\",\"file\":\"" << JsonEscape(NativeArgumentToUtf8(context.GetMainConfig()))
          << "\",\"section\":\"" << key.first << "\",\"key\":\"" << key.second << "\"";
      for (const auto& field : config->GetFields()) {
        if (StringUtils::ToLower(field.section) == StringUtils::ToLower(key.first)
            && StringUtils::ToLower(field.key) == StringUtils::ToLower(key.second)) {
          out << ",\"line\":" << field.lineNumber;
          break;
        }
      }
      out << '}';
      return;
    }
    out << "default\"}";
  };
  out << "{\"schema\":\"G4UniversalSimRunPlan\",\"version\":1,"
      << "\"configuration_evaluated\":true,\"execution_performed\":false,"
      << "\"configuration_phase\":\"before_macro\","
      << "\"working_directory\":\"" << JsonEscape(std::filesystem::current_path().u8string()) << "\","
      << "\"macro_execution_planned\":" << ((!context.IsDryRun() && context.HasMacroFile()) ? "true" : "false")
      << ",\"initial_configuration\":[";
  fact("main_config", NativeArgumentToUtf8(context.GetMainConfig()), !options.configFile.empty(), {}); out << ',';
  fact("macro_file", options.macroFile.empty() ? context.GetMacroFile() : NativeArgumentToUtf8(context.GetMacroFile()),
       !options.macroFile.empty(), {{"run", "macro"}}); out << ',';
  fact("output_dir", options.outputDir.empty() ? context.GetOutputDir() : NativeArgumentToUtf8(context.GetOutputDir()),
       !options.outputDir.empty(), {{"output", "dir"}, {"output", "outputDir"}}, true); out << ',';
  fact("threads", std::to_string(context.GetNumThreads()), options.threads.has_value(), {{"run", "threads"}}); out << ',';
  fact("seed", context.HasSeed() ? std::to_string(context.GetSeed()) : "unset", options.seed.has_value(),
       {{"run", "seed"}, {"run", "randomSeed"}, {"general", "seed"}, {"general", "randomSeed"}}); out << ',';
  fact("run_name", options.runName.empty() ? context.GetRunName() : NativeArgumentToUtf8(context.GetRunName()),
       !options.runName.empty(), {{"run", "name"}, {"run", "run_name"}, {"run", "runName"}}, true); out << ',';
  fact("dry_run", context.IsDryRun() ? "true" : "false", options.dryRun, {{"run", "dry_run"}, {"run", "dryRun"}}); out << ',';
  fact("interactive", context.IsInteractive() ? "true" : "false", options.interactive, {{"run", "interactive"}}); out << ',';
  fact("check_overlaps", context.GetCheckOverlaps() ? "true" : "false", options.checkOverlaps.has_value(),
       {{"geometry", "check_overlaps"}, {"geometry", "checkOverlaps"}, {"run", "check_overlaps"}, {"run", "checkOverlaps"}}); out << ',';
  fact("geometry_template", sim.GetGeometryManager()->GetTemplateName(), false,
       {{"geometry", "template"}, {"geometry", "templateName"}}, true); out << ',';
  fact("geometry_config", sim.GetGeometryManager()->GetGeometryConfigFile(), false,
       {{"geometry", "config"}, {"geometry", "configFile"}}, true); out << ',';
  fact("materials_file", sim.GetMaterialsConfigFile(), false,
       {{"materials", "file"}, {"materials", "materialFile"}, {"materials", "config"}, {"materials", "configFile"}}, true);
  out << "],\"main_ini_fields\":[";
  bool first = true;
  const auto fields = context.GetMainConfig().empty() ? std::vector<IniFieldInfo>{} : config->GetFields();
  for (const auto& field : fields) {
    if (!first) out << ',';
    first = false;
    out << "{\"section\":\"" << JsonEscape(field.originalSection)
        << "\",\"key\":\"" << JsonEscape(field.originalKey)
        << "\",\"value\":\"" << JsonEscape(field.value) << "\",\"line\":" << field.lineNumber
        << ",\"consumed\":" << (field.consumed ? "true" : "false") << '}';
  }
  out << "],\"macro_plan\":";
  WriteMacroPlan(macro, out);
  out << "}\n";
}

std::unique_ptr<G4RunManager> CreateRunManager(const SimulationManager& sim) {
#ifdef G4MULTITHREADED
  auto runManager = std::make_unique<G4MTRunManager>();
  runManager->SetNumberOfThreads(sim.GetContext().GetNumThreads());
  return runManager;
#else
  (void)sim;
  return std::make_unique<G4RunManager>();
#endif
}

}  // namespace

int main(int argc, char** argv) {
  SimulationManager sim;
  std::optional<MacroFailureInfo> macroFailure;
  std::string macroStatus = "not_run";
  bool finalizationStarted = false;
  try {
    const CommandLineOptions options = ParseCommandLine(argc, argv);
    if (options.help) {
      PrintUsage(argv[0]);
      return EXIT_SUCCESS;
    }
    if (options.capabilities) {
      WriteBackendCapabilities(std::cout);
      return EXIT_SUCCESS;
    }
    if (options.inspectMacro) {
      if (options.macroFile.empty()) {
        throw std::runtime_error("--inspect-macro requires --macro <file>.");
      }
      if (!options.configFile.empty()) {
        throw std::runtime_error("--inspect-macro does not evaluate --config; inspect the macro separately from configuration.");
      }
      MacroPreflightLocks locks;
      locks.outputDir = !options.outputDir.empty();
      locks.numThreads = options.threads.has_value();
      locks.seed = options.seed.has_value();
      locks.checkOverlaps = options.checkOverlaps.has_value();
      const auto plan = PreflightMacro(options.macroFile, locks);
      WriteMacroPlan(plan, std::cout);
      return EXIT_SUCCESS;
    }

    SimulationCommandLineOverrides cliOverrides;
    if (!options.configFile.empty()) cliOverrides.mainConfig = options.configFile;
    if (!options.macroFile.empty()) cliOverrides.macroFile = options.macroFile;
    if (!options.outputDir.empty()) cliOverrides.outputDir = options.outputDir;
    if (!options.runName.empty()) cliOverrides.runName = options.runName;
    if (options.interactive) cliOverrides.interactive = true;
    if (options.dryRun) cliOverrides.dryRun = true;
    cliOverrides.checkOverlaps = options.checkOverlaps;
    cliOverrides.numThreads = options.threads;
    cliOverrides.seed = options.seed;
    sim.SetCommandLineOverrides(cliOverrides);

    if (options.inspectRun) {
      try {
        std::ostringstream configurationLog;
        {
          ScopedCoutCapture capture(configurationLog);
          sim.Configure();
        }
        std::cerr << configurationLog.str();
        MacroPreflightResult plan;
        const auto& context = sim.GetContext();
        if (!context.IsDryRun() && context.HasMacroFile()) {
          MacroPreflightLocks locks;
          locks.outputDir = cliOverrides.outputDir.has_value();
          locks.numThreads = cliOverrides.numThreads.has_value();
          locks.seed = cliOverrides.seed.has_value();
          locks.checkOverlaps = cliOverrides.checkOverlaps.has_value();
          plan = PreflightMacro(context.GetMacroFile(), locks);
        }
        WriteRunPlan(sim, options, plan, std::cout);
        return EXIT_SUCCESS;
      } catch (const std::exception& error) {
        std::cerr << "G4UniversalSim run inspection failed: " << error.what() << '\n';
        return EXIT_FAILURE;
      }
    }

    sim.Configure();
    sim.BeginRuntimeTracking();
    const SimulationContext& context = sim.GetContext();
    if (!context.IsDryRun() && !context.IsInteractive() && !context.HasMacroFile()) {
      PrintUsage(argv[0]);
      return EXIT_SUCCESS;
    }

    MacroPreflightResult preflight;
    if (!context.IsDryRun() && context.HasMacroFile()) {
      sim.SetExecutedMacroPath(context.GetMacroFile());
      MacroPreflightLocks locks;
      locks.outputDir = cliOverrides.outputDir.has_value();
      locks.numThreads = cliOverrides.numThreads.has_value();
      locks.seed = cliOverrides.seed.has_value();
      locks.checkOverlaps = cliOverrides.checkOverlaps.has_value();
      preflight = PreflightMacro(context.GetMacroFile(), locks);
      sim.SetExecutedMacroPath(preflight.macroPath.string());
    }

    if (context.IsInteractive() && !context.IsDryRun()) {
      sim.GetBiasingManager()->SetInteractiveSessionMode(true);
      for (const auto& command : preflight.commands) {
        const std::string name = MacroCommandName(command.text);
        const bool biasingMutation = name.rfind("/aihl/biasing/", 0) == 0 &&
            name != "/aihl/biasing/print" &&
            name != "/aihl/biasing/validate" &&
            name != "/aihl/biasing/xs/printrules";
        if (biasingMutation) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
          macroStatus = "preflight_failed";
          throw std::runtime_error("Interactive XS biasing macro mutation is not supported because geometry reinitialization can invalidate attached operators; run this macro in batch mode in a fresh process: " + command.text);
        }
      }
    }

    sim.Initialize();
    if (sim.GetContext().HasSeed()) {
      CLHEP::HepRandom::setTheSeed(
          static_cast<long>(sim.GetContext().GetSeed()));
    }

    auto runManager = CreateRunManager(sim);
    // Enable Geant4 command-based scoring (/score/...). Must exist on the
    // master before /run/initialize; meshes are merged across threads.
    G4ScoringManager::GetScoringManager();

    auto detector = sim.CreateDetectorConstruction();
    detector->SetSensitiveDetectorFactory(sim.CreateSensitiveDetectorFactory());
    detector->SetGeometryPostBuildCallback(
        sim.CreateGeometryPostBuildCallback());
    runManager->SetUserInitialization(detector.release());

    auto physics = sim.CreatePhysicsList();
    runManager->SetUserInitialization(physics.release());

    sim.InitializeSourceAfterPhysicsListRegistered();

    auto actions = sim.CreateActionInitialization();
    runManager->SetUserInitialization(actions.release());

    // [scoring.mesh.*] INI sections -> /score/ commands. Applied after the
    // physics list is registered (particle filters need the particle table)
    // and before any user macro, so macros may add further meshes.
    for (const std::string& command : sim.GetScoringMeshCommands()) {
      const G4int status = G4UImanager::GetUIpointer()->ApplyCommand(command);
      if (status != 0) {
        throw std::runtime_error("[scoring.mesh.*] generated command failed (Geant4 status " +
                                 std::to_string(status) + "): " + command +
                                 "; check the scorer type, unit and particle names");
      }
    }

    std::unique_ptr<G4VisManager> visManager;
    if (sim.GetContext().IsInteractive() && !sim.GetContext().IsDryRun()) {
      visManager = std::make_unique<G4VisExecutive>();
      visManager->Initialize();
    }

    G4UImanager* uiManager = G4UImanager::GetUIpointer();
    if (!uiManager) {
      throw std::runtime_error("G4UImanager::GetUIpointer returned null");
    }

    if (sim.GetContext().IsDryRun()) {
      std::cout << "G4UniversalSim dry-run completed: managers and Geant4 user "
                   "initialization objects were created; macro/UI execution "
                   "skipped.\n";
      finalizationStarted = true;
      try {
        if (!sim.FinalizeRunSummary("dry_run", EXIT_SUCCESS, "skipped_dry_run")) {
          std::cerr << "G4UniversalSim output finalization failed; see run_summary.txt\n";
          return EXIT_FAILURE;
        }
      } catch (const std::exception& summaryError) {
        std::cerr << "G4UniversalSim summary failure: "
                  << summaryError.what() << std::endl;
        throw;
      }
      return EXIT_SUCCESS;
    }

    bool physicsListDirty = false;
    if (!sim.GetContext().GetMacroFile().empty()) {
      macroStatus = "running";
      bool kernelInitialized = false;
      for (const auto& command : preflight.commands) {
        const std::string commandName = MacroCommandName(command.text);
        const bool physicsCommand = commandName.rfind("/aihl/physics/", 0) == 0 ||
            commandName.rfind("/aihl/biasing/", 0) == 0;
        const bool readOnlyPhysicsCommand = commandName == "/aihl/physics/print" ||
            commandName == "/aihl/physics/listavailablereferences" ||
            commandName == "/aihl/physics/listavailableemreferences" ||
            commandName == "/aihl/biasing/print" ||
            commandName == "/aihl/biasing/validate" ||
            commandName == "/aihl/biasing/xs/printrules";
        const bool changesPhysics = physicsCommand && !readOnlyPhysicsCommand;
        const bool materialCommand = commandName.rfind("/aihl/material/", 0) == 0;
        const bool readOnlyMaterialCommand = commandName == "/aihl/material/print" ||
            commandName == "/aihl/material/list";
        if (materialCommand && !readOnlyMaterialCommand && kernelInitialized) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error("Material macro command after kernel initialization is not supported; move it before /run/initialize or /run/beamOn, or start a new process: " + command.text);
        }
        if (changesPhysics && kernelInitialized) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error("Physics/biasing macro command after kernel initialization is not supported; move it before /run/initialize or /run/beamOn: " + command.text);
        }
        if (commandName == "/run/reinitializegeometry" && kernelInitialized &&
            sim.GetBiasingManager() && sim.GetBiasingManager()->IsEnabled()) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error("/run/reinitializeGeometry with attached biasing operators is not safe in this lifecycle; start a fresh process with the new geometry instead.");
        }
        if (commandName == "/run/initialize" || commandName == "/run/beamon") {
          if (physicsListDirty) {
            runManager->SetUserInitialization(sim.CreatePhysicsList().release());
            sim.InitializeSourceAfterPhysicsListRegistered();
            physicsListDirty = false;
          }
        }
        if (commandName == "/run/beamon" && sim.GetBiasingManager() && sim.GetBiasingManager()->IsEnabled()) {
          runManager->Initialize();
          kernelInitialized = true;
          try {
            sim.ValidateBiasingProcessTargets();
          } catch (...) {
            macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
            macroStatus = "failed";
            throw;
          }
        }
        if (commandName == "/run/beamon") {
          if (!kernelInitialized) {
            macroFailure = MacroFailureInfo{
                command.sourceFile.string(), static_cast<int>(command.lineNumber),
                command.text, 0, false};
            macroStatus = "failed";
            throw std::runtime_error(
                "/run/beamOn requires an initialized Geant4 kernel in batch mode; "
                "add /run/initialize before /run/beamOn. Without initialization "
                "Geant4 may silently ignore BeamOn without processing events.");
          }
          try {
            const int nextRunId = static_cast<int>(sim.GetOutputManager()->GetRunSummary().GetRuns().size());
            sim.GetOutputManager()->ValidateOutputTargetDirectories(
                nextRunId, sim.GetContext().GetNumThreads());
          } catch (...) {
            macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
            macroStatus = "failed";
            throw;
          }
        }
        const auto materialFailuresBefore = sim.GetMaterialManager()->GetCommandFailureCount();
        const auto outputFailuresBefore = sim.GetOutputManager()->GetCommandFailureCount();
        const bool seedStateChanged = sim.NoteMacroCommand(command.text);
        const int status = uiManager->ApplyCommand(command.text.c_str());
        if (status != 0) {
          macroFailure = MacroFailureInfo{
              command.sourceFile.string(),
              static_cast<int>(command.lineNumber),
              command.text,
              status,
              true};
          macroStatus = "failed";
          throw std::runtime_error(
              "Failed to execute macro command '" + command.text + "' at " +
              command.sourceFile.string() + ":" +
              std::to_string(command.lineNumber) +
              ", G4UImanager status=" + std::to_string(status));
        }
        if (materialCommand &&
            sim.GetMaterialManager()->GetCommandFailureCount() != materialFailuresBefore) {
          macroFailure = MacroFailureInfo{
              command.sourceFile.string(), static_cast<int>(command.lineNumber),
              command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error(sim.GetMaterialManager()->GetLastCommandFailure());
        }
        if (commandName.rfind("/aihl/output/", 0) == 0 &&
            sim.GetOutputManager()->GetCommandFailureCount() != outputFailuresBefore) {
          macroFailure = MacroFailureInfo{
              command.sourceFile.string(), static_cast<int>(command.lineNumber),
              command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error(sim.GetOutputManager()->GetLastCommandFailure());
        }
        if (commandName == "/run/beamon" && sim.GetOutputManager()->HasOutputFailure()) {
          const auto failure = sim.GetOutputManager()->GetOutputFailure();
          macroFailure = MacroFailureInfo{
              command.sourceFile.string(), static_cast<int>(command.lineNumber),
              command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error("Worker output failure (run " +
              std::to_string(failure.runId) + ", thread " +
              std::to_string(failure.threadId) + ", " + failure.stage +
              "): " + failure.message);
        }
        if (commandName == "/run/initialize") {
          kernelInitialized = true;
          try {
            sim.ValidateBiasingProcessTargets();
          } catch (...) {
            macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
            macroStatus = "failed";
            throw;
          }
        }
        if (changesPhysics) physicsListDirty = true;
        sim.ConfirmMacroCommandSuccess(seedStateChanged);
        sim.RecordSuccessfulMacroCommand(command.text, command.sourceFile.string(),
                                         static_cast<int>(command.lineNumber));
      }
      macroStatus = "completed";
    }

    if (sim.GetContext().IsInteractive()) {
      // A batch macro may end after mutating physics but before initializing
      // the kernel. Rebind now: the interactive /run/initialize command is
      // dispatched inside Geant4 and cannot go through the batch rebind path.
      if (physicsListDirty) {
        runManager->SetUserInitialization(sim.CreatePhysicsList().release());
        sim.InitializeSourceAfterPhysicsListRegistered();
        physicsListDirty = false;
        std::cout << "[PhysicsLifecycle] Rebound physics list from batch macro before interactive UI.\n";
      }
      // Interactive PhysicsMessenger mutations are rejected after registration.
      sim.EnableInteractivePhysicsGuard();
      const auto physicsFailuresBefore = sim.GetInteractivePhysicsFailureCount();
      const auto materialFailuresBefore = sim.GetMaterialManager()->GetCommandFailureCount();
      const auto outputFailuresBefore = sim.GetOutputManager()->GetCommandFailureCount();
      RunSummary& summary = sim.GetOutputManager()->GetRunSummary();
      summary.Set("interactive_command_failure_kind", "none");
      summary.Set("interactive_command_failure_message", "not_applicable");
      std::string unrecognizedCommand;
      std::string invalidParameter;
      std::string parameterOutOfRange;
      std::string illegalApplicationState;
      std::string failedCommand;
      G4int failedCommandStatus = fCommandSucceeded;
      if (options.uiSession == "csh") {
        bool stopAfterFailure = false;
        const auto hasHandlerFailure = [&]() {
          return sim.GetInteractivePhysicsFailureCount() != physicsFailuresBefore ||
                 sim.GetMaterialManager()->GetCommandFailureCount() != materialFailuresBefore ||
                 sim.GetOutputManager()->GetCommandFailureCount() != outputFailuresBefore ||
                 sim.GetOutputManager()->HasOutputFailure();
        };
        AuditedCshSession ui(stopAfterFailure, hasHandlerFailure);
        ui.SessionStart();
        unrecognizedCommand = ui.UnrecognizedCommandDiagnostic();
        invalidParameter = ui.InvalidParameterDiagnostic();
        parameterOutOfRange = ui.ParameterOutOfRangeDiagnostic();
        illegalApplicationState = ui.IllegalApplicationStateDiagnostic();
        failedCommand = ui.FailedCommand();
        failedCommandStatus = ui.FailedCommandStatus();
      } else {
        G4UIExecutive ui(argc, argv);
        ui.SessionStart();
      }
      const bool materialFailed = sim.GetMaterialManager()->GetCommandFailureCount() != materialFailuresBefore;
      const bool outputFailed = sim.GetOutputManager()->GetCommandFailureCount() != outputFailuresBefore;
      const bool physicsFailed = sim.GetInteractivePhysicsFailureCount() != physicsFailuresBefore;
      const bool uiCommandFailed = failedCommandStatus != fCommandSucceeded;
      if (materialFailed || outputFailed || !unrecognizedCommand.empty() || !invalidParameter.empty() ||
          !parameterOutOfRange.empty() || !illegalApplicationState.empty() || physicsFailed || uiCommandFailed) {
        const bool otherFailed = materialFailed || outputFailed || !unrecognizedCommand.empty() ||
                                 !invalidParameter.empty() || !parameterOutOfRange.empty() ||
                                 !illegalApplicationState.empty() || uiCommandFailed;
        const std::string kind = physicsFailed ? (otherFailed ? "multiple" : "physics") :
            (materialFailed && outputFailed ? "material_and_output" :
            (materialFailed ? "material" : (outputFailed ? "output" :
            (!unrecognizedCommand.empty() ? "geant4_command_not_found" :
             (!invalidParameter.empty() ? "geant4_invalid_parameter" :
             (!parameterOutOfRange.empty() ? "geant4_parameter_out_of_range" :
             (!illegalApplicationState.empty() ? "geant4_illegal_application_state" :
              "geant4_command_status")))))));
        std::vector<std::string> messages;
        const auto appendDiagnostic = [&](const std::string& diagnostic) {
          if (diagnostic.empty()) return;
          // Native G4cerr diagnostics often end with a newline; the summary
          // is key=value line-oriented and must keep the complete message on
          // a single line for downstream parsers.
          std::string singleLine;
          singleLine.reserve(diagnostic.size());
          for (char ch : diagnostic) {
            if (ch == '\r' || ch == '\n' || ch == '\t') {
              if (!singleLine.empty() && singleLine.back() != ' ') singleLine.push_back(' ');
            } else {
              singleLine.push_back(ch);
            }
          }
          while (!singleLine.empty() && singleLine.back() == ' ') singleLine.pop_back();
          if (!singleLine.empty()) messages.push_back(std::move(singleLine));
        };
        if (physicsFailed) appendDiagnostic(sim.GetLastInteractivePhysicsFailure());
        if (materialFailed) appendDiagnostic(sim.GetMaterialManager()->GetLastCommandFailure());
        if (outputFailed) appendDiagnostic(sim.GetOutputManager()->GetLastCommandFailure());
        appendDiagnostic(unrecognizedCommand);
        appendDiagnostic(invalidParameter);
        appendDiagnostic(parameterOutOfRange);
        appendDiagnostic(illegalApplicationState);
        if (uiCommandFailed) {
          appendDiagnostic("Geant4 UI status=" + std::to_string(failedCommandStatus) +
                           " for command: " + failedCommand);
        }
        const std::string message = StringUtils::Join(messages, "; ");
        summary.Set("interactive_command_failure_kind", kind);
        summary.Set("interactive_command_failure_message", message);
        throw std::runtime_error("Interactive command failure: " + message);
      }
    }
    if (sim.GetOutputManager()->HasOutputFailure()) {
      const auto failure = sim.GetOutputManager()->GetOutputFailure();
      throw std::runtime_error("Interactive output failure (run " +
          std::to_string(failure.runId) + ", thread " +
          std::to_string(failure.threadId) + ", " + failure.stage +
          "): " + failure.message);
    }

    const auto& runs = sim.GetOutputManager()->GetRunSummary().GetRuns();
    const std::string status = sim.GetContext().IsInteractive() && runs.empty()
        ? "interactive_no_run"
        : "completed";
    finalizationStarted = true;
    try {
      if (!sim.FinalizeRunSummary(status, EXIT_SUCCESS, macroStatus)) {
        std::cerr << "G4UniversalSim output finalization failed; see run_summary.txt\n";
        return EXIT_FAILURE;
      }
    } catch (const std::exception& summaryError) {
      std::cerr << "G4UniversalSim summary failure: "
                << summaryError.what() << std::endl;
      throw;
    }
    return EXIT_SUCCESS;
  } catch (const MacroPreflightError& ex) {
    macroStatus = "preflight_failed";
    macroFailure = MacroFailureInfo{
        ex.File().string(),
        static_cast<int>(ex.Line()),
        ex.Command(),
        0};
    if (sim.IsConfigured() && !finalizationStarted) {
      try {
        finalizationStarted = true;
        sim.FinalizeRunSummary(
            "failed",
            EXIT_FAILURE,
            macroStatus,
            macroFailure->file,
            macroFailure->line,
            macroFailure->command,
            macroFailure->code);
      } catch (const std::exception& summaryError) {
        std::cerr << "G4UniversalSim summary failure: "
                  << summaryError.what() << std::endl;
      }
    }
    std::cerr << "G4UniversalSim macro preflight failed: "
              << ex.what() << std::endl;
    return EXIT_FAILURE;
  } catch (const std::exception& ex) {
    if (sim.IsConfigured() && !finalizationStarted) {
      try {
        finalizationStarted = true;
        sim.FinalizeRunSummary(
            "failed",
            EXIT_FAILURE,
            macroStatus == "not_run" && !sim.GetContext().IsInteractive() ? "failed" : macroStatus,
            macroFailure ? macroFailure->file : "",
            macroFailure ? macroFailure->line : 0,
            macroFailure ? macroFailure->command : "",
            macroFailure ? macroFailure->code : 0,
            macroFailure ? macroFailure->codeAvailable : false);
      } catch (const std::exception& summaryError) {
        std::cerr << "G4UniversalSim summary failure: "
                  << summaryError.what() << std::endl;
      }
    }
    std::cerr << "G4UniversalSim fatal error: " << ex.what() << std::endl;
    return EXIT_FAILURE;
  } catch (...) {
    if (sim.IsConfigured() && !finalizationStarted) {
      try {
        finalizationStarted = true;
        sim.FinalizeRunSummary("failed", EXIT_FAILURE, macroStatus);
      } catch (const std::exception& summaryError) {
        std::cerr << "G4UniversalSim summary failure: "
                  << summaryError.what() << std::endl;
      }
    }
    std::cerr << "G4UniversalSim fatal error: unknown exception" << std::endl;
    return EXIT_FAILURE;
  }
}
