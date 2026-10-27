#pragma once

// Best-effort process-wide telemetry. No random draws, output-file registration,
// or exceptions are allowed to affect the simulation through this interface.
namespace RunProgress {
void Begin(int runId, int plannedEvents) noexcept;
void EventCompleted(int runId, bool eventAborted) noexcept;
void End(int runId, int plannedEvents, int completedEvents, bool failed) noexcept;
}
