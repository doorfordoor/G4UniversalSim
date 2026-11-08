// Component-only port checks against the production session coordinator.
// No kernel Initialize/BeamOn, physics construction, or transport is requested.
#include "Core/RuntimeExecution.hh"
#include "Core/RuntimeSession.hh"
#include "Core/RunFinalization.hh"
#include "Biasing/BiasingManager.hh"
#include "Core/SimulationManager.hh"
#include "Core/MacroPreflight.hh"
#include "Config/EffectiveConfig.hh"
#include "BuildInfo.hh"
#include "G4RunManager.hh"
#include "G4Version.hh"
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
int checks = 0;
void Require(bool value, const char* message)
{
    if (!value) throw std::runtime_error(message);
    ++checks;
}

void CheckFinalizationAttempt()
{
    using Result = runtime::FinalizationAttemptResult;
    for (int mode = 0; mode < 4; ++mode) {
        int calls = 0;
        runtime::ProcessFinalizationAttempt attempt;
        bool caught = false;
        try {
            const auto result = attempt.Run([&]() {
                ++calls;
                Require(attempt.Started(), "attempt not recorded before IO");
                Require(attempt.Run([&]() { ++calls; return true; }) == Result::AlreadyAttempted,
                        "reentrant finalization not refused");
                if (mode == 2) throw std::runtime_error("finalization first cause");
                if (mode == 3) throw 31;
                return mode == 0;
            });
            Require(result == (mode == 0 ? Result::Completed : Result::Failed), "finalization result changed");
        } catch (const std::runtime_error& error) {
            caught = true;
            Require(mode == 2 && std::string(error.what()) == "finalization first cause", "finalization exception changed");
        } catch (int error) {
            caught = true;
            Require(mode == 3 && error == 31, "nonstandard finalization exception changed");
        }
        Require(caught == (mode >= 2), "finalization throw outcome changed");
        Require(attempt.Run([&]() { ++calls; return true; }) == Result::AlreadyAttempted,
                "second finalization not refused");
        Require(calls == 1 && attempt.Started(), "finalizer retried");
    }
}

class RecordingExecution final : public runtime::NativeExecutionPort {
public:
    int status = 0;
    bool throwStd = false;
    bool throwNonStd = false;
    int failAt = 1;
    int initializeFault = 0;
    int initializations = 0;
    int runs = 0;
    std::vector<std::string> commands;
    int ApplyCommand(const std::string& command) override
    {
        commands.push_back(command);
        if (throwStd && commands.size() == static_cast<std::size_t>(failAt)) throw std::runtime_error("port exception");
        if (throwNonStd && commands.size() == static_cast<std::size_t>(failAt)) throw 17;
        return status;
    }
    void InitializeKernel() override {
        ++initializations;
        if (initializeFault == 1) throw std::runtime_error("initialization first cause");
        if (initializeFault == 2) throw 41;
    }
    void BeamOn(int) override { ++runs; }
};

void CheckBatch(G4RunManager& kernel, int mode, int failAt = 1)
{
    SimulationManager simulation;
    simulation.Configure();
    simulation.SetMacroFile("component-only.mac");
    MacroPreflightResult plan;
    plan.commands.push_back({"component-only.mac", 7, "/control/verbose 0", "input-sha", ""});
    plan.commands.push_back({"component-only.mac", 8, "/control/verbose 1", "input-sha", ""});
    RecordingExecution port;
    port.failAt = failAt;
    port.status = mode == 1 ? 100 : 0;
    port.throwStd = mode == 2;
    port.throwNonStd = mode == 3;
    std::optional<runtime::MacroFailureInfo> failure;
    std::string macroStatus = "not_run";
    bool caught = false;
    try {
        runtime::RunBatchAndCshSession(simulation, kernel, port, plan, {}, failure, macroStatus);
    } catch (const std::runtime_error& error) {
        caught = true;
        Require(mode == 1 || mode == 2, "unexpected standard exception");
        if (mode == 2) Require(std::string(error.what()) == "port exception", "port first cause changed");
    } catch (int value) {
        caught = true;
        Require(mode == 3 && value == 17, "nonstandard exception changed");
    }
    Require(caught == (mode != 0), "exception outcome");
    Require(port.commands.size() == (mode == 0 ? 2u : static_cast<std::size_t>(failAt)), "dispatch continued after failure");
    Require(port.commands.front() == plan.commands.front().text, "normalized command changed");
    Require(port.initializations == 0 && port.runs == 0, "command dispatch conflated with direct run");
    if (mode == 0) {
        Require(macroStatus == "completed" && !failure, "normal diagnostic state");
    } else if (mode == 1) {
        Require(macroStatus == "failed" && failure.has_value(), "UI refusal diagnostic missing");
        Require(failure->file == "component-only.mac" && failure->line == 7 &&
                failure->command == plan.commands.front().text, "command origin changed");
        Require(failure->codeAvailable && failure->code == 100, "actual UI status lost");
    } else {
        Require(macroStatus == "failed" && failure.has_value(), "dispatch exception diagnostic missing");
        Require(failure->file == "component-only.mac" && failure->line == 6 + failAt &&
                failure->command == plan.commands[failAt - 1].text, "dispatch exception origin lost");
        Require(!failure->codeAvailable && failure->code == 0, "invented returned-status evidence");
    }
}

