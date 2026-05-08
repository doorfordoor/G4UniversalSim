// main.cc - G4UniversalSim minimal test entry point
//
// 用途：
// 1. 创建 SimulationManager
// 2. 创建 Geant4 RunManager
// 3. 将 DetectorConstruction / PhysicsList / ActionInitialization 交给 RunManager
// 4. 执行 macro
//
// 推荐测试：
//   ./G4UniversalSim -m ../macros/test_simple_min.mac
//   ./G4UniversalSim -c ../config/main.ini -m ../macros/run_simple.mac
//
// Windows 示例：
//   .\Debug\G4UniversalSim.exe -m ..\macros\test_simple_min.mac
//   .\Debug\G4UniversalSim.exe -c ..\config\main.ini -m ..\macros\run_simple.mac

#include <exception>
#include <iostream>
#include <memory>
#include <string>

#include "Core/SimulationManager.hh"

#include "G4RunManager.hh"
#include "G4UImanager.hh"

#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
#endif

namespace {

    struct CliOptions {
        std::string mainConfig;
        std::string macroFile;
        std::string outputDir;
        int numThreads = 1;
        bool printHelp = false;
    };

    void PrintUsage(const char* exeName) {
        std::cout
            << "Usage:\n"
            << "  " << exeName << " -m <macro.mac>\n"
            << "  " << exeName << " -c <config/main.ini> -m <macro.mac>\n"
            << "  " << exeName << " -c <config/main.ini> -m <macro.mac> -o <output_dir>\n"
            << "  " << exeName << " -c <config/main.ini> -m <macro.mac> -t <threads>\n"
            << "\n"
            << "Options:\n"
            << "  -c, --config   Main ini config file\n"
            << "  -m, --macro    Geant4 macro file to execute\n"
            << "  -o, --output   Output directory\n"
            << "  -t, --threads  Number of worker threads, if Geant4 MT is enabled\n"
            << "  -h, --help     Show this help\n"
            << "\n"
            << "Minimal examples:\n"
            << "  " << exeName << " -m ../macros/test_simple_min.mac\n"
            << "  " << exeName << " -c ../config/main.ini -m ../macros/run_simple.mac\n";
    }

    CliOptions ParseArgs(int argc, char** argv) {
        CliOptions opt;

        for (int i = 1; i < argc; ++i) {
            const std::string arg = argv[i];

            auto requireValue = [&](const std::string& name) -> std::string {
                if (i + 1 >= argc) {
                    throw std::runtime_error("Missing value after argument: " + name);
                }
                return argv[++i];
                };

            if (arg == "-h" || arg == "--help") {
                opt.printHelp = true;
            }
            else if (arg == "-c" || arg == "--config") {
                opt.mainConfig = requireValue(arg);
            }
            else if (arg == "-m" || arg == "--macro") {
                opt.macroFile = requireValue(arg);
            }
            else if (arg == "-o" || arg == "--output") {
                opt.outputDir = requireValue(arg);
            }
            else if (arg == "-t" || arg == "--threads") {
                opt.numThreads = std::stoi(requireValue(arg));
                if (opt.numThreads <= 0) {
                    throw std::runtime_error("Thread count must be positive.");
                }
            }
            else {
                throw std::runtime_error("Unknown argument: " + arg);
            }
        }

        return opt;
    }

} // namespace

int main(int argc, char** argv) {
    try {
        std::cout << "G4UniversalSim - minimal test main" << std::endl;

        const CliOptions opt = ParseArgs(argc, argv);

        if (opt.printHelp) {
            PrintUsage(argv[0]);
            return 0;
        }

        if (opt.macroFile.empty()) {
            std::cerr << "[Error] No macro file specified.\n\n";
            PrintUsage(argv[0]);
            return 1;
        }

        // 1. 创建项目级 SimulationManager。
        //    它持有 Config / Output / Material / Geometry / Physics / Source / Biasing / Scoring managers。
        SimulationManager simManager;

        if (!opt.mainConfig.empty()) {
            simManager.SetMainConfig(opt.mainConfig);
        }

        if (!opt.outputDir.empty()) {
            simManager.SetOutputDir(opt.outputDir);
        }

        simManager.SetNumThreads(opt.numThreads);
        simManager.SetMacroFile(opt.macroFile);

        // 2. 配置项目 managers。
        //
        // 有 main.ini 时：
        //   使用 SimulationManager::Initialize() 读取 config 并转发到各 manager。
        //
        // 无 main.ini 时：
        //   只 BuildManagers()，让 macro 里的 /AIHL/... 命令在 /run/initialize 前配置各模块。
        //
        // 这种方式适合当前调试：
        //   - 可以用 -c 测配置驱动；
        //   - 也可以只用 -m 测 messenger 命令驱动。
        if (!opt.mainConfig.empty()) {
            simManager.Initialize();
        }
        else {
            simManager.BuildManagers();
        }

        simManager.PrintSummary();

        // 3. 创建 Geant4 RunManager。
#ifdef G4MULTITHREADED
        auto runManager = std::make_unique<G4MTRunManager>();
        runManager->SetNumberOfThreads(opt.numThreads);
#else
        auto runManager = std::make_unique<G4RunManager>();
        if (opt.numThreads != 1) {
            std::cout
                << "[Warning] This Geant4 build is not multi-threaded. "
                << "Ignoring requested thread count: " << opt.numThreads << std::endl;
        }
#endif

        // 4. 将项目模块交给 Geant4 生命周期。
        //
        // 注意：
        //   SetUserInitialization() 接管裸指针生命周期；
        //   因此这里使用 unique_ptr::release()。
        auto detector = simManager.CreateDetectorConstruction();
        auto physics = simManager.CreatePhysicsList();
        auto actions = simManager.CreateActionInitialization();

        if (!detector) {
            throw std::runtime_error("SimulationManager::CreateDetectorConstruction() returned null.");
        }
        if (!physics) {
            throw std::runtime_error("SimulationManager::CreatePhysicsList() returned null.");
        }
        if (!actions) {
            throw std::runtime_error("SimulationManager::CreateActionInitialization() returned null.");
        }

        runManager->SetUserInitialization(detector.release());
        runManager->SetUserInitialization(physics.release());
        runManager->SetUserInitialization(actions.release());

        // 5. 执行 macro。
        //
        // macro 中应该包含：
        //   /run/initialize
        //   /run/beamOn N
        //
        // 如果你只想测试初始化，也可以只写到 /run/initialize。
        G4UImanager* ui = G4UImanager::GetUIpointer();
        if (!ui) {
            throw std::runtime_error("G4UImanager::GetUIpointer() returned null.");
        }

        const std::string command = "/control/execute " + opt.macroFile;
        const G4int status = ui->ApplyCommand(command);

        if (status != 0) {
            std::cerr
                << "[Error] Macro execution failed. Geant4 UI status = "
                << status << std::endl;
            return 2;
        }

        // 6. 主动销毁 RunManager，触发 Geant4 清理。
        runManager.reset();

        std::cout << "G4UniversalSim finished successfully." << std::endl;
        return 0;

    }
    catch (const std::exception& e) {
        std::cerr << "[Fatal] " << e.what() << std::endl;
        return 1;
    }
    catch (...) {
        std::cerr << "[Fatal] Unknown exception." << std::endl;
        return 1;
    }
}