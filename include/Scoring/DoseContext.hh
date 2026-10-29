#pragma once

#include "Output/OutputRecord.hh"

#include "G4LogicalVolume.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh"
#include "G4TouchableHandle.hh"
#include "G4VPhysicalVolume.hh"
#include "G4VSolid.hh"

#include <string>

// Transport-only metadata. Dose is scored per physical touchable instance;
// GetMass(true,false) removes daughter displacement without adding their mass.
inline void PopulateDoseContext(const G4Step* step, HitRecord& record)
{
    if (!step || !step->GetPreStepPoint()) return;
    const auto& touchable = step->GetPreStepPoint()->GetTouchableHandle();
    if (!touchable || !touchable->GetVolume()) return;
    auto* logical = touchable->GetVolume()->GetLogicalVolume();
    if (!logical) return;
    // Pass the step material so parameterised copies with their own material
    // get their own mass (same as the logical volume's material otherwise).
    record.doseMass = logical->GetMass(true, false, step->GetPreStepPoint()->GetMaterial());
    // MVP fluence supports sensitive solids without daughter volumes only.
    // A mother volume's cubic volume includes its daughters and would give a
    // wrong track-length normalization if silently used here.
    if (logical->GetNoDaughters() == 0 && logical->GetSolid()) {
        record.fluenceVolume = logical->GetSolid()->GetCubicVolume();
    }
    if (const auto* post = step->GetPostStepPoint()) {
        record.meanKineticEnergy =
            0.5 * (step->GetPreStepPoint()->GetKineticEnergy() + post->GetKineticEnergy());
    }
    const int depth = touchable->GetHistoryDepth();
    for (int i = depth; i >= 0; --i) {
        const auto* volume = touchable->GetVolume(i);
        if (!volume) continue;
        record.doseVolumePath += "/" + std::string(volume->GetName()) +
                                 "#" + std::to_string(touchable->GetCopyNumber(i));
    }
}
