// AR2 native lifecycle probe. Test registration belongs here, never in main.cc.
// No production switches/environment defaults are introduced by this executable.
#include "Actions/ActionInitialization.hh"
#include "Actions/RunManagerFactory.hh"
#include "Config/InputProvenance.hh"
#include "Core/SessionJson.hh"
#include "Core/SimulationManager.hh"
#include "Detector/DetectorConstruction.hh"
#include "Output/OutputManager.hh"
#include "Output/RunSummary.hh"
#include "Scoring/ScorerFactory.hh"
#include "Scoring/ScoringManager.hh"
#include "Source/PrimaryGeneratorAction.hh"
#include "Source/SourceManager.hh"
#include "BuildInfo.hh"
#include "G4Event.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4ScoringManager.hh"
#include "G4Threading.hh"
#include "G4UImanager.hh"
#include "G4UserEventAction.hh"
#include "G4UserRunAction.hh"
#include "G4VModularPhysicsList.hh"
#include "G4Version.hh"
#include "Randomize.hh"
#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
#endif

#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <typeinfo>
#include <utility>
#include <vector>

// Primary integration must embed the SHA of THIS tools source, separately from
// BuildInfo (the application's C++ fingerprint does not include tools/*.cc).
#ifndef G4USIM_SCORING_LIFECYCLE_PROBE_SHA256
#define G4USIM_SCORING_LIFECYCLE_PROBE_SHA256 "unavailable"
#endif
#ifndef G4USIM_BUILD_CONFIGURATION
#define G4USIM_BUILD_CONFIGURATION "unknown"
#endif

namespace {
using Json = SessionJson::Json;
namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

void Require(bool condition, const std::string& message)
{
    if (!condition) throw std::runtime_error(message);
}

struct Options {
    fs::path config, output, probeSource, runFrom;
    std::string mode = "normal", startup = "explicit", exception = "std";
    int workers = 1, eventModulo = 1, faultThread = -1, delayMs = 50, gateTimeoutMs = 10000;
    std::vector<int> events{12, 8};
    unsigned long seed = 20261108;
    bool sequential = false, help = false, identity = false;
};

int Integer(const std::string& text)
{
    std::size_t end = 0;
    const int n = std::stoi(text, &end);
    Require(end == text.size(), "invalid integer: " + text);
    return n;
}

Options Parse(int argc, char** argv)
{
    Options o;
    for (int i = 1; i < argc; ++i) {
        const std::string key = argv[i];
        if (key == "--help") { o.help = true; return o; }
        if (key == "--identity") { Require(argc == 2, "--identity is a standalone identity query"); o.identity = true; return o; }
        if (key == "--sequential") { o.sequential = true; continue; }
        Require(i + 1 < argc, "missing value for " + key);
        const std::string value = argv[++i];
        if (key == "--config") o.config = fs::u8path(value);
        else if (key == "--output") o.output = fs::u8path(value);
        else if (key == "--probe-source") o.probeSource = fs::u8path(value);
        else if (key == "--run-from") o.runFrom = fs::u8path(value);
        else if (key == "--mode") o.mode = value;
        else if (key == "--startup") o.startup = value;
        else if (key == "--exception") o.exception = value;
        else if (key == "--workers") o.workers = Integer(value);
        else if (key == "--event-modulo") o.eventModulo = Integer(value);
        else if (key == "--fault-thread") {
            o.faultThread = value == "last" ? -1 : Integer(value);
            Require(value == "last" || o.faultThread >= 0, "fault-thread must be nonnegative or last");
        }
        else if (key == "--delay-ms") o.delayMs = Integer(value);
        else if (key == "--gate-timeout-ms") o.gateTimeoutMs = Integer(value);
        else if (key == "--seed") {
            Require(!value.empty() && value.find_first_not_of("0123456789") == std::string::npos, "invalid seed");
            std::size_t end = 0; o.seed = std::stoul(value, &end);
            Require(end == value.size() && o.seed <= static_cast<unsigned long>(std::numeric_limits<long>::max()), "seed exceeds engine long range");
        } else if (key == "--events") {
            const auto comma = value.find(',');
            Require(comma != std::string::npos && value.find(',', comma + 1) == std::string::npos, "--events needs two counts");
            o.events = {Integer(value.substr(0, comma)), Integer(value.substr(comma + 1))};
        } else throw std::runtime_error("unknown probe option: " + key);
    }
    const std::set<std::string> modes{"normal", "worker-throw", "worker-delayed-throw", "legacy-clone",
        "register-empty", "register-null", "register-unknown", "register-wrong-name", "register-duplicate",
        "register-throw-std", "register-throw-nonstd"};
    Require(modes.count(o.mode) != 0, "unknown probe mode");
    Require(o.startup == "explicit" || o.startup == "direct-beamon", "unknown startup mode");
    Require(o.exception == "std" || o.exception == "nonstd", "exception must be std or nonstd");
    Require(o.workers == 1 || o.workers == 2 || o.workers == 4, "workers must be 1,2,4");
    Require(!o.sequential || o.workers == 1, "realSequential requires --workers 1");
    Require(o.eventModulo >= 1 && o.eventModulo <= 100000, "invalid event modulo");
    Require(o.events[0] > 0 && o.events[1] > 0, "both runs need positive counts");
    Require(o.delayMs >= 0 && o.delayMs <= 10000 && o.gateTimeoutMs >= 1 && o.gateTimeoutMs <= 60000, "invalid delay/timeout");
    if (o.mode == "worker-delayed-throw") {
        Require(o.faultThread == -1 || o.faultThread == o.workers - 1, "delayed failure must target last worker");
        o.faultThread = o.workers - 1;
    } else if (o.faultThread == -1) o.faultThread = 0;
    Require(o.faultThread >= 0 && o.faultThread < o.workers, "fault thread outside worker set");
    Require(!o.config.empty() && !o.output.empty() && !o.probeSource.empty(), "required: --config --output --probe-source");
    o.config = fs::absolute(o.config); o.output = fs::absolute(o.output); o.probeSource = fs::absolute(o.probeSource);
    Require(fs::is_regular_file(o.config) && fs::is_regular_file(o.probeSource), "input/source missing");
    Require(!fs::exists(o.output) && !fs::is_symlink(o.output), "output must be a fresh directory");
    return o;
}

struct State {
    explicit State(const Options& options) : options(options) {}
    const Options& options;
    std::mutex mutex;
    std::condition_variable arrivedChanged;
    std::set<int> arrived;
    Json trace = Json::array();
    std::map<int, std::vector<int>> scorerEvents;
    std::uint64_t sequence = 0, instanceSerial = 0;
    std::atomic<bool> observationError{false}, gateTimedOut{false};
    std::atomic<std::int64_t> primaryCalls{0}, primaryVertices{0}, eventBegin{0}, eventEnd{0}, aborted{0};

