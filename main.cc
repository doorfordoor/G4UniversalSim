#include "Actions/ActionInitialization.hh"
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
  bool interactive = false;
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
      << "  --config <file>   Load main ini configuration through "
         "SimulationManager.\n"
      << "  --macro <file>    Execute a Geant4 macro after initialization "
         "setup.\n"
      << "  --ui              Start an interactive Geant4 UI session.\n"
      << "  --threads <N>     Set requested number of worker threads when MT "
         "is available.\n"
      << "  --seed <N>        Set random seed in SimulationManager and CLHEP.\n"
      << "  --help, -h        Show this help.\n\n"
      << "If neither --macro nor --ui is supplied, no beamOn is run "
         "automatically.\n";
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
  std::size_t consumed = 0;
  const unsigned long parsed = std::stoul(value, &consumed);
  if (consumed != value.size()) {
    throw std::runtime_error("Invalid value for --seed: '" + value + "'");
  }
  return parsed;
}

CommandLineOptions ParseCommandLine(int argc, char** argv) {
  CommandLineOptions options;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];

    if (arg == "--help" || arg == "-h") {
      options.help = true;
    } else if (arg == "--config") {
      options.configFile = RequireValue(i, argc, argv, arg);
    } else if (arg == "--macro") {
      options.macroFile = RequireValue(i, argc, argv, arg);
    } else if (arg == "--ui") {
      options.interactive = true;
    } else if (arg == "--threads") {
      options.threads = ParsePositiveInt(RequireValue(i, argc, argv, arg), arg);
    } else if (arg == "--seed") {
      options.seed = ParseSeed(RequireValue(i, argc, argv, arg));
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
    if (options.help || (options.macroFile.empty() && !options.interactive)) {
      PrintUsage(argv[0]);
      return options.help ? EXIT_SUCCESS : EXIT_SUCCESS;
    }

    SimulationManager sim;
    if (!options.configFile.empty()) sim.SetMainConfig(options.configFile);
    if (!options.macroFile.empty()) sim.SetMacroFile(options.macroFile);
    sim.SetInteractive(options.interactive);
    if (options.threads) sim.SetNumThreads(*options.threads);
    if (options.seed) sim.SetSeed(*options.seed);

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

    auto actions = sim.CreateActionInitialization();
    runManager->SetUserInitialization(actions.release());

    std::unique_ptr<G4VisManager> visManager;
    if (options.interactive) {
      visManager = std::make_unique<G4VisExecutive>();
      visManager->Initialize();
    }

    G4UImanager* uiManager = G4UImanager::GetUIpointer();
    if (!uiManager) {
      throw std::runtime_error("G4UImanager::GetUIpointer returned null");
    }

    if (!options.macroFile.empty()) {
      const std::string command = "/control/execute " + options.macroFile;
      const int status = uiManager->ApplyCommand(command);
      if (status != 0) {
        throw std::runtime_error(
            "Failed to execute macro '" + options.macroFile +
            "', G4UImanager status=" + std::to_string(status));
      }
    }

    if (options.interactive) {
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
