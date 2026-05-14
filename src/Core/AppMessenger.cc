#include "Core/AppMessenger.hh"

#include "Core/SimulationManager.hh"

#include "G4Exception.hh"
#include "G4UIcmdWithABool.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIcmdWithAnInteger.hh"
#include "G4UIcommand.hh"
#include "G4UIdirectory.hh"

#include <string>

namespace {

void WarnIfInitialized(const SimulationManager* manager, const char* commandName)
{
    if (!manager || !manager->IsInitialized()) return;
    G4Exception(
        "AppMessenger",
        "AIHLAppCmdWarn001",
        JustWarning,
        (std::string(commandName)
         + " is recommended before /run/initialize. If run-manager state already exists, "
           "reinitialize geometry/physics or restart the executable as appropriate.").c_str()
    );
}

}  // namespace

AppMessenger::AppMessenger(SimulationManager* manager)
    : manager_(manager)
{
    appDir_ = std::make_unique<G4UIdirectory>("/AIHL/app/");
    appDir_->SetGuidance("Application-level commands for G4UniversalSim.");

    setMainConfigCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/app/setMainConfig", this);
    setMainConfigCmd_->SetGuidance("Set the main ini config file.");

    setOutputDirCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/app/setOutputDir", this);
    setOutputDirCmd_->SetGuidance("Set output directory.");

    setNumThreadsCmd_ = std::make_unique<G4UIcmdWithAnInteger>("/AIHL/app/setNumThreads", this);
    setNumThreadsCmd_->SetGuidance("Set number of worker threads.");
    setNumThreadsCmd_->SetParameterName("threads", false);
    setNumThreadsCmd_->SetRange("threads > 0");

    setSeedCmd_ = std::make_unique<G4UIcmdWithAnInteger>("/AIHL/app/setSeed", this);
    setSeedCmd_->SetGuidance("Set random seed stored in SimulationContext.");
    setSeedCmd_->SetParameterName("seed", false);
    setSeedCmd_->SetRange("seed >= 0");

    setVerboseCmd_ = std::make_unique<G4UIcmdWithAnInteger>("/AIHL/app/setVerbose", this);
    setVerboseCmd_->SetGuidance("Set application verbose level.");

    setCheckOverlapsCmd_ = std::make_unique<G4UIcmdWithABool>("/AIHL/app/setCheckOverlaps", this);
    setCheckOverlapsCmd_->SetGuidance("Enable or disable geometry overlap checks.");

    printSummaryCmd_ = std::make_unique<G4UIcommand>("/AIHL/app/printSummary", this);
    printSummaryCmd_->SetGuidance("Print current SimulationManager summary.");
}

AppMessenger::~AppMessenger() = default;

void AppMessenger::SetNewValue(G4UIcommand* command, G4String value)
{
    if (!manager_) {
        G4Exception(
            "AppMessenger::SetNewValue",
            "G4UniversalSim_Core_001",
            JustWarning,
            "SimulationManager pointer is null."
        );
        return;
    }

    if (command == setMainConfigCmd_.get()) {
        WarnIfInitialized(manager_, "/AIHL/app/setMainConfig");
        manager_->SetMainConfig(value);
    } else if (command == setOutputDirCmd_.get()) {
        WarnIfInitialized(manager_, "/AIHL/app/setOutputDir");
        manager_->SetOutputDir(value);
    } else if (command == setNumThreadsCmd_.get()) {
        WarnIfInitialized(manager_, "/AIHL/app/setNumThreads");
        manager_->SetNumThreads(setNumThreadsCmd_->GetNewIntValue(value));
    } else if (command == setSeedCmd_.get()) {
        WarnIfInitialized(manager_, "/AIHL/app/setSeed");
        const int seed = setSeedCmd_->GetNewIntValue(value);
        manager_->SetSeed(static_cast<unsigned long>(seed));
    } else if (command == setVerboseCmd_.get()) {
        manager_->SetVerboseLevel(setVerboseCmd_->GetNewIntValue(value));
    } else if (command == setCheckOverlapsCmd_.get()) {
        WarnIfInitialized(manager_, "/AIHL/app/setCheckOverlaps");
        manager_->SetCheckOverlaps(setCheckOverlapsCmd_->GetNewBoolValue(value));
    } else if (command == printSummaryCmd_.get()) {
        manager_->PrintSummary();
    }
}