    std::string Role() const {
        if (options.sequential) return "sequential";
        return G4Threading::G4GetThreadId() < 0 ? "master" : "worker";
    }
    void NoteLocked(Json row) {
        row["seq"] = ++sequence;
        row["monotonic_ns"] = std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count();
        row["native_thread_id"] = G4Threading::G4GetThreadId();
        row["role"] = Role();
        trace.push_back(std::move(row));
    }
    void Note(Json row) noexcept {
        try { std::lock_guard<std::mutex> lock(mutex); NoteLocked(std::move(row)); }
        catch (...) { observationError.store(true); }
    }
    std::uint64_t NewInstance() { std::lock_guard<std::mutex> lock(mutex); return ++instanceSerial; }
    void FactoryArrival(int thread) {
        std::lock_guard<std::mutex> lock(mutex);
        arrived.insert(thread);
        NoteLocked({{"kind", "factory_arrived"}, {"factory_thread_id", thread}});
        arrivedChanged.notify_all();
    }
    void DelayLast(int thread, int delayMs, int timeoutMs) {
        std::unique_lock<std::mutex> lock(mutex);
        const auto othersArrived = [&] {
            for (int id = 0; id < options.workers; ++id) if (id != thread && !arrived.count(id)) return false;
            return true;
        };
        NoteLocked({{"kind", "delay_gate_enter"}, {"factory_thread_id", thread}, {"arrived_factory_threads", arrived}});
        const bool ready = arrivedChanged.wait_for(lock, std::chrono::milliseconds(timeoutMs), othersArrived);
        NoteLocked({{"kind", "delay_gate_release"}, {"factory_thread_id", thread}, {"all_other_factories_arrived", ready},
                    {"arrived_factory_threads", arrived}, {"not_a_kernel_ready_barrier", true}});
        lock.unlock();
        if (!ready) { gateTimedOut.store(true); throw std::runtime_error("probe delay gate timed out: not an expected factory fault"); }
        // Extra delay is diagnostic only: the condition-variable predicate is
        // the deterministic witness; realSequential waits for zero peers.
        if (delayMs) std::this_thread::sleep_for(std::chrono::milliseconds(delayMs));
    }
};

State* active = nullptr; // observation sink; the registered factory has no captures

class Counter final : public ScorerBase {
public:
    Counter(std::string name, int factoryThread)
        : ScorerBase(std::move(name)), id_(active->NewInstance()), factoryThread_(factoryThread) {
        std::ostringstream address; address << static_cast<const void*>(this);
        active->Note({{"kind", "instance_construct"}, {"instance", id_}, {"pointer_diagnostic", address.str()}, {"factory_thread_id", factoryThread_}});
    }
    ~Counter() override { active->Note({{"kind", "instance_destroy"}, {"instance", id_}, {"factory_thread_id", factoryThread_}}); }
    void BeginRun(int run) override {
        run_ = run; events_.clear(); sum_ = 0;
        active->Note({{"kind", "scorer_begin_run"}, {"instance", id_}, {"factory_thread_id", factoryThread_}, {"run", run}, {"reset", true}});
    }
    void BeginEvent(int event) override {
        active->Note({{"kind", "scorer_begin_event"}, {"instance", id_}, {"run", run_}, {"event", event}});
    }
    void EndEvent(int event) override {
        events_.push_back(event); sum_ += event % 2;
        { std::lock_guard<std::mutex> lock(active->mutex); active->scorerEvents[run_].push_back(event); }
        active->Note({{"kind", "scorer_end_event"}, {"instance", id_}, {"run", run_}, {"event", event}, {"test_units", event % 2}});
    }
    void EndRun(int run) override {
        active->Note({{"kind", "scorer_end_run"}, {"instance", id_}, {"factory_thread_id", factoryThread_}, {"run", run},
                      {"events", events_}, {"n_events", events_.size()}, {"sum_test_units", sum_}, {"sum_sq_test_units2", sum_}});
    }
private:
    std::uint64_t id_;
    int factoryThread_, run_ = -1;
    std::vector<int> events_;
    std::int64_t sum_ = 0;
};

double Parameter(const ScorerDescription& d, const std::string& name, double fallback = 0)
{
    const auto it = d.Settings().parameters.find(name);
    return it == d.Settings().parameters.end() ? fallback : it->second;
}

std::unique_ptr<ScorerBase> Factory(const ScorerDescription& d, int thread)
{
    active->Note({{"kind", "factory_enter"}, {"factory_phase", thread < 0 ? "registration" : "clone"},
                  {"factory_thread_id", thread}, {"type", d.Type()}, {"requested_name", d.Id()}});
    if (thread >= 0) active->FactoryArrival(thread);
    const bool registrationFault = Parameter(d, "registration_failure") != 0;
    const bool workerFault = thread >= 0 && Parameter(d, "worker_failure") != 0 && thread == static_cast<int>(Parameter(d, "faultthread"));
    if (registrationFault || workerFault) {
        if (workerFault && Parameter(d, "delay_enabled") != 0)
            active->DelayLast(thread, static_cast<int>(Parameter(d, "delayms")), static_cast<int>(Parameter(d, "gate_timeout_ms")));
        active->Note({{"kind", "factory_throw"}, {"factory_thread_id", thread}, {"exception", Parameter(d, "nonstd") != 0 ? "nonstd" : "std"}});
        if (Parameter(d, "nonstd") != 0) throw 17;
        throw std::runtime_error("scoringLifecycleCheck deliberate factory throw thread=" + std::to_string(thread));
    }
    if (Parameter(d, "return_null") != 0) { active->Note({{"kind", "factory_return_null"}}); return nullptr; }
    auto result = std::make_unique<Counter>(Parameter(d, "wrong_name") != 0 ? "wrong-probe-name" : d.Id(), thread);
    active->Note({{"kind", "factory_return"}, {"factory_thread_id", thread}, {"returned_name", result->GetName()}});
    return result;
}

int CurrentRun()
{
    const auto* manager = G4RunManager::GetRunManager();
    const auto* run = manager ? manager->GetCurrentRun() : nullptr;
    return run ? run->GetRunID() : -1;
}

// Decorate the actual production-installed actions; preserve their ownership
// and all callbacks. Never replace production scoring/output actions by stubs.
class ObservedPrimary final : public PrimaryGeneratorAction {
public:
    explicit ObservedPrimary(std::unique_ptr<PrimaryGeneratorAction> delegate)
        : PrimaryGeneratorAction(delegate->GetSourceManager()), delegate_(std::move(delegate)) {}
    void GeneratePrimaries(G4Event* event) override {
        ++active->primaryCalls;
        active->Note({{"kind", "primary_enter"}, {"run", CurrentRun()}, {"event", event ? event->GetEventID() : -1}});
        delegate_->GeneratePrimaries(event);
        if (event) {
            active->primaryVertices.fetch_add(event->GetNumberOfPrimaryVertex());
            active->Note({{"kind", "primary_vertices_after_generation"}, {"run", CurrentRun()}, {"event", event->GetEventID()},
                          {"vertices", event->GetNumberOfPrimaryVertex()}, {"aborted", event->IsAborted()}});
        }
    }
private:
    std::unique_ptr<PrimaryGeneratorAction> delegate_;
};

class ObservedEvent final : public G4UserEventAction {
public:
    explicit ObservedEvent(std::unique_ptr<G4UserEventAction> delegate) : delegate_(std::move(delegate)) {}
    void BeginOfEventAction(const G4Event* event) override {
        ++active->eventBegin;
        active->Note({{"kind", "event_begin_observed"}, {"run", CurrentRun()}, {"event", event ? event->GetEventID() : -1}});
        delegate_->BeginOfEventAction(event);
    }
    void EndOfEventAction(const G4Event* event) override {
        delegate_->EndOfEventAction(event);
        ++active->eventEnd;
        if (event && event->IsAborted()) ++active->aborted;
        active->Note({{"kind", "event_end_observed"}, {"run", CurrentRun()}, {"event", event ? event->GetEventID() : -1},
                      {"aborted", event ? Json(event->IsAborted()) : Json(nullptr)}});
    }
private:
    std::unique_ptr<G4UserEventAction> delegate_;
};

class ObservedRun final : public G4UserRunAction {
public:
    explicit ObservedRun(std::unique_ptr<G4UserRunAction> delegate) : delegate_(std::move(delegate)) { SetMaster(delegate_->IsMaster()); }
    void SetMaster(G4bool value = true) override { G4UserRunAction::SetMaster(value); delegate_->SetMaster(value); }
    G4Run* GenerateRun() override { return delegate_->GenerateRun(); }
    void BeginOfRunAction(const G4Run* run) override {
        active->Note({{"kind", "run_begin_observed"}, {"run", run->GetRunID()}, {"planned", run->GetNumberOfEventToBeProcessed()}});
        delegate_->BeginOfRunAction(run);
    }
    void EndOfRunAction(const G4Run* run) override {
        delegate_->EndOfRunAction(run);
        active->Note({{"kind", "run_end_observed"}, {"run", run->GetRunID()}, {"planned", run->GetNumberOfEventToBeProcessed()},
                      {"geant4_run_processed", run->GetNumberOfEvent()}});
    }
private:
    std::unique_ptr<G4UserRunAction> delegate_;
};

class ObservedActions final : public G4VUserActionInitialization {
public:
    explicit ObservedActions(std::unique_ptr<ActionInitialization> delegate) : delegate_(std::move(delegate)) {}
    void BuildForMaster() const override { delegate_->BuildForMaster(); WrapRun(); active->Note({{"kind", "master_actions_built"}}); }
    void Build() const override {
        active->Note({{"kind", "action_build_enter"}});
        delegate_->Build();
        auto* manager = G4RunManager::GetRunManager();
        auto* primary = const_cast<PrimaryGeneratorAction*>(dynamic_cast<const PrimaryGeneratorAction*>(manager->GetUserPrimaryGeneratorAction()));
        auto* event = const_cast<G4UserEventAction*>(manager->GetUserEventAction());
        Require(primary && event, "production primary/event actions absent");
        manager->SetUserAction(new ObservedPrimary(std::unique_ptr<PrimaryGeneratorAction>(primary)));
        manager->SetUserAction(new ObservedEvent(std::unique_ptr<G4UserEventAction>(event)));
        WrapRun();
        active->Note({{"kind", "action_build_complete"}});
    }
private:
    static void WrapRun() {
        auto* manager = G4RunManager::GetRunManager();
        auto* run = const_cast<G4UserRunAction*>(manager->GetUserRunAction());
        Require(run != nullptr, "production run action absent");
        manager->SetUserAction(new ObservedRun(std::unique_ptr<G4UserRunAction>(run)));
    }
    std::unique_ptr<ActionInitialization> delegate_;
};

Json Failure(OutputManager* output)
{
    if (!output || !output->HasOutputFailure()) return nullptr;
    const auto failure = output->GetOutputFailure();
    return {{"stage", failure.stage}, {"message", failure.message}, {"thread_id", failure.threadId}, {"run_id", failure.runId}};
}

void CheckFailure(SimulationManager& sim)
{
    if (sim.GetOutputManager()->HasOutputFailure()) {
        const auto f = sim.GetOutputManager()->GetOutputFailure();
        throw std::runtime_error("latched " + f.stage + ": " + f.message);
    }
}

void Register(ScoringManager& scoring, const Options& o)
{
    if (o.mode == "legacy-clone") { scoring.RegisterScorer(std::make_unique<Counter>("lifecycle_probe", -1)); return; }
    scoring.RegisterScorerFactory("lifecycle_probe", o.mode == "register-empty" ? nullptr : &Factory);
    ScorerSettings settings;
    settings.parameters = {{"faultthread", o.faultThread}, {"delayms", o.delayMs}, {"gate_timeout_ms", o.gateTimeoutMs},
        {"worker_failure", o.mode == "worker-throw" || o.mode == "worker-delayed-throw" ? 1.0 : 0.0},
        {"delay_enabled", o.mode == "worker-delayed-throw" ? 1.0 : 0.0},
        {"nonstd", o.exception == "nonstd" || o.mode == "register-throw-nonstd" ? 1.0 : 0.0},
        {"registration_failure", o.mode == "register-throw-std" || o.mode == "register-throw-nonstd" ? 1.0 : 0.0},
        {"return_null", o.mode == "register-null" ? 1.0 : 0.0}, {"wrong_name", o.mode == "register-wrong-name" ? 1.0 : 0.0}};
    const ScorerDescription description("lifecycle_probe", o.mode == "register-unknown" ? "unknown_lifecycle_type" : "lifecycle_probe", true, settings);
    scoring.RegisterScorer(description);
    if (o.mode == "register-duplicate") scoring.RegisterScorer(description);
}

void VerifyNormal(State& state, const Options& o, const RunSummary& summary)
{
    std::lock_guard<std::mutex> lock(state.mutex);
    const auto& runs = summary.GetRuns();
    Require(runs.size() == 2, "normal probe did not complete two real runs");
    for (std::size_t i = 0; i < runs.size(); ++i) {
        Require(runs[i].plannedEvents == o.events[i] && runs[i].completedEvents == o.events[i], "normal planned/completed mismatch");
        auto ids = state.scorerEvents[runs[i].runId];
        std::sort(ids.begin(), ids.end());
        Require(ids.size() == static_cast<std::size_t>(o.events[i]), "scorer lifecycle missing or duplicate events");
        for (int id = 0; id < o.events[i]; ++id) Require(ids[id] == id, "scorer event set differs from real run");
    }
}

int Execute(const Options& o, const fs::path& binary)
{
    const auto probeHash = input_provenance::HashFile(o.probeSource.u8string()).sha256;
    const std::string compiledProbe = G4USIM_SCORING_LIFECYCLE_PROBE_SHA256;
    Require(compiledProbe.size() == 64 && compiledProbe == probeHash, "probe source/build SHA unavailable or mismatched; primary must embed G4USIM_SCORING_LIFECYCLE_PROBE_SHA256");
    const auto binaryHash = input_provenance::HashFile(binary.u8string()).sha256;
    const auto configHash = input_provenance::HashFile(o.config.u8string()).sha256;
    fs::create_directories(o.output);
    if (!o.runFrom.empty()) fs::current_path(o.runFrom);
    State state(o); active = &state;
    SimulationManager sim; // destroyed before State; instance destructors retain a valid observer
    std::unique_ptr<G4RunManager> manager;
    Json report = {{"schema", "scoring_lifecycle_probe_v1"}, {"entrypoint", o.sequential ? "probe_realSequential" : "probe_MT"},
        {"not_production_CLI_coverage", true}, {"mode", o.mode}, {"startup", o.startup},
        {"parameters", {{"workers", o.workers}, {"event_modulo_requested", o.eventModulo}, {"fault_thread", o.faultThread}, {"delay_ms", o.delayMs},
                        {"gate_timeout_ms", o.gateTimeoutMs}, {"exception", o.exception}, {"events", o.events}, {"seed", o.seed}}},
        {"identity", {{"binary_path", binary.u8string()}, {"binary_sha256_before", binaryHash}, {"source_fingerprint", G4USIM_SOURCE_FINGERPRINT},
                      {"probe_source_path", o.probeSource.u8string()}, {"probe_source_sha256", probeHash}, {"compiled_probe_sha256", compiledProbe},
                      {"geant4_version_number", G4VERSION_NUMBER}, {"compiler_id", G4USIM_COMPILER_ID}, {"compiler_version", G4USIM_COMPILER_VERSION},
                      {"configuration", G4USIM_BUILD_CONFIGURATION}, {"config_path", o.config.u8string()}, {"config_sha256", configHash}}}};
    const std::vector<std::string> commands = {o.startup == "explicit" ? "Initialize_with_MT_fake_if_MT" : "base_kernel_Initialize_without_MT_fake",
        "BeamOn_run_0", "probe_marker_after_run_0", "BeamOn_run_1", "probe_marker_after_run_1"};
    Json commandRows = Json::array();
    for (const auto& command : commands) commandRows.push_back({{"command", command}, {"status", "not_started"}});
    int code = 0, failedCommand = -1;
    bool finalizeCalled = false, finalizeResult = false;
    std::string error;
    try {
        SimulationCommandLineOverrides overrides;
        overrides.mainConfig = o.config.u8string(); overrides.outputDir = o.output.u8string(); overrides.numThreads = o.workers;
        overrides.seed = o.seed; overrides.interactive = false; overrides.dryRun = false;
        sim.SetCommandLineOverrides(overrides);
        sim.Configure(); sim.BeginRuntimeTracking(); sim.Initialize();
        Require(!sim.GetContext().HasMacroFile(), "probe never executes preset INI macro; use a frozen probe config without it");
        Require(sim.GetScoringManager()->IsEnabled(), "probe requires scoring enabled in actual config");
        Register(*sim.GetScoringManager(), o);
        CLHEP::HepRandom::setTheSeed(static_cast<long>(sim.GetContext().GetSeed()));
        manager = CreateSimulationRunManager(sim.GetOutputManager(), o.workers, o.sequential);
        report["identity"]["runmanager_cpp_type"] = typeid(*manager).name();
        report["identity"]["runmanager_kind"] = static_cast<int>(manager->GetRunManagerType());
        Require((manager->GetRunManagerType() == G4RunManager::sequentialRM) == o.sequential, "requested runmanager kind unavailable");
#ifdef G4MULTITHREADED
        if (!o.sequential) {
            auto* mt = dynamic_cast<G4MTRunManager*>(manager.get());
            Require(mt != nullptr, "MT request did not create a real MT manager");
            mt->SetEventModulo(o.eventModulo);
            report["parameters"]["event_modulo_public_getter"] = mt->GetEventModulo();
            Require(mt->GetEventModulo() == o.eventModulo, "SetEventModulo readback mismatch");
        } else report["parameters"]["event_modulo_public_getter"] = nullptr;
#else
        Require(o.sequential, "MT probe unavailable in this Geant4 build");
        report["parameters"]["event_modulo_public_getter"] = nullptr;
#endif
        G4ScoringManager::GetScoringManager();
        auto detector = sim.CreateDetectorConstruction();
        detector->SetSensitiveDetectorFactory(sim.CreateSensitiveDetectorFactory());
        detector->SetGeometryPostBuildCallback(sim.CreateGeometryPostBuildCallback());
        manager->SetUserInitialization(detector.release());
        auto physics = sim.CreatePhysicsList(); manager->SetUserInitialization(physics.release());
        sim.InitializeSourceAfterPhysicsListRegistered();
        manager->SetUserInitialization(new ObservedActions(sim.CreateActionInitialization()));
        for (const auto& command : sim.GetScoringMeshCommands())
            Require(G4UImanager::GetUIpointer()->ApplyCommand(command) == 0, "configured mesh command rejected");
        sim.ValidateParallelWorldDependencies();
        for (std::size_t i = 0; i < commands.size(); ++i) {
            failedCommand = static_cast<int>(i);
            commandRows[i]["status"] = "started";
            state.Note({{"kind", "probe_command_start"}, {"index", i}, {"command", commands[i]}});
            if (i == 0) {
                if (o.startup == "explicit") manager->Initialize();
                else manager->G4RunManager::Initialize(); // kernel only, not MT Initialize's fake BeamOn(0)
            } else if (i == 1 || i == 3) {
                sim.ValidateBiasingProcessTargets();
                sim.ValidateScoringVolumeConfigsBeforeRun(); sim.ValidateParallelWorldForRun();
                manager->BeamOn(o.events[i == 1 ? 0 : 1]);
            }
            const auto latched = Failure(sim.GetOutputManager());
            const bool controlledDirectAdmission = i == 0 && o.startup == "direct-beamon" &&
                !latched.is_null() && latched["stage"] == "scoring_factory_build";
            if (controlledDirectAdmission) {
                // Test ONLY the actual production DoEventLoop admission adapter.
                // Keep the original latch intact. Production CLI is not allowed
                // to continue like this; the very first BeamOn is checked below.
                report["controlled_direct_admission"] = {{"enabled", true}, {"first_failure", latched},
                    {"not_production_CLI_behavior", true}, {"failure_latch_cleared", false}};
                state.Note({{"kind", "controlled_direct_admission_with_startup_failure"}, {"stage", latched["stage"]}});
            } else CheckFailure(sim); // explicit fake failure and all positive BeamOn failures stop immediately
            commandRows[i]["status"] = "completed";
            state.Note({{"kind", "probe_command_complete"}, {"index", i}});
            failedCommand = -1;
        }
        Require(o.mode == "normal", "requested rejection mode unexpectedly reached the end without failure");
        VerifyNormal(state, o, sim.GetOutputManager()->GetRunSummary());
        Require(!state.observationError.load(), "observer failed to retain complete facts");
    } catch (const std::exception& e) { error = e.what(); code = 1; }
    catch (...) { error = "non-standard exception escaped probe main boundary"; code = 2; }
    if (failedCommand >= 0) commandRows[failedCommand]["status"] = "failed";
    if (code && sim.GetOutputManager() && !sim.GetOutputManager()->HasOutputFailure())
        sim.GetOutputManager()->RecordStartupFailure("probe_exception", error);
    report["first_failure_before_finalize"] = Failure(sim.GetOutputManager());
    try {
        finalizeCalled = true;
        finalizeResult = sim.FinalizeRunSummary(code ? "failed" : "completed", code, code ? "failed" : "completed",
            code ? o.probeSource.u8string() : "", 0, failedCommand >= 0 ? commands[failedCommand] : "", 0, false);
        if (!finalizeResult) code = 1;
    } catch (const std::exception& e) { code = 2; report["finalize_exception"] = e.what(); }
    catch (...) { code = 2; report["finalize_exception"] = "non-standard"; }
    report["first_failure_after_finalize"] = Failure(sim.GetOutputManager());
    Json runs = Json::array(); std::int64_t processed = 0;
    if (sim.GetOutputManager()) for (const auto& run : sim.GetOutputManager()->GetRunSummary().GetRuns()) {
        runs.push_back({{"run_id", run.runId}, {"planned", run.plannedEvents}, {"processed", run.completedEvents}});
        processed += run.completedEvents;
    }
    manager.reset(); // finish native worker shutdown while the observation sink is alive
    if (state.observationError.load() || state.gateTimedOut.load()) code = 2;
    report["runs_from_production_summary"] = std::move(runs);
    report["commands"] = std::move(commandRows);
    report["event_observations"] = {{"primary_generator_calls", state.primaryCalls.load()}, {"primary_vertices", state.primaryVertices.load()},
        {"event_begin_callbacks", state.eventBegin.load()}, {"event_end_callbacks", state.eventEnd.load()}, {"aborted_at_event_end", state.aborted.load()},
        {"processed_from_production_run_summary", processed}, {"dispatched", nullptr},
        {"dispatched_reason", "receipt does not infer global dispatch; wrapper must independently inspect raw RunAdmissionRejected lines and source"},
        {"admission_evidence_streams", "original stdout/stderr, preserved separately by native wrapper; no redirection or filtering in probe"}};
    report["finalization"] = {{"producer", "SimulationManager::FinalizeRunSummary"}, {"calls", finalizeCalled ? 1 : 0}, {"returned_success", finalizeResult}};
    const auto summary = o.output / "run_summary.txt";
    report["finalization"]["summary_path"] = summary.u8string();
    report["finalization"]["summary_sha256"] = fs::is_regular_file(summary) ? Json(input_provenance::HashFile(summary.u8string()).sha256) : Json(nullptr);
    report["identity"]["binary_sha256_after"] = input_provenance::HashFile(binary.u8string()).sha256;
    report["identity"]["probe_source_sha256_after"] = input_provenance::HashFile(o.probeSource.u8string()).sha256;
    if (report["identity"]["binary_sha256_after"] != binaryHash || report["identity"]["probe_source_sha256_after"] != probeHash) code = 2;
    report["observations_complete"] = !state.observationError.load();
    report["delay_gate_timed_out"] = state.gateTimedOut.load();
    report["runmanager_destroyed"] = true;
    report["master_manager_lifetime"] = "SimulationManager still alive when receipt written";
    report["error"] = error; report["exit_code"] = code;
    report["verdict"] = "raw_observation_only; external negative-case judge required";
    { std::lock_guard<std::mutex> lock(state.mutex); report["trace"] = state.trace; }
    std::ofstream stream(o.output / "scoring-lifecycle-receipt.json", std::ios::binary);
    Require(static_cast<bool>(stream), "cannot create lifecycle receipt");
    stream << report.dump(2) << '\n'; stream.close();
    Require(static_cast<bool>(stream), "cannot finish lifecycle receipt");
    return code;
}
} // namespace

