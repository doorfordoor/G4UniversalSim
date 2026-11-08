#include "Core/RunFinalization.hh"
#include "Actions/ActionInitialization.hh"
#include "Actions/RunManagerFactory.hh"
#include "Biasing/BiasingManager.hh"
#include "Core/MacroPreflight.hh"
#include "Core/RandomCommandGuard.hh"
#include "Core/BackendCapabilities.hh"
#include "Core/Geant4DataLocator.hh"
#include "Core/SessionServer.hh"
#include "Core/RuntimeExecution.hh"
#include "Core/RuntimeSession.hh"
#include "Core/SimulationManager.hh"
#include "Config/ConfigManager.hh"
#include "Geometry/GeometryManager.hh"
#include "Materials/MaterialManager.hh"
#include "Source/SourceManager.hh"
#include "Scoring/ScoringMeshConfig.hh"
#include "Utils/StringUtils.hh"
#include "Detector/DetectorConstruction.hh"
#include "G4RunManager.hh"
#include "G4StateManager.hh"
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
#include <system_error>
#include <string>
#include <sstream>
#include <initializer_list>
#include <utility>
#include <vector>

#include "Randomize.hh"

using runtime::MacroFailureInfo;
using runtime::MacroCommandName;

namespace {

struct CommandLineOptions {
  std::string workingDirectory;
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
  bool sessionServer = false;
  std::string sessionRecordDir;
  std::string sessionReplayDir;
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
      << "  --working-directory <absolute-dir>  Enter this directory before reading inputs.\n"
      << "  --config, -c <file>  Load main ini configuration through "
         "SimulationManager.\n"
      << "  --macro, -m <file>   Execute a Geant4 macro after initialization "
         "setup.\n"
      << "  --output, -o <dir>   Override output directory.\n"
      << "  --run-name <name>    Override run name in SimulationManager.\n"
      << "  --ui                 Start an interactive Geant4 UI session.\n"
      << "  --ui-session csh   Required with --ui for the audited command-line session.\n"
      << "  --session-server   Serve the versioned JSON-lines controlled session on stdin/stdout.\n"
      << "  --session-record-dir <dir>  Absolute record directory outside --output for session receipts.\n"
      << "  --session-replay <session-dir>  Replay a completed session's captured random state in a new session.\n"
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
  const auto first = value.find_first_not_of(" \t\n\r\f\v");
  if (first == std::string::npos || value[first] == '-') {
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
    } else if (arg == "--session-server") {
      if (options.sessionServer) throw std::runtime_error("Duplicate --session-server");
      options.sessionServer = true;
    } else if (arg == "--session-replay") {
      if (!options.sessionReplayDir.empty()) throw std::runtime_error("Duplicate --session-replay");
      options.sessionReplayDir = RequireNonEmptyValue(i, argc, argv, arg);
    } else if (arg == "--session-record-dir") {
      if (!options.sessionRecordDir.empty()) throw std::runtime_error("Duplicate --session-record-dir");
      options.sessionRecordDir = RequireNonEmptyValue(i, argc, argv, arg);
    } else if (arg == "--working-directory") {
      if (!options.workingDirectory.empty()) throw std::runtime_error("Duplicate --working-directory");
      options.workingDirectory = RequireNonEmptyValue(i, argc, argv, arg);
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
  if (options.sessionServer) {
    if (options.interactive || !options.macroFile.empty() || options.dryRun)
      throw std::runtime_error("--session-server cannot be combined with --ui, --macro or --dry-run");
    if (options.configFile.empty())
      throw std::runtime_error("--session-server requires --config <main.ini>");
    if (options.sessionRecordDir.empty())
      throw std::runtime_error("--session-server requires --session-record-dir <outside-output-dir>");
  }
  if (!options.sessionReplayDir.empty() && !options.sessionServer)
    throw std::runtime_error("--session-replay requires --session-server");
  if (!options.uiSession.empty() && !options.interactive) {
    throw std::runtime_error("--ui-session requires --ui");
  }
  if (!options.dumpEffectiveConfig.empty() && (options.inspectRun || options.inspectMacro ||
      options.capabilities || options.checkGeant4Data || options.help || options.interactive || options.dryRun)) {
    throw std::runtime_error("--dump-effective-config is mutually exclusive with inspection, help, capabilities, data checks, --ui and --dry-run");
  }
  return options;
}


std::filesystem::path NormalizedAbsolutePath(const std::filesystem::path& path) {
  std::error_code absoluteError;
  const auto absolute = std::filesystem::absolute(path, absoluteError);
  const auto base = absoluteError ? path : absolute;
  std::error_code canonicalError;
  const auto canonical = std::filesystem::weakly_canonical(base, canonicalError);
  if (!canonicalError) return canonical;
  return base.lexically_normal();
}

std::string FolderKeyOf(std::filesystem::path path) {
  std::string text = path.lexically_normal().generic_u8string();
  while (text.size() > 1 && text.back() == '/') text.pop_back();
#ifdef _WIN32
  for (char& ch : text) {
    ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
  }
#endif
  return text;
}

bool PathIsInsideDirectory(const std::filesystem::path& root,
                           const std::filesystem::path& candidate) {
  const std::string rootKey = FolderKeyOf(root);
  const std::string candidateKey = FolderKeyOf(candidate);
  if (rootKey.empty()) return false;
  if (candidateKey == rootKey) return true;
  return candidateKey.rfind(rootKey + "/", 0) == 0;
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
  return CreateSimulationRunManager(sim.GetOutputManager(), sim.GetContext().GetNumThreads());
}

}  // namespace

int main(int argc, char** argv) {
  CommandLineOptions options;
  std::string invokedProgram = argc > 0 ? argv[0] : "";
  try {
    options = ParseCommandLine(argc, argv);
    if (!options.workingDirectory.empty()) {
      const auto directory = std::filesystem::u8path(NativeArgumentToUtf8(options.workingDirectory));
      if (!directory.is_absolute())
        throw std::runtime_error("--working-directory requires an absolute directory");
      std::error_code error;
      if (!std::filesystem::is_directory(directory, error))
        throw std::runtime_error("--working-directory is not an accessible directory: " + directory.u8string());
      // Preserve the executable locator's original base on non-Windows hosts.
      if (!invokedProgram.empty()) invokedProgram = std::filesystem::absolute(invokedProgram).string();
      std::filesystem::current_path(directory, error);
      if (error) throw std::runtime_error("Cannot apply --working-directory: " + error.message());
    }
  } catch (const std::exception& error) {
    // No Manager, data lookup, input reads or output writes before cwd succeeds.
    std::cerr << "G4UniversalSim fatal error: " << error.what() << std::endl;
    return EXIT_FAILURE;
  }
  SimulationManager sim;
  std::optional<MacroFailureInfo> macroFailure;
  std::string macroStatus = "not_run";
  runtime::ProcessFinalizationAttempt finalization;
  try {
    // An installed package points at an existing Geant4 data folder (roadmap D).
    const std::string dataNote = Geant4DataLocator::ApplyGeant4DataFile(invokedProgram.c_str());
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
          sim.SetEffectiveMacroInputs(plan.inputs);
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

    if (options.sessionServer && context.HasMacroFile()) {
      throw std::runtime_error(
          "--session-server does not support a preconfigured macro from the main INI "
          "([run] macro or equivalent): " + context.GetMacroFile() +
          "; remove the macro, or run this configuration as a batch/--ui session. "
          "The session protocol never executes a preset macro silently.");
    }
    if (!context.IsDryRun() && !context.IsInteractive() && !context.HasMacroFile() && !options.sessionServer) {
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
      sim.SetEffectiveMacroInputs(preflight.inputs);
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
    runtime::Geant4Execution execution(runManager.get());
    for (const std::string& command : sim.GetScoringMeshCommands()) {
      const G4int status = execution.ApplyCommand(command);
      if (status != 0) {
        throw std::runtime_error("[scoring.mesh.*] generated command failed (Geant4 status " +
                                 std::to_string(status) + "): " + command +
                                 "; check the scorer type, unit and particle names");
      }
    }
    ScoringMeshConfig::RecordEffectiveConfigDispatch();

    if (options.sessionServer) {
      if (options.sessionRecordDir.empty())
        throw std::runtime_error("--session-record-dir must not be empty");
      const std::filesystem::path requestedRecordRoot(options.sessionRecordDir);
      const auto outputRoot = NormalizedAbsolutePath(sim.GetContext().GetOutputDir());
      const auto recordRoot = NormalizedAbsolutePath(requestedRecordRoot);
      if (PathIsInsideDirectory(outputRoot, recordRoot))
        throw std::runtime_error("--session-record-dir must be outside --output: " +
                                 outputRoot.u8string());
      SessionServer session(sim, execution, recordRoot.u8string(), options.sessionReplayDir);
      const int sessionCode = session.Run();
      const auto& sessionRuns = sim.GetOutputManager()->GetRunSummary().GetRuns();
      const std::string sessionStatus = sessionCode == 0
          ? (sessionRuns.empty() ? "interactive_no_run" : "completed")
          : "failed";
      if (finalization.Run([&]() { return sim.FinalizeRunSummary(sessionStatus, sessionCode, "session_server"); }) != runtime::FinalizationAttemptResult::Completed) {
        std::cerr << "G4UniversalSim output finalization failed; see run_summary.txt\n";
        return EXIT_FAILURE;
      }
      return sessionCode;
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
      try {
        if (finalization.Run([&]() { return sim.FinalizeRunSummary("dry_run", EXIT_SUCCESS, "skipped_dry_run"); }) != runtime::FinalizationAttemptResult::Completed) {
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

    runtime::RunBatchAndCshSession(sim, *runManager, execution, preflight,
                                   {options.uiSession, options.seed.has_value()},
                                   macroFailure, macroStatus);

    const auto& runs = sim.GetOutputManager()->GetRunSummary().GetRuns();
    const std::string status = sim.GetContext().IsInteractive() && runs.empty()
        ? "interactive_no_run"
        : "completed";
    try {
      if (finalization.Run([&]() { return sim.FinalizeRunSummary(status, EXIT_SUCCESS, macroStatus); }) != runtime::FinalizationAttemptResult::Completed) {
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
    if (sim.IsConfigured() && !finalization.Started()) {
      try {
        finalization.Run([&]() { return sim.FinalizeRunSummary(
            "failed",
            EXIT_FAILURE,
            macroStatus,
            macroFailure->file,
            macroFailure->line,
            macroFailure->command,
            macroFailure->code); });
      } catch (const std::exception& summaryError) {
        std::cerr << "G4UniversalSim summary failure: "
                  << summaryError.what() << std::endl;
      }
    }
    std::cerr << "G4UniversalSim macro preflight failed: "
              << ex.what() << std::endl;
    return EXIT_FAILURE;
  } catch (const std::exception& ex) {
    if (sim.IsConfigured() && !finalization.Started()) {
      try {
        finalization.Run([&]() { return sim.FinalizeRunSummary(
            "failed",
            EXIT_FAILURE,
            macroStatus == "not_run" && !sim.GetContext().IsInteractive() ? "failed" : macroStatus,
            macroFailure ? macroFailure->file : "",
            macroFailure ? macroFailure->line : 0,
            macroFailure ? macroFailure->command : "",
            macroFailure ? macroFailure->code : 0,
            macroFailure ? macroFailure->codeAvailable : false); });
      } catch (const std::exception& summaryError) {
        std::cerr << "G4UniversalSim summary failure: "
                  << summaryError.what() << std::endl;
      }
    }
    std::cerr << "G4UniversalSim fatal error: " << ex.what() << std::endl;
    return EXIT_FAILURE;
  } catch (...) {
    if (sim.IsConfigured() && !finalization.Started()) {
      try {
        finalization.Run([&]() { return sim.FinalizeRunSummary("failed", EXIT_FAILURE, macroStatus,
            macroFailure ? macroFailure->file : "",
            macroFailure ? macroFailure->line : 0,
            macroFailure ? macroFailure->command : "",
            macroFailure ? macroFailure->code : 0,
            macroFailure ? macroFailure->codeAvailable : false); });
      } catch (const std::exception& summaryError) {
        std::cerr << "G4UniversalSim summary failure: "
                  << summaryError.what() << std::endl;
      }
    }
    std::cerr << "G4UniversalSim fatal error: unknown exception" << std::endl;
    return EXIT_FAILURE;
  }
}
