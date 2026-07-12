#include "Actions/ActionInitialization.hh"
#include "Core/MacroPreflight.hh"
#include "Core/SimulationManager.hh"
#include "Detector/DetectorConstruction.hh"
#include "G4RunManager.hh"
#include "G4UIExecutive.hh"
#include "G4UImanager.hh"
#include "G4VModularPhysicsList.hh"
#include "G4VisExecutive.hh"
#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
#endif

#include <cstdlib>
#include <exception>
#include <filesystem>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>

#include "Randomize.hh"

namespace {

struct CommandLineOptions {
  std::string configFile;
  std::string macroFile;
  std::string outputDir;
  std::string runName;
  bool interactive = false;
  bool dryRun = false;
  std::optional<bool> checkOverlaps;
  std::optional<int> threads;
  std::optional<unsigned long> seed;
  bool help = false;
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
      << "  --threads, -t <N>    Set requested number of worker threads when "
         "MT "
         "is available.\n"
      << "  --seed <N>           Set random seed in SimulationManager and "
         "CLHEP.\n"
      << "  --check-overlaps <true|false>  Override geometry overlap checks.\n"
      << "  --dry-run            Configure and register Geant4 objects but "
         "skip macro/UI execution.\n"
      << "  --help, -h           Show this help.\n\n"
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
  return options;
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
  try {
    const CommandLineOptions options = ParseCommandLine(argc, argv);
    if (options.help) {
      PrintUsage(argv[0]);
      return EXIT_SUCCESS;
    }

    SimulationManager sim;
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

    sim.Configure();
    const SimulationContext& context = sim.GetContext();
    if (!context.IsDryRun() && !context.IsInteractive() && !context.HasMacroFile()) {
      PrintUsage(argv[0]);
      return EXIT_SUCCESS;
    }

    MacroPreflightResult preflight;
    if (!context.IsDryRun() && context.HasMacroFile()) {
      MacroPreflightLocks locks;
      locks.outputDir = cliOverrides.outputDir.has_value();
      locks.numThreads = cliOverrides.numThreads.has_value();
      locks.seed = cliOverrides.seed.has_value();
      locks.checkOverlaps = cliOverrides.checkOverlaps.has_value();
      preflight = PreflightMacro(context.GetMacroFile(), locks);
    }

    sim.Initialize();
    if (sim.GetContext().HasSeed()) {
      CLHEP::HepRandom::setTheSeed(
          static_cast<long>(sim.GetContext().GetSeed()));
    }

    auto runManager = CreateRunManager(sim);

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
      return EXIT_SUCCESS;
    }

    if (!sim.GetContext().GetMacroFile().empty()) {
      for (const auto& command : preflight.commands) {
        const int status = uiManager->ApplyCommand(command.text.c_str());
        if (status != 0) {
          throw std::runtime_error(
              "Failed to execute macro command '" + command.text + "' at " +
              command.sourceFile.string() + ":" +
              std::to_string(command.lineNumber) +
              ", G4UImanager status=" + std::to_string(status));
        }
      }
    }

    if (sim.GetContext().IsInteractive()) {
      G4UIExecutive ui(argc, argv);
      ui.SessionStart();
    }

    return EXIT_SUCCESS;
  } catch (const std::exception& ex) {
    std::cerr << "G4UniversalSim fatal error: " << ex.what() << std::endl;
    return EXIT_FAILURE;
  } catch (...) {
    std::cerr << "G4UniversalSim fatal error: unknown exception" << std::endl;
    return EXIT_FAILURE;
  }
}