int main(int argc, char** argv)
{
    try {
        const auto options = Parse(argc, argv);
        if (options.help) {
            std::cout << "scoringLifecycleCheck (probe CLI, not production main):\n"
                " --config FILE --output NEW_DIR --probe-source FILE [--run-from DIR]\n"
                " --mode normal|worker-throw|worker-delayed-throw|legacy-clone|register-{empty,null,unknown,wrong-name,duplicate,throw-std,throw-nonstd}\n"
                " --workers 1|2|4 [--sequential] --startup explicit|direct-beamon\n"
                " --event-modulo N --events 12,8 --seed N --fault-thread N|last\n"
                " --exception std|nonstd --delay-ms N --gate-timeout-ms N\n"
                " --identity (standalone build identity JSON; no configuration or kernel initialization)\n"
                "Rejection modes exit nonzero with actual production failure summary, never synthetic PASS.\n";
            return 0;
        }
        const auto binary = fs::absolute(fs::u8path(argv[0]));
        Require(fs::is_regular_file(binary), "invoke the probe using its actual executable path");
        if (options.identity) {
            const Json identity = {{"schema", "scoring_lifecycle_identity_v1"}, {"source_fingerprint", G4USIM_SOURCE_FINGERPRINT},
                {"compiled_probe_sha256", G4USIM_SCORING_LIFECYCLE_PROBE_SHA256}, {"compiler_id", G4USIM_COMPILER_ID},
                {"compiler_version", G4USIM_COMPILER_VERSION}, {"configuration", G4USIM_BUILD_CONFIGURATION},
                {"build_git_commit", G4USIM_GIT_COMMIT}, {"build_git_source_state", G4USIM_GIT_SOURCE_STATE},
                {"geant4_version_number", G4VERSION_NUMBER}, {"binary_path", binary.u8string()},
                {"binary_sha256", input_provenance::HashFile(binary.u8string()).sha256}, {"execution_performed", false}};
            std::cout << identity.dump(2) << '\n';
            return 0;
        }
        return Execute(options, binary);
    } catch (const std::exception& e) { std::cerr << "scoringLifecycleCheck: " << e.what() << '\n'; return 2; }
    catch (...) { std::cerr << "scoringLifecycleCheck: unhandled non-standard error\n"; return 2; }
}
