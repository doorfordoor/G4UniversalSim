#pragma once

// Versioned controlled-session server (protocol g4usim-session-v1).
//
// The session keeps the existing G4 command-line session and batch entry points
// untouched: it is an opt-in stdio transport used by the GUI's next-round panel
// and by the F2 replay tests. All Geant4 work happens on the process main
// thread; a reader thread only parses frames and records cancel intent.
//
// Evidence rules:
//  * requested and resolved values are reported separately; a rejected request
//    never edits the source;
//  * manager acceptance is not kernel application: every response says which
//    evidence level was actually observed;
//  * per-run receipts bind the OutputManager artifacts registered for that run
//    id after they were closed, and are written outside the output root.

#include <cstdint>
#include <string>

class OutputManager;
class SimulationManager;
namespace runtime { class NativeExecutionPort; }

namespace SessionControl {

// Called by RunAction on the master thread. These hooks are no-ops unless a
// SessionServer is attached.
bool CancelRequested(int runId) noexcept;
void OnRunBegin(int runId, int plannedEvents);
void OnRunEnd(int runId, int plannedEvents, int completedEvents, long long abortedEvents,
              bool outputFailed, OutputManager* outputManager);

}  // namespace SessionControl

class SessionServer {
public:
    // `recordRoot` must be absolute and outside the configured output root; the
    // caller validates that before constructing the server.  When `replaySource`
    // is non-empty the server validates that session directory (snapshot and
    // manifest), restores the captured random engine state and repeats the
    // recorded accepted operations instead of serving a fresh session.
    SessionServer(SimulationManager& simulation, std::string recordRoot,
                  std::string replaySource = std::string());
    // Borrowed synchronous execution; must outlive this session.
    SessionServer(SimulationManager& simulation, runtime::NativeExecutionPort& execution,
                  std::string recordRoot, std::string replaySource = std::string());
    ~SessionServer();

    SessionServer(const SessionServer&) = delete;
    SessionServer& operator=(const SessionServer&) = delete;

    // Serves the session until shutdown, EOF or a terminal protocol failure.
    // Returns 0 for a clean session, non-zero otherwise.
    int Run();

    // Geant4 callback entry points (master thread only).
    void HandleRunBegin(int runId, int plannedEvents);
    void HandleRunEnd(int runId, int plannedEvents, int completedEvents, long long abortedEvents,
                      bool outputFailed, OutputManager* outputManager);

private:
    struct Impl;
    Impl* impl_ = nullptr;
    SimulationManager& simulation_;
    std::string recordRoot_;
    std::string replaySource_;
};
