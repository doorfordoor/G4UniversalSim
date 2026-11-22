#pragma once

#include "Output/OutputRecord.hh"

#include <unordered_map>
#include <unordered_set>
#include <vector>

class G4Event;
class G4Step;
class G4Track;
class G4VProcess;

namespace activation_observation {
double ValidateRun();
class Event {
public:
    void ObserveStep(const G4Step& step, int runID, int eventID, int schemaVersion);
    void ObserveStackedTrack(const G4Track& track, bool extended);
    void AppendCompletedEventPrimaries(const G4Event& event, int runID);
    void Clear();
    void ClearPendingBirths() noexcept { pendingBirths_.clear(); }
    const std::vector<ActivationObservationRecord>& Records() const { return records_; }

private:
    struct BirthLink {
        std::size_t rowIndex;
        const G4VProcess* creator;
    };

    std::vector<ActivationObservationRecord> records_;
    std::unordered_set<int> decayedTracks_;
    std::unordered_map<const G4Track*, BirthLink> pendingBirths_;
    std::unordered_map<int, BirthLink> stackedBirths_;
    std::unordered_map<int, std::size_t> nuclearLineage_;
};
}
