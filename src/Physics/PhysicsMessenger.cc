#include "Physics/PhysicsMessenger.hh"

#include "Physics/PhysicsFactory.hh"
#include "Physics/PhysicsManager.hh"
#include "Utils/CommandParser.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4Exception.hh"
#include "G4UIcmdWithABool.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIcmdWithAnInteger.hh"
#include "G4UIcmdWithoutParameter.hh"
#include "G4UIdirectory.hh"
#include "G4ios.hh"

#include <stdexcept>
#include <string>
#include <vector>

namespace {

PhysicsManager* RequireManager(PhysicsManager* manager, const std::string& command)
{
    if (!manager) {
        throw std::runtime_error("PhysicsMessenger command '" + command + "' failed: PhysicsManager is null");
    }
    return manager;
}

void ReportFailure(const std::string& command, const std::string& raw, const std::exception& error)
{
    const auto message = "Physics command " + command + " failed for input '" + raw + "': " + error.what()
        + ". Supported examples: /AIHL/physics/setDefaultCut 1 mm; /AIHL/physics/setCut proton 1 um; /AIHL/physics/setRegionCut SV e- 100 nm.";
    G4Exception("PhysicsMessenger::SetNewValue", "AIHL_PHYSICS_001",
                FatalException, message.c_str());
}

std::pair<std::string, double> ParseParticleCutArgs(const std::string& raw)
{
    const auto tokens = CommandParser::SplitWhitespaceRespectQuotes(raw);
    if (tokens.size() < 2) {
        throw std::runtime_error("expected '<particle> <value unit>'");
    }
    std::string value = tokens[1];
    for (std::size_t i = 2; i < tokens.size(); ++i) value += " " + tokens[i];
    return {tokens[0], UnitParser::ParseLength(value)};
}

struct RegionCutArgs {
    std::string region;
    std::string particle;
    double cut = 0.0;
};

RegionCutArgs ParseRegionCutArgs(const std::string& raw)
{
    const auto tokens = CommandParser::SplitWhitespaceRespectQuotes(raw);
    if (tokens.size() < 3) {
        throw std::runtime_error("expected '<region> <particle> <value unit>'");
    }
    std::string value = tokens[2];
    for (std::size_t i = 3; i < tokens.size(); ++i) value += " " + tokens[i];
    return {tokens[0], tokens[1], UnitParser::ParseLength(value)};
}

} // namespace

