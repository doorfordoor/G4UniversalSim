#pragma once

#include "G4UImessenger.hh"

class G4UIcmdWithAString;
class G4UIcmdWithoutParameter;
class G4UIcommand;
class G4UIdirectory;
class SourceManager;

class SourceMessenger : public G4UImessenger {
public:
    explicit SourceMessenger(SourceManager* manager);
    ~SourceMessenger() override;

    void SetNewValue(G4UIcommand* command, G4String newValue) override;

private:
    SourceManager* manager_ = nullptr; // not owned

    G4UIdirectory* sourceDir_ = nullptr;
    G4UIcmdWithAString* presetCmd_ = nullptr;
    G4UIcmdWithAString* particleCmd_ = nullptr;
    G4UIcmdWithAString* energyCmd_ = nullptr;
    G4UIcmdWithAString* pointCmd_ = nullptr;
    G4UIcmdWithAString* directionCmd_ = nullptr;
    G4UIcmdWithoutParameter* isotropicCmd_ = nullptr;
    G4UIcmdWithAString* planeBeamCmd_ = nullptr;
    G4UIcmdWithoutParameter* printCmd_ = nullptr;
    G4UIcmdWithoutParameter* resetCmd_ = nullptr;
};
