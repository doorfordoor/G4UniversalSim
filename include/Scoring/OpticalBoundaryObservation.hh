#pragma once

#include "Output/OutputRecord.hh"

#include <optional>

class G4Step;

namespace optical_boundary {

// Read the current worker step without changing track or process state.
std::optional<OpticalBoundaryStepRecord> ObserveStep(const G4Step& step, int runID, int eventID);

}  // namespace optical_boundary
