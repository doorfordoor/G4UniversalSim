#pragma once

#include "G4VDiscreteProcess.hh"
#include "G4SystemOfUnits.hh"
#include "globals.hh"

class G4ParticleDefinition;
class G4Step;
class G4Track;
class G4VParticleChange;

class ElectronCapture : public G4VDiscreteProcess {
public:
    explicit ElectronCapture(const G4String& processName = "eCapture",
                             G4double threshold = 16.7 * CLHEP::eV,
                             const G4String& regionName = "SV");
    ~ElectronCapture() override;

    G4bool IsApplicable(const G4ParticleDefinition& particle) override;

    G4double PostStepGetPhysicalInteractionLength(
        const G4Track& track,
        G4double previousStepSize,
        G4ForceCondition* condition) override;

    G4double GetMeanFreePath(
        const G4Track& track,
        G4double previousStepSize,
        G4ForceCondition* condition) override;

    G4VParticleChange* PostStepDoIt(
        const G4Track& track,
        const G4Step& step) override;

    void SetThreshold(G4double threshold);
    G4double GetThreshold() const;

    void SetRegionName(const G4String& regionName);
    const G4String& GetRegionName() const;

private:
    bool IsInTargetRegion(const G4Track& track) const;

    G4double threshold_;
    G4String regionName_;
};
