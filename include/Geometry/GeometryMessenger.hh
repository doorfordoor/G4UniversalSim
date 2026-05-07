#pragma once

#include "G4UImessenger.hh"

class G4UIcmdWithABool;
class G4UIcmdWithAString;
class G4UIcmdWithoutParameter;
class G4UIdirectory;
class G4UIcommand;
class GeometryManager;

class GeometryMessenger : public G4UImessenger {
public:
    explicit GeometryMessenger(GeometryManager* manager);
    ~GeometryMessenger() override;

    void SetNewValue(G4UIcommand* command, G4String newValue) override;

private:
    void EnsureManager(const char* commandName) const;
    void PrintChangedMessage() const;
    void PrintTreeModifiedMessage() const;
    void ReportCommandError(const char* commandName, const G4String& value, const std::exception& error) const;

    GeometryManager* manager_ = nullptr;
    G4UIdirectory* directory_ = nullptr;
    G4UIcmdWithAString* setTemplateCmd_ = nullptr;
    G4UIcmdWithAString* loadConfigCmd_ = nullptr;
    G4UIcmdWithABool* checkOverlapsCmd_ = nullptr;
    G4UIcmdWithAString* setDefaultWorldMaterialCmd_ = nullptr;
    G4UIcmdWithAString* addBoxCmd_ = nullptr;
    G4UIcmdWithAString* addTubsCmd_ = nullptr;
    G4UIcmdWithAString* addVolumeCmd_ = nullptr;
    G4UIcmdWithAString* removeUserVolumeCmd_ = nullptr;
    G4UIcmdWithoutParameter* printCmd_ = nullptr;
    G4UIcmdWithoutParameter* printTreeCmd_ = nullptr;
    G4UIcmdWithoutParameter* clearCmd_ = nullptr;
    G4UIcmdWithoutParameter* clearUserVolumesCmd_ = nullptr;
    G4UIcmdWithoutParameter* listUserVolumesCmd_ = nullptr;
    G4UIcmdWithABool* preserveUserVolumesOnLoadCmd_ = nullptr;
    G4UIcmdWithoutParameter* markModifiedCmd_ = nullptr;
};
