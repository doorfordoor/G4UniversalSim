#pragma once

#include "Output/OutputManager.hh"
#include <utility>
#include <vector>

namespace runtime {

enum class PublicationOutcome { Clean, Failed };

// Publish already-collected evidence and final summary fields. A failed
// metadata write may correct the text summary; this is not a two-file commit.
PublicationOutcome PublishFinalRunEvidence(
    OutputManager& output, std::vector<OutputManager::ArtifactEvidence> artifacts);

enum class FinalizationAttemptResult { Completed, Failed, AlreadyAttempted };

// One process-level attempt; no destructor IO, no retries, no Manager state.
// The caller supplies its synchronous finalizer using its existing references.
class ProcessFinalizationAttempt {
public:
    ProcessFinalizationAttempt() = default;
    ProcessFinalizationAttempt(const ProcessFinalizationAttempt&) = delete;
    ProcessFinalizationAttempt& operator=(const ProcessFinalizationAttempt&) = delete;
    bool Started() const { return started_; }

    template<class Finalize>
    FinalizationAttemptResult Run(Finalize&& finalize) {
        if (started_) return FinalizationAttemptResult::AlreadyAttempted;
        started_ = true;
        return std::forward<Finalize>(finalize)()
            ? FinalizationAttemptResult::Completed : FinalizationAttemptResult::Failed;
    }
private:
    bool started_ = false;
};

} // namespace runtime
