#include "Actions/ActionInitialization.hh"
#include "Biasing/BiasingManager.hh"
#include "Core/MacroPreflight.hh"
#include "Core/RandomCommandGuard.hh"
#include "Core/BackendCapabilities.hh"
#include "Core/Geant4DataLocator.hh"
#include "Core/SimulationManager.hh"
#include "Config/ConfigManager.hh"
#include "Geometry/GeometryManager.hh"
#include "Materials/MaterialManager.hh"
#include "Source/SourceManager.hh"
#include "Utils/StringUtils.hh"
#include "Detector/DetectorConstruction.hh"
#include "G4RunManager.hh"
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
#include <cstdio>
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

class SemanticCommandError : public std::runtime_error {
 public:
  explicit SemanticCommandError(const std::string& message, std::string kind = "random_command_validation")
      : std::runtime_error(message), kind_(std::move(kind)) {}
  const std::string& Kind() const { return kind_; }
 private:
  std::string kind_;
};

bool RestartsExecutedKernel(const std::string& commandName) {
  return commandName == "/run/initialize" || commandName == "/run/reinitializegeometry" ||
         commandName == "/run/physicsmodified" || commandName == "/run/geometrymodified";
}

const char* const kRunRestartError = "Kernel reinitialization after an executed run is unsupported: "
    "Geant4 MT initialization can reset master run IDs while workers continue; start a new process instead";

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
  AuditedCshSession(bool& stopAfterFailure, std::function<bool()> hasHandlerFailure,
                    std::function<bool(const std::string&)> beforeCommand,
                    std::function<void(const std::string&)> afterCommand)
      : G4UIterminal(new FailFastCshShell(stopAfterFailure)),
        stopAfterFailure_(stopAfterFailure), hasHandlerFailure_(std::move(hasHandlerFailure)),
        beforeCommand_(std::move(beforeCommand)), afterCommand_(std::move(afterCommand)) {}

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
  const std::string& SemanticFailureDiagnostic() const { return semanticFailure_; }
  const std::string& SemanticFailureKind() const { return semanticFailureKind_; }
  G4int FailedCommandStatus() const { return failedCommandStatus_; }

 private:
  // G4UIterminal's own override is private but virtual. Capture the actual
  // ApplyCommand result here: G4UImanager::GetLastReturnCode() remains zero
  // for rejected csh commands in the tested Geant4 11.3.2 installation.
  void ExecuteCommand(const G4String& command) override {
    if (command.length() < 2) return;
    auto* ui = G4UImanager::GetUIpointer();
    if (!ui) return;
    // Validate the same alias-expanded direct command that Geant4 executes.
    const G4String auditedCommand = StringUtils::NormalizeCommandSlashes(
        StringUtils::Trim(ui->SolveAlias(command)));

    bool handled = false;
    try {
      handled = beforeCommand_(command);
    } catch (const SemanticCommandError& error) {
      stopAfterFailure_ = true;
      failedCommand_ = command;
      semanticFailure_ = error.what();
      semanticFailureKind_ = error.Kind();
      G4cerr << error.what() << G4endl;
      return;
    } catch (const std::exception& error) {
      stopAfterFailure_ = true;
      failedCommand_ = command;
      failedCommandStatus_ = fIllegalApplicationState;
      illegalApplicationState_ = error.what();
      G4cerr << error.what() << G4endl;
      return;
    }
    const G4int result = handled ? fCommandSucceeded : ui->ApplyCommand(auditedCommand);
    // Finish the current command's diagnostics, then stop reading later input.
    // Messenger failures can occur even when ApplyCommand returns zero.
    if (result != fCommandSucceeded || hasHandlerFailure_()) stopAfterFailure_ = true;
    if (!stopAfterFailure_) afterCommand_(auditedCommand);
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
  std::function<bool(const std::string&)> beforeCommand_;
  std::function<void(const std::string&)> afterCommand_;
  std::string semanticFailure_;
  std::string semanticFailureKind_;
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
  bool checkGeant4Data = false;
  bool inspectMacro = false;
  bool inspectRun = false;
  std::string dumpEffectiveConfig;
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
      << "  --ui-session csh   Required with --ui for the audited command-line session.\n"
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
      << "  --check-geant4-data Print where each Geant4 dataset was found as JSON; exit 1 if a\n"
      << "                      required dataset is missing (set GEANT4_DATA_DIR or write the data\n"
      << "                      folder into geant4-data.txt next to the executable).\n\n"
      << "  --inspect-macro     Print recursive macro preflight as JSON; requires --macro; does not evaluate --config.\n\n"
      << "  --inspect-run       Configure and preflight inputs as JSON without initialization or execution.\n\n"
      << "  --dump-effective-config <path|->  Export configured Manager subset; preflight only, no execution.\n\n"
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
    } else if (arg == "--check-geant4-data") {
      options.checkGeant4Data = true;
    } else if (arg == "--inspect-macro") {
      options.inspectMacro = true;
    } else if (arg == "--inspect-run") {
      options.inspectRun = true;
    } else if (arg == "--dump-effective-config") {
      if (!options.dumpEffectiveConfig.empty()) throw std::runtime_error("Duplicate --dump-effective-config");
      options.dumpEffectiveConfig = RequireNonEmptyValue(i, argc, argv, arg);
      if (options.dumpEffectiveConfig != "-" && options.dumpEffectiveConfig.front() == '-')
        throw std::runtime_error("--dump-effective-config requires <path|->");
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
  if (!options.dumpEffectiveConfig.empty() && (options.inspectRun || options.inspectMacro ||
      options.capabilities || options.checkGeant4Data || options.help || options.interactive || options.dryRun)) {
    throw std::runtime_error("--dump-effective-config is mutually exclusive with inspection, help, capabilities, data checks, --ui and --dry-run");
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
    // An installed package points at an existing Geant4 data folder (roadmap D).
    const std::string dataNote = Geant4DataLocator::ApplyGeant4DataFile(argc > 0 ? argv[0] : nullptr);
    const CommandLineOptions options = ParseCommandLine(argc, argv);
    if (options.checkGeant4Data) {
      return Geant4DataLocator::WriteReport(std::cout, dataNote) ? EXIT_SUCCESS : EXIT_FAILURE;
    }
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

    if (options.inspectRun || !options.dumpEffectiveConfig.empty()) {
      try {
        std::ostringstream configurationLog;
        {
          ScopedCoutCapture capture(configurationLog);
          sim.Configure();
        }
        std::cerr << configurationLog.str();
        MacroPreflightResult plan;
        const auto& context = sim.GetContext();
        if ((!context.IsDryRun() || !options.dumpEffectiveConfig.empty()) && context.HasMacroFile()) {
          MacroPreflightLocks locks;
          locks.outputDir = cliOverrides.outputDir.has_value();
          locks.numThreads = cliOverrides.numThreads.has_value();
          locks.seed = cliOverrides.seed.has_value();
          locks.checkOverlaps = cliOverrides.checkOverlaps.has_value();
          plan = PreflightMacro(context.GetMacroFile(), locks);
        }
        if (options.dumpEffectiveConfig.empty()) {
          WriteRunPlan(sim, options, plan, std::cout);
        } else {
          const std::string json = sim.ExportEffectiveConfigJson() + '\n';
          if (options.dumpEffectiveConfig == "-") {
            std::cout << json;
            if (!std::cout) throw std::runtime_error("EffectiveConfig stdout write failed");
          } else {
            const std::filesystem::path destination(options.dumpEffectiveConfig);
#ifdef _WIN32
            std::FILE* output = _wfopen(destination.c_str(), L"wbx");
#else
            std::FILE* output = std::fopen(destination.c_str(), "wbx");
#endif
            if (!output) throw std::runtime_error("Cannot create new EffectiveConfig export (target must not exist): " + options.dumpEffectiveConfig);
            const bool written = std::fwrite(json.data(), 1, json.size(), output) == json.size();
            const bool closed = std::fclose(output) == 0;
            if (!written || !closed) throw std::runtime_error("EffectiveConfig export write failed: " + options.dumpEffectiveConfig);
          }
        }
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

    if (context.IsInteractive() && !context.IsDryRun() && options.uiSession != "csh") {
      throw std::runtime_error("Interactive execution requires --ui-session csh: use --ui --ui-session csh. "
                               "Native Qt/other sessions cannot enforce command validation and are unavailable; "
                               "the Python desktop GUI and batch macros remain available.");
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
        if (!sim.GetOutputManager()->GetRunSummary().GetRuns().empty() && RestartsExecutedKernel(commandName)) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error(kRunRestartError);
        }
        const bool physicsCommand = commandName.rfind("/aihl/physics/", 0) == 0 ||
            commandName.rfind("/aihl/biasing/", 0) == 0;
        const bool readOnlyPhysicsCommand = commandName == "/aihl/physics/print" ||
            commandName == "/aihl/physics/listavailablereferences" ||
            commandName == "/aihl/physics/listavailableemreferences" ||
            commandName == "/aihl/physics/dumpprocesses" ||
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
          if (!kernelInitialized) {
            runManager->Initialize();
            kernelInitialized = true;
          }
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
        bool restoredRandomState = false;
        try {
          sim.GetSourceManager()->BeforeNativeGPSCommand(command.text);
          RandomCommandGuard::Validate(command.text);
          restoredRandomState = RandomCommandGuard::ExecuteRestoreIfRequested(command.text);
        } catch (...) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
          macroStatus = "failed";
          throw;
        }
        const int status = restoredRandomState ? fCommandSucceeded : uiManager->ApplyCommand(command.text.c_str());
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
      if (options.uiSession != "csh" && sim.GetSourceManager()->HasPendingDeferredConfiguration()) {
        throw std::runtime_error("Interactive ion/confinement configuration before its first run requires --ui-session csh "
                                 "to track native GPS overrides; use csh or a batch macro in a fresh process");
      }
      sim.EnableInteractivePhysicsGuard();
      const auto physicsFailuresBefore = sim.GetInteractivePhysicsFailureCount();
      const auto appFailuresBefore = sim.GetAppCommandFailureCount();
      const auto materialFailuresBefore = sim.GetMaterialManager()->GetCommandFailureCount();
      const auto outputFailuresBefore = sim.GetOutputManager()->GetCommandFailureCount();
      // Rejected interactive biasing mutations used to be warnings only: the
      // command was ignored, the session continued and the process exited 0
      // while the user believed biasing was configured.
      const auto biasingRejectsBefore = sim.GetBiasingManager()->GetInteractiveRejectCount();
      RunSummary& summary = sim.GetOutputManager()->GetRunSummary();
      summary.Set("interactive_command_failure_kind", "none");
      summary.Set("interactive_command_failure_message", "not_applicable");
      std::string unrecognizedCommand;
      std::string invalidParameter;
      std::string parameterOutOfRange;
      std::string illegalApplicationState;
      std::string failedCommand;
      std::string randomSemanticFailure;
      std::string semanticFailureKind;
      G4int failedCommandStatus = fCommandSucceeded;
      if (options.uiSession == "csh") {
        bool stopAfterFailure = false;
        const auto hasHandlerFailure = [&]() {
          return sim.GetInteractivePhysicsFailureCount() != physicsFailuresBefore ||
                 sim.GetAppCommandFailureCount() != appFailuresBefore ||
                 sim.GetMaterialManager()->GetCommandFailureCount() != materialFailuresBefore ||
                 sim.GetOutputManager()->GetCommandFailureCount() != outputFailuresBefore ||
                 sim.GetBiasingManager()->GetInteractiveRejectCount() != biasingRejectsBefore ||
                 sim.GetOutputManager()->HasOutputFailure();
        };
        AuditedCshSession ui(stopAfterFailure, hasHandlerFailure, [&](const std::string& command) {
          sim.GetSourceManager()->BeforeNativeGPSCommand(command);
          try {
            const std::string resolved = StringUtils::NormalizeCommandSlashes(StringUtils::Trim(
                G4UImanager::GetUIpointer()->SolveAlias(command.c_str())));
            std::istringstream input(resolved);
            std::string token;
            input >> token;
            token = StringUtils::ToLower(token);
            if (!sim.GetOutputManager()->GetRunSummary().GetRuns().empty() && RestartsExecutedKernel(token))
              throw SemanticCommandError(kRunRestartError, "run_lifecycle");
            if (token == "/control/execute" || token == "/control/loop" ||
                token == "/control/foreach" || token == "/control/if" || token == "/control/doif" ||
                token == "/control/strif" || token == "/control/strdoif") {
              throw std::runtime_error("Nested/dynamic csh dispatch cannot audit random command semantics; "
                                       "use a preflighted --macro file or direct csh commands instead");
            }
            if (options.seed && token.rfind("/random/", 0) == 0) {
              throw std::runtime_error("Random command conflicts with explicit CLI seed lock");
            }
            RandomCommandGuard::Validate(resolved);
            return RandomCommandGuard::ExecuteRestoreIfRequested(resolved);
          } catch (const SemanticCommandError&) {
            throw;
          } catch (const std::exception& error) {
            throw SemanticCommandError(error.what());
          }
        }, [&](const std::string& command) {
          sim.ConfirmMacroCommandSuccess(sim.NoteMacroCommand(command));
        });
        ui.SessionStart();
        unrecognizedCommand = ui.UnrecognizedCommandDiagnostic();
        invalidParameter = ui.InvalidParameterDiagnostic();
        parameterOutOfRange = ui.ParameterOutOfRangeDiagnostic();
        illegalApplicationState = ui.IllegalApplicationStateDiagnostic();
        failedCommand = ui.FailedCommand();
        failedCommandStatus = ui.FailedCommandStatus();
        randomSemanticFailure = ui.SemanticFailureDiagnostic();
        semanticFailureKind = ui.SemanticFailureKind();
      } else {
        throw std::runtime_error("Interactive execution requires --ui-session csh; native unaudited sessions are unavailable.");
      }
      const bool materialFailed = sim.GetMaterialManager()->GetCommandFailureCount() != materialFailuresBefore;
      const bool outputFailed = sim.GetOutputManager()->GetCommandFailureCount() != outputFailuresBefore;
      const bool physicsFailed = sim.GetInteractivePhysicsFailureCount() != physicsFailuresBefore;
      const bool appFailed = sim.GetAppCommandFailureCount() != appFailuresBefore;
      const bool biasingFailed = sim.GetBiasingManager()->GetInteractiveRejectCount() != biasingRejectsBefore;
      const bool uiCommandFailed = failedCommandStatus != fCommandSucceeded;
      if (materialFailed || outputFailed || !unrecognizedCommand.empty() || !invalidParameter.empty() ||
          !parameterOutOfRange.empty() || !illegalApplicationState.empty() || physicsFailed ||
          biasingFailed || appFailed || uiCommandFailed || !randomSemanticFailure.empty()) {
        std::vector<std::string> kinds;
        if (physicsFailed) kinds.push_back("physics");
        if (appFailed) kinds.push_back("app");
        if (biasingFailed) kinds.push_back("biasing");
        if (materialFailed) kinds.push_back("material");
        if (outputFailed) kinds.push_back("output");
        if (!randomSemanticFailure.empty()) kinds.push_back(semanticFailureKind);
        if (!unrecognizedCommand.empty()) kinds.push_back("geant4_command_not_found");
        if (!invalidParameter.empty()) kinds.push_back("geant4_invalid_parameter");
        if (!parameterOutOfRange.empty()) kinds.push_back("geant4_parameter_out_of_range");
        if (!illegalApplicationState.empty()) kinds.push_back("geant4_illegal_application_state");
        // A refused command also reports a non-zero UI status; keep the specific
        // diagnostic as the reported kind instead of degrading it to "multiple".
        if (uiCommandFailed && kinds.empty()) kinds.push_back("geant4_command_status");
        std::string kind;
        if (kinds.size() == 1) {
          kind = kinds.front();
        } else if (kinds.size() == 2 && materialFailed && outputFailed) {
          // Historical summary value: material and output failures were
          // reported together before the other kinds existed.
          kind = "material_and_output";
        } else {
          kind = "multiple";
        }
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
        if (appFailed) appendDiagnostic(sim.GetLastAppCommandFailure());
        if (biasingFailed) appendDiagnostic(sim.GetBiasingManager()->GetLastInteractiveReject());
        if (materialFailed) appendDiagnostic(sim.GetMaterialManager()->GetLastCommandFailure());
        if (outputFailed) appendDiagnostic(sim.GetOutputManager()->GetLastCommandFailure());
        appendDiagnostic(unrecognizedCommand);
        appendDiagnostic(invalidParameter);
        appendDiagnostic(parameterOutOfRange);
        appendDiagnostic(illegalApplicationState);
        appendDiagnostic(randomSemanticFailure);
        if (!randomSemanticFailure.empty()) appendDiagnostic("Rejected command: " + failedCommand);
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
