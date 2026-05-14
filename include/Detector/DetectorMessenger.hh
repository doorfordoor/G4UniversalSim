#pragma once

#include "G4UImessenger.hh"

class DetectorConstruction;
class G4UIcmdWithABool;
class G4UIcmdWithAString;
class G4UIcmdWithAnInteger;
class G4UIcmdWithoutParameter;
class G4UIdirectory;
class G4UIcommand;

class DetectorMessenger : public G4UImessenger {
public:
    explicit DetectorMessenger(DetectorConstruction* detector);
    ~DetectorMessenger() override;

    void SetNewValue(G4UIcommand* command, G4String newValue) override;

private:
    void EnsureDetector(const char* commandName) const;
    void WarnIfWorldBuilt(const char* commandName) const;
    void ReportCommandError(const char* commandName, const G4String& value, const std::exception& error) const;

    DetectorConstruction* detector_ = nullptr;
    G4UIdirectory* directory_ = nullptr;
    G4UIcmdWithABool* enableSDCmd_ = nullptr;
    G4UIcmdWithAString* setSDNameCmd_ = nullptr;
    G4UIcmdWithoutParameter* printRegistryCmd_ = nullptr;
    G4UIcmdWithoutParameter* printSensitiveVolumesCmd_ = nullptr;
    G4UIcmdWithoutParameter* printBiasVolumesCmd_ = nullptr;
    G4UIcmdWithAnInteger* setVerboseCmd_ = nullptr;
    G4UIcmdWithoutParameter* printWorldCmd_ = nullptr;
};
