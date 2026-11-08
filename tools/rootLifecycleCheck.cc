// Real production TLS / SDK callbacks. No BeamOn or application finalization.
#include "Output/AnalysisOutput.hh"
#include "Output/OutputManager.hh"
#include "Output/OutputRecord.hh"
#include "Actions/RunAction.hh"
#include "Biasing/BiasingManager.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/ScorerBase.hh"
#include "Config/EffectiveConfig.hh"
#include "BuildInfo.hh"
#include "G4AnalysisManager.hh"
#include "G4Box.hh"
#include "G4LogicalVolume.hh"
#include "G4NistManager.hh"
#include "G4PVPlacement.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4StateManager.hh"
#include "G4VExceptionHandler.hh"
#include "G4VUserDetectorConstruction.hh"
#include "G4VUserPhysicsList.hh"
#include "G4Gamma.hh"
#include "G4Electron.hh"
#include "G4Positron.hh"
#include "G4Proton.hh"
#include "G4SystemOfUnits.hh"
#include "G4Version.hh"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>

namespace {
using Value = effective_config::Value;
int checks = 0;
void Require(bool condition, const char* message)
{
    if (!condition) throw std::runtime_error(message);
    ++checks;
}
Value Identity()
{
    return Value::Object{{"source_fingerprint", G4USIM_SOURCE_FINGERPRINT},
        {"probe_sha256", G4USIM_ROOT_LIFECYCLE_PROBE_SHA256},
        {"geant4_version_number", G4VERSION_NUMBER}, {"compiler", G4USIM_COMPILER_ID},
        {"compiler_version", G4USIM_COMPILER_VERSION}, {"build_configuration", G4USIM_BUILD_CONFIGURATION},
        {"git_commit", G4USIM_GIT_COMMIT}, {"git_source_state", G4USIM_GIT_SOURCE_STATE}};
}
void Save(const std::filesystem::path& path, const Value& value)
{
    std::ofstream file(path, std::ios::binary);
    file << value.ToJson() << '\n';
    file.close();
    if (!file) throw std::runtime_error("Cannot write probe result");
}
Value Failure(const OutputManager::OutputFailure& failure)
{
    return Value::Object{{"stage", failure.stage}, {"message", failure.message},
                         {"run", failure.runId}, {"thread", failure.threadId}};
}

void RootRuns(const std::filesystem::path& root, Value::Object& result)
{
    Require(!AnalysisOutput::IsOpen(), "TLS initially open");
    Require(!G4AnalysisManager::Instance()->IsOpenFile(), "native resource initially open");
    AnalysisOutput::H1Binning bins;
    bins.bins = 10; bins.min = 0; bins.max = 10;
    Value::Array runs;
    for (int run = 0; run < 2; ++run) {
        const auto path = root / ("run" + std::to_string(run) + ".root");
        AnalysisOutput::BeginRun(path.string(), bins, bins);
        const bool tlsOpen = AnalysisOutput::IsOpen();
        const bool nativeOpen = G4AnalysisManager::Instance()->IsOpenFile();
        Require(tlsOpen && nativeOpen, "Begin did not open TLS and actual ROOT file");
        const int count = run == 0 ? 2 : 1;
        for (int i = 0; i < count; ++i) {
            EventEdepRecord event;
            event.runID = run; event.eventID = run == 0 ? 11+i : 21;
            event.rawEdep = run == 0 ? 1+i : 3;
            event.weightedEdep = run == 0 ? 4+i : 6;
            AnalysisOutput::FillEvent(event, 0);
            AnalysisOutput::FillEdepHistograms(true, event.rawEdep, true, event.weightedEdep);
        }
        const bool ended = AnalysisOutput::EndRun();
        const bool tlsClosed = !AnalysisOutput::IsOpen();
        const bool nativeClosed = !G4AnalysisManager::Instance()->IsOpenFile();
        const bool repeated = AnalysisOutput::EndRun();
        Require(ended && tlsClosed && nativeClosed, "End did not close real resource");
        Require(!repeated, "repeated End retried");
        EventEdepRecord sentinel;
        sentinel.runID = 99; sentinel.eventID = 999; sentinel.rawEdep = 9.5; sentinel.weightedEdep = 9.5;
        AnalysisOutput::FillEvent(sentinel, 0);
        AnalysisOutput::FillEdepHistograms(true, 9.5, true, 9.5);
        Require(!AnalysisOutput::IsOpen() && !G4AnalysisManager::Instance()->IsOpenFile(), "closed Fill reopened resource");
        runs.emplace_back(Value::Object{{"run", run}, {"file", path.string()}, {"fills", count},
            {"tls_open_after_begin", tlsOpen}, {"native_open_after_begin", nativeOpen},
            {"end_return", ended}, {"tls_closed_after_end", tlsClosed}, {"native_closed_after_end", nativeClosed},
            {"repeat_end_return", repeated}, {"sentinel_event_id", 999}});
    }
    result["runs"] = std::move(runs);
}

class Detector final : public G4VUserDetectorConstruction {
    G4VPhysicalVolume* Construct() override
    {
        auto* solid = new G4Box("RootLifecycleWorld", 10*mm, 10*mm, 10*mm);
        auto* logical = new G4LogicalVolume(solid, G4NistManager::Instance()->FindOrBuildMaterial("G4_Galactic"), "RootLifecycleWorld");
        return new G4PVPlacement(nullptr, {}, logical, "RootLifecycleWorld", nullptr, false, 0);
    }
};
class MinimalPhysics final : public G4VUserPhysicsList {
    void ConstructParticle() override
    {
        G4Gamma::GammaDefinition(); G4Electron::ElectronDefinition();
        G4Positron::PositronDefinition(); G4Proton::ProtonDefinition();
    }
    void ConstructProcess() override { AddTransportation(); }
    void SetCuts() override { SetCutsWithDefault(); }
};
class Counter final : public ScorerBase {
public:
    Counter() : ScorerBase("root_lifecycle_counter") {}
    int begins = 0, ends = 0;
    void BeginRun(int) override { ++begins; }
    void EndRun(int) override { ++ends; }
};
class ObserveException final : public G4VExceptionHandler {
public:
    ObserveException(OutputManager& output, const int& effectiveBegin, std::string expected,
                     G4VExceptionHandler* previous)
        : output_(output), effectiveBegin_(effectiveBegin), expected_(std::move(expected)), previous_(previous) {}
    ~ObserveException() override { G4StateManager::GetStateManager()->SetExceptionHandler(previous_); }
    bool Notify(const char* origin, const char* code, G4ExceptionSeverity severity, const char* description) override
    {
        const auto failure = output_.GetOutputFailure();
        const bool observed = output_.HasOutputFailure() && failure.stage == "biasing_validate_active" &&
            failure.runId == 42 && failure.message == expected_ && effectiveBegin_ == 0;
        notifications.emplace_back(Value::Object{{"origin", origin}, {"code", code},
            {"severity", static_cast<int>(severity)}, {"description", description},
            {"latch_at_notify", Failure(failure)}, {"effective_begin_at_notify", effectiveBegin_},
            {"latch_precedes_exception", observed}});
        ordered = ordered && observed && std::string(origin) == "RunAction::BeginOfRunAction" &&
            std::string(code) == "AIHLBiasingTarget001" && severity == RunMustBeAborted &&
            std::string(description) == expected_;
        return false; // temporary test handler only; does not prove default-handler abort behavior
    }
    bool ordered = true;
    Value::Array notifications;
private:
    OutputManager& output_;
    const int& effectiveBegin_;
    std::string expected_;
    G4VExceptionHandler* previous_;
};

void EarlyBias(const std::filesystem::path& root, const std::string& mode, Value::Object& result)
{
    auto kernel = std::make_unique<G4RunManager>();
    kernel->SetUserInitialization(new Detector());
    kernel->SetUserInitialization(new MinimalPhysics());
    kernel->Initialize(); // real particle construction/readiness, never a readiness flag assignment
    Require(G4StateManager::GetStateManager()->GetCurrentState() == G4State_Idle, "kernel not initialized");
    result["kernel_initialized"] = true;
    OutputManager output;
    output.SetOutputDir((root / "output").string()); output.SetRunId(7);
    BiasingManager bias;
    bias.Enable(true);
    if (mode == "bias-unattached") {
        XSProcessBiasRule rule;
        rule.name = "gamma_compt"; rule.particleName = "gamma"; rule.processName = "compt";
        rule.factor = 2; rule.volumeNames = {"RootLifecycleWorld"};
        bias.AddXSProcessBiasRule(rule);
    }
    const std::string expected = mode == "bias-no-rules"
        ? "XS biasing is enabled but no process-level rule is active. Add a rule or disable biasing."
        : "XS biasing has active rules but no operator is attached to a geometry volume. Configure a valid rule volume or disable biasing.";
    ScoringManager scoring;
    scoring.SetAutoCreateDefaultScorers(false);
    auto counter = std::make_unique<Counter>(); auto* counts = counter.get();
    scoring.RegisterScorer(std::move(counter)); // direct instance use, no cloning
    int effectiveBegin = 0, effectiveEnd = 0;
    RunAction action(&scoring, &output, RunAction::Role::Sequential, &bias);
    action.SetEffectiveCallbacks([&](int, ScoringManager*, OutputManager*) { ++effectiveBegin; },
                                 [&](int, ScoringManager*, OutputManager*) { ++effectiveEnd; });
    G4Run run;
    run.SetRunID(42); run.SetNumberOfEventToBeProcessed(1);
    auto* previous = G4StateManager::GetStateManager()->GetExceptionHandler();
    {
        ObserveException observer(output, effectiveBegin, expected, previous);
        action.BeginOfRunAction(&run);
        Require(observer.notifications.size() == 1 && observer.ordered, "exception ordering/identity mismatch");
        result["notifications"] = observer.notifications;
        result["first_failure_after_begin"] = Failure(output.GetOutputFailure());
        Require(output.GetRunId() == 7, "early failure changed output run storage");
        action.EndOfRunAction(&run);
        Require(effectiveBegin == 0 && effectiveEnd == 1, "effective callback boundary");
        Require(counts->begins == 0 && counts->ends == 0, "unentered scorer called");
        Require(bias.GetWorkerEvidence().empty(), "unentered bias worker receipt");
        output.RecordOutputFailure("probe_cleanup_second_cause", "second cause", 99);
        const auto failure = output.GetOutputFailure();
        Require(failure.runId == 42 && failure.stage == "biasing_validate_active" && failure.message == expected,
                "End/cleanup overwrote first cause");
        result["first_failure_after_end_and_cleanup"] = Failure(failure);
    }
    Require(G4StateManager::GetStateManager()->GetExceptionHandler() == previous, "handler not restored");
    const auto& runs = output.GetRunSummary().GetRuns();
    Require(runs.size() == 1 && runs[0].runId == 42 && runs[0].plannedEvents == 1 && runs[0].completedEvents == 0,
            "callback run observation mismatch");
    for (const auto& item : std::filesystem::recursive_directory_iterator(root))
        Require(item.path().filename().string().find("scorer_statistics") == std::string::npos, "unexpected statistics file");
    output.GetRunSummary().WriteJson((root / "callback-summary.json").string());
    result["effective_begin"] = effectiveBegin; result["effective_end"] = effectiveEnd;
    result["scorer_begin"] = counts->begins; result["scorer_end"] = counts->ends;
    result["bias_worker_receipts"] = static_cast<int>(bias.GetWorkerEvidence().size());
    result["callback_run"] = Value::Object{{"run", 42}, {"planned", 1}, {"completed", 0}};
    result["handler_restored"] = true;
}
}  // namespace

