#include "Actions/RunManagerFactory.hh"
#include "Output/OutputManager.hh"
#include "G4RunManager.hh"
#include "G4Threading.hh"
#include "G4ios.hh"
#include <stdexcept>
#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
#include "G4UserWorkerThreadInitialization.hh"
#include "G4WorkerRunManager.hh"
#endif

namespace {
void ReportRejectedLoop(const OutputManager& output, G4int planned, const char* role)
{
    const auto failure = output.GetOutputFailure();
    G4cout << "[RunAdmissionRejected] role=" << role
           << " thread=" << G4Threading::G4GetThreadId()
           << " planned=" << planned << " loop_dispatched=0 stage=" << failure.stage << G4endl;
}
class GuardedSequentialRunManager final : public G4RunManager {
public:
    explicit GuardedSequentialRunManager(const OutputManager* output) : output_(output) {}
    void DoEventLoop(G4int events, const char* macro = nullptr, G4int selected = -1) override
    {
        if (output_ && output_->HasOutputFailure()) {
            ReportRejectedLoop(*output_, events, "sequential");
            runAborted = true;
            // Preserve the planned count and fakeRun; initialize and terminate
            // the ordinary zero-iteration loop without allocating an event.
            G4RunManager::DoEventLoop(0, macro, selected);
            return;
        }
        G4RunManager::DoEventLoop(events, macro, selected);
    }
private:
    const OutputManager* output_;
};
#ifdef G4MULTITHREADED
class GuardedWorkerRunManager final : public G4WorkerRunManager {
public:
    explicit GuardedWorkerRunManager(const OutputManager* output) : output_(output) {}
    void DoEventLoop(G4int events, const char* macro = nullptr, G4int selected = -1) override
    {
        // Geant4 11.3.2 has passed ThisWorkerReady after all Build calls,
        // then reset runAborted after BeginRun. Check before GenerateEvent
        // allocates an event/seeds. BeamOn still calls RunTermination and its
        // worker completion barrier; never bypass those synchronization points.
        if (output_ && output_->HasOutputFailure()) {
            ReportRejectedLoop(*output_, events, "worker");
            InitializeEventLoop(events, macro, selected);
            eventLoopOnGoing = false;
            runAborted = true;
            TerminateEventLoop();
            return;
        }
        G4WorkerRunManager::DoEventLoop(events, macro, selected);
    }
private:
    const OutputManager* output_;
};
class GuardedWorkerInitialization final : public G4UserWorkerThreadInitialization {
public:
    explicit GuardedWorkerInitialization(const OutputManager* output) : output_(output) {}
    G4WorkerRunManager* CreateWorkerRunManager() const override
    {
        return new GuardedWorkerRunManager(output_);
    }
private:
    const OutputManager* output_;
};
#endif
} // namespace

std::unique_ptr<G4RunManager> CreateSimulationRunManager(
    const OutputManager* output, int threads, bool sequential)
{
    if (!output) throw std::invalid_argument("Run manager requires a shared failure registry");
    if (threads < 1) throw std::invalid_argument("Run manager thread count must be positive");
#ifdef G4MULTITHREADED
    if (!sequential) {
        auto manager = std::make_unique<G4MTRunManager>();
        manager->SetNumberOfThreads(threads);
        manager->SetUserInitialization(new GuardedWorkerInitialization(output));
        return manager;
    }
#else
    (void)threads;
    (void)sequential;
#endif
    return std::make_unique<GuardedSequentialRunManager>(output);
}