void CheckInitializationFailure(G4RunManager& kernel, int mode)
{
    SimulationManager simulation;
    simulation.Configure();
    simulation.SetMacroFile("implicit-initialize.mac");
    simulation.GetBiasingManager()->Enable(true);
    MacroPreflightResult plan;
    plan.commands.push_back({"implicit-initialize.mac", 19, "/run/beamOn 1", "input-sha", ""});
    plan.commands.push_back({"implicit-initialize.mac", 20, "/control/verbose 1", "input-sha", ""});
    RecordingExecution port;
    port.initializeFault = mode;
    std::optional<runtime::MacroFailureInfo> failure;
    std::string status = "not_run";
    bool caught = false;
    try { runtime::RunBatchAndCshSession(simulation, kernel, port, plan, {}, failure, status); }
    catch (const std::runtime_error& error) {
        caught = true;
        Require(mode == 1 && std::string(error.what()) == "initialization first cause", "initialization exception changed");
    } catch (int error) {
        caught = true;
        Require(mode == 2 && error == 41, "initialization nonstandard exception changed");
    }
    Require(caught && port.initializations == 1 && port.commands.empty() && port.runs == 0,
            "initialization failure did not stop dispatch");
    Require(status == "failed" && failure.has_value(), "initialization diagnostic absent");
    Require(failure->file == "implicit-initialize.mac" && failure->line == 19 &&
            failure->command == "/run/beamOn 1", "initialization triggering command lost");
    Require(failure->code == 0 && !failure->codeAvailable, "fabricated initialization UI code");
}
}  // namespace

int main(int argc, char** argv)
{
    try {
        if (argc == 2 && std::string(argv[1]) == "--identity") {
            std::cout << effective_config::Value(effective_config::Value::Object{
                {"source_fingerprint", G4USIM_SOURCE_FINGERPRINT},
                {"probe_sha256", G4USIM_RUNTIME_SESSION_PROBE_SHA256},
                {"geant4_version_number", G4VERSION_NUMBER},
                {"compiler", G4USIM_COMPILER_ID},
                {"compiler_version", G4USIM_COMPILER_VERSION},
                {"build_configuration", G4USIM_BUILD_CONFIGURATION},
                {"git_commit", G4USIM_GIT_COMMIT},
                {"git_source_state", G4USIM_GIT_SOURCE_STATE}}).ToJson() << '\n';
            return 0;
        }
        if (argc != 1) throw std::runtime_error("usage: runtimeSessionCheck [--identity]");
        G4RunManager kernel;
        CheckFinalizationAttempt();
        for (int mode = 0; mode != 4; ++mode) CheckBatch(kernel, mode);
        CheckBatch(kernel, 2, 2);
        CheckBatch(kernel, 3, 2);
        CheckInitializationFailure(kernel, 1);
        CheckInitializationFailure(kernel, 2);
        std::cout << "Runtime session component checks passed: " << checks << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "runtimeSessionCheck failed: " << error.what() << '\n';
    } catch (...) {
        std::cerr << "runtimeSessionCheck failed: nonstandard exception\n";
    }
    return 1;
}
