#include "Detector/DetectorMessenger.hh"

#include "Detector/DetectorConstruction.hh"

#include "G4Exception.hh"
#include "G4UIcmdWithABool.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIcmdWithAnInteger.hh"
#include "G4UIcmdWithoutParameter.hh"
#include "G4UIdirectory.hh"
#include "G4VPhysicalVolume.hh"
#include "G4ios.hh"

#include <exception>
#include <stdexcept>

DetectorMessenger::DetectorMessenger(DetectorConstruction* detector)
    : detector_(detector)
{
    directory_ = new G4UIdirectory("/AIHL/detector/");
    directory_->SetGuidance("Detector construction commands for G4UniversalSim.");

    enableSDCmd_ = new G4UIcmdWithABool("/AIHL/detector/enableSD", this);
    enableSDCmd_->SetGuidance("Enable or disable sensitive detector binding in ConstructSDandField().");
    enableSDCmd_->SetParameterName("enable", false);

    setSDNameCmd_ = new G4UIcmdWithAString("/AIHL/detector/setSDName", this);
    setSDNameCmd_->SetGuidance("Set the logical sensitive detector name reserved for the future Hits module.");
    setSDNameCmd_->SetParameterName("name", false);

    printRegistryCmd_ = new G4UIcmdWithoutParameter("/AIHL/detector/printRegistry", this);
    printRegistryCmd_->SetGuidance("Print GeometryRegistry summary.");

    printSensitiveVolumesCmd_ = new G4UIcmdWithoutParameter("/AIHL/detector/printSensitiveVolumes", this);
    printSensitiveVolumesCmd_->SetGuidance("Print sensitive volume names from GeometryRegistry.");

    printBiasVolumesCmd_ = new G4UIcmdWithoutParameter("/AIHL/detector/printBiasVolumes", this);
    printBiasVolumesCmd_->SetGuidance("Print bias volume names from GeometryRegistry.");

    setVerboseCmd_ = new G4UIcmdWithAnInteger("/AIHL/detector/setVerbose", this);
    setVerboseCmd_->SetGuidance("Set DetectorConstruction verbose level.");
    setVerboseCmd_->SetParameterName("level", false);

    printWorldCmd_ = new G4UIcmdWithoutParameter("/AIHL/detector/printWorld", this);
    printWorldCmd_->SetGuidance("Print whether the last constructed world volume is available.");
}

DetectorMessenger::~DetectorMessenger()
{
    delete printWorldCmd_;
    delete setVerboseCmd_;
    delete printBiasVolumesCmd_;
    delete printSensitiveVolumesCmd_;
    delete printRegistryCmd_;
    delete setSDNameCmd_;
    delete enableSDCmd_;
    delete directory_;
}

void DetectorMessenger::SetNewValue(G4UIcommand* command, G4String newValue)
{
    try {
        if (command == enableSDCmd_) {
            EnsureDetector("/AIHL/detector/enableSD");
            detector_->SetSensitiveDetectorEnabled(enableSDCmd_->GetNewBoolValue(newValue));
            return;
        }
        if (command == setSDNameCmd_) {
            EnsureDetector("/AIHL/detector/setSDName");
            detector_->SetSensitiveDetectorName(newValue);
            return;
        }
        if (command == printRegistryCmd_) {
            EnsureDetector("/AIHL/detector/printRegistry");
            detector_->PrintRegistrySummary();
            return;
        }
        if (command == printSensitiveVolumesCmd_) {
            EnsureDetector("/AIHL/detector/printSensitiveVolumes");
            detector_->PrintSensitiveVolumes();
            return;
        }
        if (command == printBiasVolumesCmd_) {
            EnsureDetector("/AIHL/detector/printBiasVolumes");
            detector_->PrintBiasVolumes();
            return;
        }
        if (command == setVerboseCmd_) {
            EnsureDetector("/AIHL/detector/setVerbose");
            detector_->SetVerboseLevel(setVerboseCmd_->GetNewIntValue(newValue));
            return;
        }
        if (command == printWorldCmd_) {
            EnsureDetector("/AIHL/detector/printWorld");
            G4cout << "[DetectorMessenger] worldVolume="
                   << (detector_->GetWorldVolume() ? "available" : "not built")
                   << G4endl;
            return;
        }
    } catch (const std::exception& e) {
        ReportCommandError("DetectorMessenger::SetNewValue", newValue, e);
        return;
    }

    G4Exception(
        "DetectorMessenger::SetNewValue",
        "AIHLDetectorCmd000",
        JustWarning,
        "Unknown /AIHL/detector command object."
    );
}

void DetectorMessenger::EnsureDetector(const char* commandName) const
{
    if (!detector_) {
        throw std::runtime_error(std::string(commandName) + " failed: DetectorConstruction pointer is null");
    }
}

void DetectorMessenger::ReportCommandError(const char* commandName, const G4String& value, const std::exception& error) const
{
    const std::string message = std::string(commandName) + " failed for input '" + value + "': " + error.what();
    G4Exception("DetectorMessenger", "AIHLDetectorCmd001", JustWarning, message.c_str());
}
