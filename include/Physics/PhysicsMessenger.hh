#pragma once

#include "G4UImessenger.hh"

class G4UIcmdWithABool;
class G4UIcmdWithAString;
class G4UIcmdWithAnInteger;
class G4UIcmdWithoutParameter;
class G4UIcommand;
class G4UIdirectory;
class PhysicsManager;

class PhysicsMessenger : public G4UImessenger {
public:
    explicit PhysicsMessenger(PhysicsManager* manager);
    ~PhysicsMessenger() override;

    void SetNewValue(G4UIcommand* command, G4String newValue) override;

private:
    PhysicsManager* manager_ = nullptr; // not owned

    G4UIdirectory* physicsDir_ = nullptr;
    G4UIcmdWithAString* setEMCmd_ = nullptr;
    G4UIcmdWithAString* setReferenceListCmd_ = nullptr;
    G4UIcmdWithoutParameter* clearReferenceListCmd_ = nullptr;
    G4UIcmdWithAString* setBaseReferenceListCmd_ = nullptr;
    G4UIcmdWithAString* addModuleCmd_ = nullptr;
    G4UIcmdWithAString* removeModuleCmd_ = nullptr;
    G4UIcmdWithoutParameter* clearModulesCmd_ = nullptr;
    G4UIcmdWithAString* addHadronicCmd_ = nullptr;
    G4UIcmdWithAString* addOtherCmd_ = nullptr;
    G4UIcmdWithAString* addExtraModuleCmd_ = nullptr;
    G4UIcmdWithAString* removeExtraModuleCmd_ = nullptr;
    G4UIcmdWithoutParameter* clearExtraModulesCmd_ = nullptr;
    G4UIcmdWithAString* setDefaultCutCmd_ = nullptr;
    G4UIcmdWithAString* setCutCmd_ = nullptr;
    G4UIcmdWithAString* setRegionCutCmd_ = nullptr;
    G4UIcmdWithABool* enableBiasingCmd_ = nullptr;
    G4UIcmdWithAnInteger* verboseCmd_ = nullptr;
    G4UIcmdWithoutParameter* printCmd_ = nullptr;
    G4UIcmdWithoutParameter* listAvailableReferencesCmd_ = nullptr;
    G4UIcmdWithoutParameter* listAvailableEMReferencesCmd_ = nullptr;
};