PhysicsMessenger::PhysicsMessenger(PhysicsManager* manager)
    : manager_(manager)
{
    physicsDir_ = new G4UIdirectory("/AIHL/physics/");
    physicsDir_->SetGuidance("AIHL physics configuration commands. Prefer before /run/initialize.");

    setEMCmd_ = new G4UIcmdWithAString("/AIHL/physics/setEM", this);
    setReferenceListCmd_ = new G4UIcmdWithAString("/AIHL/physics/setReferenceList", this);
    clearReferenceListCmd_ = new G4UIcmdWithoutParameter("/AIHL/physics/clearReferenceList", this);
    setBaseReferenceListCmd_ = new G4UIcmdWithAString("/AIHL/physics/setBaseReferenceList", this);
    addModuleCmd_ = new G4UIcmdWithAString("/AIHL/physics/addModule", this);
    removeModuleCmd_ = new G4UIcmdWithAString("/AIHL/physics/removeModule", this);
    clearModulesCmd_ = new G4UIcmdWithoutParameter("/AIHL/physics/clearModules", this);
    addHadronicCmd_ = new G4UIcmdWithAString("/AIHL/physics/addHadronic", this);
    addOtherCmd_ = new G4UIcmdWithAString("/AIHL/physics/addOther", this);
    addExtraModuleCmd_ = new G4UIcmdWithAString("/AIHL/physics/addExtraModule", this);
    removeExtraModuleCmd_ = new G4UIcmdWithAString("/AIHL/physics/removeExtraModule", this);
    clearExtraModulesCmd_ = new G4UIcmdWithoutParameter("/AIHL/physics/clearExtraModules", this);
    setDefaultCutCmd_ = new G4UIcmdWithAString("/AIHL/physics/setDefaultCut", this);
    setCutCmd_ = new G4UIcmdWithAString("/AIHL/physics/setCut", this);
    setRegionCutCmd_ = new G4UIcmdWithAString("/AIHL/physics/setRegionCut", this);
    enableBiasingCmd_ = new G4UIcmdWithABool("/AIHL/physics/enableBiasing", this);
    enableMicroElecCmd_ = new G4UIcmdWithABool("/AIHL/physics/enableMicroElec", this);
    setMicroElecRegionCmd_ = new G4UIcmdWithAString("/AIHL/physics/setMicroElecRegion", this);
    enableElectronCaptureCmd_ = new G4UIcmdWithABool("/AIHL/physics/enableElectronCapture", this);
    setElectronCaptureThresholdCmd_ = new G4UIcmdWithAString("/AIHL/physics/setElectronCaptureThreshold", this);
    verboseCmd_ = new G4UIcmdWithAnInteger("/AIHL/physics/verbose", this);
    printCmd_ = new G4UIcmdWithoutParameter("/AIHL/physics/print", this);
    listAvailableReferencesCmd_ = new G4UIcmdWithoutParameter("/AIHL/physics/listAvailableReferences", this);
    listAvailableEMReferencesCmd_ = new G4UIcmdWithoutParameter("/AIHL/physics/listAvailableEMReferences", this);

    setEMCmd_->SetGuidance("Set EM physics option, e.g. option4, livermore, penelope.");
    setReferenceListCmd_->SetGuidance("Set Geant4 reference physics list, e.g. FTFP_BERT_EMZ.");
    clearReferenceListCmd_->SetGuidance("Leave reference mode and return to manual physics mode.");
    setBaseReferenceListCmd_->SetGuidance("Set base reference list before applying an EM suffix.");
    addModuleCmd_->SetGuidance("Add extra physics module, e.g. bert, elastic, ion, optical.");
    removeModuleCmd_->SetGuidance("Remove extra physics module.");
    clearModulesCmd_->SetGuidance("Clear extra physics modules.");
    addHadronicCmd_->SetGuidance("Add hadronic physics option.");
    addOtherCmd_->SetGuidance("Add non-hadronic physics module.");
    addExtraModuleCmd_->SetGuidance("Add module to reference extra modules; in manual mode, it is added as a normal module.");
    removeExtraModuleCmd_->SetGuidance("Remove reference extra module.");
    clearExtraModulesCmd_->SetGuidance("Clear reference extra modules.");
    setDefaultCutCmd_->SetGuidance("Set default production cut, e.g. 1 mm.");
    setCutCmd_->SetGuidance("Set particle cut: <particle> <value unit>.");
    setRegionCutCmd_->SetGuidance("Store region cut: <region> <particle> <value unit>.");
    enableBiasingCmd_->SetGuidance("Enable generic biasing physics hook.");
    enableMicroElecCmd_->SetGuidance("Enable optional region-scoped MicroElec extension.");
    setMicroElecRegionCmd_->SetGuidance("Set MicroElec target region name, e.g. SV.");
    enableElectronCaptureCmd_->SetGuidance("Enable optional low-energy electron capture helper process.");
    setElectronCaptureThresholdCmd_->SetGuidance("Set electron capture threshold, e.g. 16.7 eV.");
    verboseCmd_->SetGuidance("Set physics verbose level.");
    printCmd_->SetGuidance("Print physics configuration summary.");
    listAvailableReferencesCmd_->SetGuidance("List available Geant4 reference physics lists.");
    listAvailableEMReferencesCmd_->SetGuidance("List available Geant4 reference EM suffixes/options.");
}

PhysicsMessenger::~PhysicsMessenger()
{
    delete listAvailableEMReferencesCmd_;
    delete listAvailableReferencesCmd_;
    delete printCmd_;
    delete verboseCmd_;
    delete setElectronCaptureThresholdCmd_;
    delete enableElectronCaptureCmd_;
    delete setMicroElecRegionCmd_;
    delete enableMicroElecCmd_;
    delete enableBiasingCmd_;
    delete setRegionCutCmd_;
    delete setCutCmd_;
    delete setDefaultCutCmd_;
    delete clearExtraModulesCmd_;
    delete removeExtraModuleCmd_;
    delete addExtraModuleCmd_;
    delete addOtherCmd_;
    delete addHadronicCmd_;
    delete clearModulesCmd_;
    delete removeModuleCmd_;
    delete addModuleCmd_;
    delete setBaseReferenceListCmd_;
    delete clearReferenceListCmd_;
    delete setReferenceListCmd_;
    delete setEMCmd_;
    delete physicsDir_;
}

