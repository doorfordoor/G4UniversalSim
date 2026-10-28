#include "Actions/RunProgress.hh"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <iomanip>
#include <locale>
#include <mutex>
#include <sstream>

namespace {
using Clock = std::chrono::steady_clock;
constexpr long long intervalNs = 500000000;

struct State {
    std::mutex mutex;
    std::atomic<int> runId{-1};
    std::atomic<long long> completed{0};
    std::atomic<long long> nextEmissionNs{0};
    std::atomic<bool> eventAborted{false};
    int planned = 0;
    Clock::time_point started;
    // Process-wide emission counter; never reset across runs. Consumers use it
    // to reject duplicated or reordered lines when stdout is chunked or a
    // message from an earlier run arrives late.
    long long sequence = 0;
};

State& Shared()
{
    static State state;
    return state;
}

long long Nanoseconds(Clock::time_point now)
{
    return std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
}

// Called under the telemetry mutex. One CRT write keeps the complete line
// together, bypassing G4cout's per-worker prefix and buffering. GUI consumers
// must still tolerate unrelated stdout noise and arbitrary pipe chunking.
void Emit(State& state, int runId, const char* phase, long long completed, Clock::time_point now)
{
    const double elapsed = std::max(0.0, std::chrono::duration<double>(now - state.started).count());
    const double rate = elapsed > 0.0 ? completed / elapsed : 0.0;
    const long long sequence = ++state.sequence;
    std::ostringstream line;
    line.imbue(std::locale::classic());
    line << std::setprecision(10)
         << "[G4USimProgress] {\"schema\":\"g4usim_progress_v1\",\"run_id\":" << runId
         << ",\"sequence\":" << sequence
         << ",\"phase\":\"" << phase << "\",\"planned_events\":" << state.planned
         << ",\"completed_events\":" << completed << ",\"elapsed_s\":" << elapsed
         << ",\"rate_eps\":";
    if (rate > 0.0) line << rate;
    else line << "null";
    line << ",\"eta_s\":";
    if (phase[0] == 'r' && rate > 0.0 && state.planned > 0 && completed < state.planned) {
        line << (state.planned - completed) / rate;
    } else if (phase[0] == 'e' && state.planned > 0 && completed == state.planned) {
        line << 0;
    } else {
        line << "null";
    }
    line << "}\n";
    const auto text = line.str();
    std::fwrite(text.data(), 1, text.size(), stdout);
    std::fflush(stdout);
}
}

void RunProgress::Begin(int runId, int plannedEvents) noexcept
{
    try {
        auto& state = Shared();
        std::lock_guard<std::mutex> lock(state.mutex);
        state.runId.store(-1);
        state.completed.store(0);
        state.eventAborted.store(false);
        state.planned = plannedEvents;
        state.started = Clock::now();
        state.nextEmissionNs.store(Nanoseconds(state.started) + intervalNs);
        state.runId.store(runId);
        Emit(state, runId, "begin", 0, state.started);
    } catch (...) {
        // Telemetry is optional; even allocation/stream failures are isolated.
    }
}

void RunProgress::EventCompleted(int runId, bool eventAborted) noexcept
{
    try {
        auto& state = Shared();
        if (state.runId.load() != runId) return;
        // This is an EndOfEventAction count, not a count of valid physics
        // histories. Aborted events are included here, as in G4Run accounting.
        state.completed.fetch_add(1, std::memory_order_relaxed);
        if (eventAborted) state.eventAborted.store(true);
        const auto now = Clock::now();
        if (Nanoseconds(now) < state.nextEmissionNs.load(std::memory_order_relaxed)) return;
        std::unique_lock<std::mutex> lock(state.mutex, std::try_to_lock);
        if (!lock || state.runId.load() != runId ||
            Nanoseconds(now) < state.nextEmissionNs.load(std::memory_order_relaxed)) return;
        state.nextEmissionNs.store(Nanoseconds(now) + intervalNs, std::memory_order_relaxed);
        Emit(state, runId, "running", state.completed.load(std::memory_order_relaxed), now);
    } catch (...) {
    }
}

void RunProgress::End(int runId, int plannedEvents, int completedEvents, bool failed) noexcept
{
    try {
        auto& state = Shared();
        std::lock_guard<std::mutex> lock(state.mutex);
        if (state.runId.load() != runId) return;
        state.planned = plannedEvents;
        // G4Run's final merged count is authoritative, exactly as RecordRun.
        const bool aborted = failed || state.eventAborted.load() || completedEvents != plannedEvents;
        state.runId.store(-1);
        Emit(state, runId, aborted ? "aborted" : "end", completedEvents, Clock::now());
    } catch (...) {
    }
}
