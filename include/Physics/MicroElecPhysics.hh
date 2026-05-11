#pragma once

#include "G4VPhysicsConstructor.hh"
#include "G4SystemOfUnits.hh"
#include "globals.hh"

class MicroElecPhysics : public G4VPhysicsConstructor {
public:
    explicit MicroElecPhysics(G4int verbose = 1,
                              const G4String& regionName = "SV",
                              const G4String& name = "MicroElecPhysics");
    ~MicroElecPhysics() override;

    void ConstructParticle() override;
    void ConstructProcess() override;

    void SetRegionName(const G4String& regionName);
    const G4String& GetRegionName() const;

    void SetVerboseLevel(G4int verbose);
    G4int GetVerboseLevel() const;

    void EnableElectronCapture(bool enable);
    bool IsElectronCaptureEnabled() const;

    void SetElectronCaptureThreshold(G4double energy);
    G4double GetElectronCaptureThreshold() const;

private:
    void ConfigureAtomicDeexcitation() const;
    void RegisterElectronCaptureProcess() const;
    void WarnIfRegionMissing() const;

    G4String regionName_;
    G4int verboseLevel_ = 1;
    G4bool electronCaptureEnabled_ = false;
    G4double electronCaptureThreshold_ = 16.7 * CLHEP::eV;
};