void PhysicsMessenger::SetNewValue(G4UIcommand* command, G4String newValue)
{
    const std::string raw = newValue;
    try {
        auto* manager = RequireManager(manager_, command ? command->GetCommandPath() : "<unknown>");
        if (command == setEMCmd_) {
            manager->SetEMOption(raw);
        } else if (command == setReferenceListCmd_) {
            manager->SetReferenceList(raw);
        } else if (command == clearReferenceListCmd_) {
            manager->ClearReferenceList();
        } else if (command == setBaseReferenceListCmd_) {
            manager->SetBaseReferenceList(raw);
        } else if (command == addModuleCmd_) {
            manager->AddPhysicsModule(raw);
        } else if (command == removeModuleCmd_) {
            manager->RemovePhysicsModule(raw);
        } else if (command == clearModulesCmd_) {
            manager->ClearPhysicsModules();
        } else if (command == addHadronicCmd_) {
            manager->AddHadronicOption(raw);
        } else if (command == addOtherCmd_) {
            manager->AddOtherOption(raw);
        } else if (command == addExtraModuleCmd_) {
            if (!manager->HasReferenceList()) {
                G4cout << "[PhysicsMessenger] addExtraModule called in manual mode; adding as a manual module." << G4endl;
                manager->AddPhysicsModule(raw);
            } else {
                manager->AddExtraModule(raw);
            }
        } else if (command == removeExtraModuleCmd_) {
            manager->RemoveExtraModule(raw);
        } else if (command == clearExtraModulesCmd_) {
            manager->ClearExtraModules();
        } else if (command == setDefaultCutCmd_) {
            manager->SetDefaultCut(UnitParser::ParseLength(raw));
        } else if (command == setCutCmd_) {
            const auto parsed = ParseParticleCutArgs(raw);
            manager->SetParticleCut(parsed.first, parsed.second);
        } else if (command == setRegionCutCmd_) {
            const auto parsed = ParseRegionCutArgs(raw);
            manager->SetRegionCut(parsed.region, parsed.particle, parsed.cut);
        } else if (command == enableBiasingCmd_) {
            manager->EnableBiasingPhysics(enableBiasingCmd_->GetNewBoolValue(newValue));
        } else if (command == enableMicroElecCmd_) {
            manager->EnableMicroElec(enableMicroElecCmd_->GetNewBoolValue(newValue));
        } else if (command == setMicroElecRegionCmd_) {
            manager->SetMicroElecRegion(raw);
        } else if (command == enableElectronCaptureCmd_) {
            manager->EnableElectronCapture(enableElectronCaptureCmd_->GetNewBoolValue(newValue));
        } else if (command == setElectronCaptureThresholdCmd_) {
            manager->SetElectronCaptureThreshold(UnitParser::ParseEnergy(raw));
        } else if (command == verboseCmd_) {
            manager->SetVerboseLevel(verboseCmd_->GetNewIntValue(newValue));
        } else if (command == printCmd_) {
            manager->PrintSummary();
        } else if (command == listAvailableReferencesCmd_) {
            G4cout << "[PhysicsMessenger] Available reference physics lists:" << G4endl;
            for (const auto& name : PhysicsFactory::AvailableReferenceLists()) {
                G4cout << "  " << name << G4endl;
            }
        } else if (command == listAvailableEMReferencesCmd_) {
            G4cout << "[PhysicsMessenger] Available reference EM options:" << G4endl;
            for (const auto& name : PhysicsFactory::AvailableReferenceListsEM()) {
                G4cout << "  " << name << G4endl;
            }
        }

        if (command != printCmd_ &&
            command != listAvailableReferencesCmd_ &&
            command != listAvailableEMReferencesCmd_) {
            G4cout << "[PhysicsMessenger] Physics configuration changed. "
                   << "Apply before /run/initialize or notify Geant4 with /run/physicsModified when appropriate."
                   << G4endl;
        }
    } catch (const std::exception& error) {
        ReportFailure(command ? command->GetCommandPath() : "<unknown>", raw, error);
    }
}