int main(int argc, char** argv)
{
    if (argc == 2 && std::string(argv[1]) == "--identity") { std::cout << Identity().ToJson() << '\n'; return 0; }
    Value::Object result{{"identity", Identity()}, {"beam_on_called", false}, {"application_finalize_called", false}};
    std::filesystem::path root;
    bool created = false;
    try {
        if (argc != 3) throw std::runtime_error("usage: rootLifecycleCheck <root-two-runs|bias-no-rules|bias-unattached> <new-output-dir>");
        const std::string mode = argv[1]; root = std::filesystem::absolute(argv[2]);
        if (mode != "root-two-runs" && mode != "bias-no-rules" && mode != "bias-unattached") throw std::runtime_error("unknown mode");
        if (!std::filesystem::create_directory(root)) throw std::runtime_error("output directory must be new");
        created = true;
        result["mode"] = mode; result["output"] = root.string();
        if (mode == "root-two-runs") RootRuns(root, result); else EarlyBias(root, mode, result);
        result["status"] = "pass"; result["checks"] = checks;
        Save(root / "result.json", result);
        std::cout << "Root lifecycle component checks passed: " << checks << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "rootLifecycleCheck: " << error.what() << '\n';
        result["status"] = "fail"; result["error"] = error.what(); result["checks"] = checks;
        // Never overwrite an existing result when the requested directory was not new.
        if (created && !std::filesystem::exists(root / "result.json")) {
            try { Save(root / "result.json", result); } catch (...) {}
        }
        return 1;
    }
}
