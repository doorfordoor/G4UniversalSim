#include "Physics/ElectronCapture.hh"

#include "G4Electron.hh"
#include "G4Exception.hh"
#include "G4LogicalVolume.hh"
#include "G4ParticleChange.hh"
#include "G4ParticleDefinition.hh"
#include "G4Region.hh"
#include "G4Step.hh"
#include "G4TouchableHandle.hh"
#include "G4Track.hh"
#include "G4VPhysicalVolume.hh"
#include "G4SystemOfUnits.hh"

#include <cfloat>
#include <stdexcept>

ElectronCapture::ElectronCapture(const G4String& processName,
                                 G4double threshold,
                                 const G4String& regionName)
    : G4VDiscreteProcess(processName),
      threshold_(threshold),
      regionName_(regionName)
{
    if (threshold_ <= 0.0) {
        throw std::runtime_error("ElectronCapture requires threshold > 0");
    }
}

ElectronCapture::~ElectronCapture() = default;

G4bool ElectronCapture::IsApplicable(const G4ParticleDefinition& particle)
{
    return &particle == G4Electron::ElectronDefinition();
}

G4double ElectronCapture::PostStepGetPhysicalInteractionLength(
    const G4Track& track,
    G4double,
    G4ForceCondition* condition)
{
    return GetMeanFreePath(track, 0.0, condition);
}

G4double ElectronCapture::GetMeanFreePath(
    const G4Track& track,
    G4double,
    G4ForceCondition* condition)
{
    if (condition) *condition = NotForced;

    const auto* definition = track.GetParticleDefinition();
    if (definition != G4Electron::ElectronDefinition()) {
        return DBL_MAX;
    }
    if (!IsInTargetRegion(track)) {
        return DBL_MAX;
    }
    if (track.GetKineticEnergy() > threshold_) {
        return DBL_MAX;
    }

    if (condition) *condition = Forced;
    return 0.0;
}

G4VParticleChange* ElectronCapture::PostStepDoIt(
    const G4Track& track,
    const G4Step&)
{
    aParticleChange.Initialize(track);
    aParticleChange.ProposeLocalEnergyDeposit(track.GetKineticEnergy());
    aParticleChange.ProposeEnergy(0.0);
    aParticleChange.ProposeTrackStatus(fStopAndKill);
    return &aParticleChange;
}

void ElectronCapture::SetThreshold(G4double threshold)
{
    if (threshold <= 0.0) {
        throw std::runtime_error("ElectronCapture::SetThreshold requires threshold > 0");
    }
    threshold_ = threshold;
}

G4double ElectronCapture::GetThreshold() const
{
    return threshold_;
}

void ElectronCapture::SetRegionName(const G4String& regionName)
{
    regionName_ = regionName;
}

const G4String& ElectronCapture::GetRegionName() const
{
    return regionName_;
}

bool ElectronCapture::IsInTargetRegion(const G4Track& track) const
{
    if (regionName_.empty()) {
        return true;
    }

    const auto touchable = track.GetTouchableHandle();
    if (!touchable) {
        return false;
    }

    const auto* physical = touchable->GetVolume();
    if (!physical) {
        return false;
    }

    const auto* logical = physical->GetLogicalVolume();
    if (!logical) {
        return false;
    }

    const auto* region = logical->GetRegion();
    return region && region->GetName() == regionName_;
}
