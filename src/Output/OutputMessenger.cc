#include "Output/OutputMessenger.hh"

#include "Output/OutputManager.hh"

#include "G4Exception.hh"
#include "G4UIcmdWithABool.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIcmdWithoutParameter.hh"
#include "G4UIdirectory.hh"
#include "G4ios.hh"

#include <exception>
#include <memory>
#include <stdexcept>
#include <string>

OutputMessenger::OutputMessenger(OutputManager* outputManager)
    : outputManager_(outputManager)
{
    directory_ = std::make_unique<G4UIdirectory>("/AIHL/output/");
    directory_->SetGuidance("Output manager commands for G4UniversalSim.");

    setDirCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/output/setDir", this);
    setDirCmd_->SetGuidance("Set output directory. Recommended before /run/initialize and before output files are opened.");
    setDirCmd_->SetParameterName("dir", false);

    setThreadSuffixCmd_ = std::make_unique<G4UIcmdWithABool>("/AIHL/output/setThreadSuffix", this);
    setThreadSuffixCmd_->SetGuidance("Enable or disable _tN thread suffixes in output filenames.");
    setThreadSuffixCmd_->SetParameterName("enable", false);

    printCmd_ = std::make_unique<G4UIcmdWithoutParameter>("/AIHL/output/print", this);
    printCmd_->SetGuidance("Print OutputManager state.");

    flushCmd_ = std::make_unique<G4UIcmdWithoutParameter>("/AIHL/output/flush", this);
    flushCmd_->SetGuidance("Flush open output files.");

    closeCmd_ = std::make_unique<G4UIcmdWithoutParameter>("/AIHL/output/close", this);
    closeCmd_->SetGuidance("Close open output files.");
}

OutputMessenger::~OutputMessenger() = default;

void OutputMessenger::SetNewValue(G4UIcommand* command, G4String newValue)
{
    try {
        if (command == setDirCmd_.get()) {
            EnsureOutputManager("/AIHL/output/setDir");
            WarnIfInitializedOrOpen("/AIHL/output/setDir");
            outputManager_->SetOutputDir(newValue);
            return;
        }
        if (command == setThreadSuffixCmd_.get()) {
            EnsureOutputManager("/AIHL/output/setThreadSuffix");
            WarnIfInitializedOrOpen("/AIHL/output/setThreadSuffix");
            outputManager_->EnableThreadSuffix(setThreadSuffixCmd_->GetNewBoolValue(newValue));
            return;
        }
        if (command == printCmd_.get()) {
            EnsureOutputManager("/AIHL/output/print");
            PrintSummary();
            return;
        }
        if (command == flushCmd_.get()) {
            EnsureOutputManager("/AIHL/output/flush");
            outputManager_->Flush();
            return;
        }
        if (command == closeCmd_.get()) {
            EnsureOutputManager("/AIHL/output/close");
            outputManager_->Close();
            return;
        }
    } catch (const std::exception& e) {
        const std::string commandName = command ? std::string(command->GetCommandPath()) : "OutputMessenger::SetNewValue";
        ReportCommandError(commandName.c_str(), newValue, e);
        return;
    }

    G4Exception(
        "OutputMessenger::SetNewValue",
        "AIHLOutputCmd000",
        JustWarning,
        "Unknown /AIHL/output command object."
    );
}

void OutputMessenger::EnsureOutputManager(const char* commandName) const
{
    if (!outputManager_) {
        throw std::runtime_error(std::string(commandName) + " failed: OutputManager pointer is null");
    }
}

void OutputMessenger::WarnIfInitializedOrOpen(const char* commandName) const
{
    if (!outputManager_) return;
    if (outputManager_->IsInitialized() || outputManager_->HasOpenFiles()) {
        G4Exception(
            "OutputMessenger",
            "AIHLOutputCmdWarn001",
            JustWarning,
            (std::string(commandName)
             + " is recommended before /run/initialize and before output files are opened. "
               "Changing output settings after initialization may only affect files opened later.").c_str()
        );
    }
}

void OutputMessenger::ReportCommandError(const char* commandName, const G4String& value, const std::exception& error) const
{
    const std::string message = std::string(commandName) + " failed for input '" + value + "': " + error.what();
    G4Exception("OutputMessenger", "AIHLOutputCmd001", JustWarning, message.c_str());
}

void OutputMessenger::PrintSummary() const
{
    EnsureOutputManager("/AIHL/output/print");
    G4cout << "[OutputManager] outputDir=" << outputManager_->GetOutputDir()
           << ", threadId=" << outputManager_->GetThreadId()
           << ", threadSuffix=" << (outputManager_->IsThreadSuffixEnabled() ? "true" : "false")
           << ", initialized=" << (outputManager_->IsInitialized() ? "true" : "false")
           << G4endl;
    G4cout << "  hitFileOpen=" << (outputManager_->IsHitFileOpen() ? "true" : "false");
    if (!outputManager_->GetHitFilename().empty()) G4cout << ", hitFile=" << outputManager_->GetHitFilename();
    G4cout << G4endl;
    G4cout << "  eventEdepFileOpen=" << (outputManager_->IsEventEdepFileOpen() ? "true" : "false");
    if (!outputManager_->GetEventEdepFilename().empty()) G4cout << ", eventEdepFile=" << outputManager_->GetEventEdepFilename();
    G4cout << G4endl;
}
