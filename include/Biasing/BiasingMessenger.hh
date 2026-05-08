#pragma once

#include "G4UImessenger.hh"
#include "globals.hh"

class BiasingManager;
class G4UIcmdWithABool;
class G4UIcmdWithAString;
class G4UIcmdWithoutParameter;
class G4UIdirectory;
class G4UIcommand;

class BiasingMessenger : public G4UImessenger {
public:
    explicit BiasingMessenger(BiasingManager* manager);
    ~BiasingMessenger() override;

    void SetNewValue(G4UIcommand* command, G4String newValue) override;

private:
    void EnsureManager(const char* commandName) const;
    void NotifyChanged() const;

    BiasingManager* manager_ = nullptr; // not owned

    G4UIdirectory* biasingDir_ = nullptr;
    G4UIdirectory* xsDir_ = nullptr;

    G4UIcmdWithABool* enableCmd_ = nullptr;
    G4UIcmdWithAString* addParticleCmd_ = nullptr;
    G4UIcmdWithAString* addProcessCmd_ = nullptr;
    G4UIcmdWithAString* addProcessForParticleCmd_ = nullptr;
    G4UIcmdWithAString* setFactorCmd_ = nullptr;
    G4UIcmdWithAString* onlyPrimaryCmd_ = nullptr;
    G4UIcmdWithAString* applyToSecondariesCmd_ = nullptr;
    G4UIcmdWithAString* setMinWeightCmd_ = nullptr;
    G4UIcmdWithAString* setMaxInteractionsCmd_ = nullptr;
    G4UIcmdWithAString* addVolumeCmd_ = nullptr;
    G4UIcmdWithAString* addVolumeForParticleCmd_ = nullptr;
    G4UIcmdWithoutParameter* validateCmd_ = nullptr;
    G4UIcmdWithoutParameter* printCmd_ = nullptr;
    G4UIcmdWithoutParameter* clearCmd_ = nullptr;
};
