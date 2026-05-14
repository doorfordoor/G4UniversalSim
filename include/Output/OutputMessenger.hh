#pragma once

#include "G4UImessenger.hh"

#include <exception>
#include <memory>

class G4UIcmdWithABool;
class G4UIcmdWithAString;
class G4UIcmdWithoutParameter;
class G4UIdirectory;
class G4UIcommand;
class G4String;
class OutputManager;

class OutputMessenger : public G4UImessenger {
public:
    explicit OutputMessenger(OutputManager* outputManager);
    ~OutputMessenger() override;

    void SetNewValue(G4UIcommand* command, G4String newValue) override;

private:
    void EnsureOutputManager(const char* commandName) const;
    void WarnIfInitializedOrOpen(const char* commandName) const;
    void ReportCommandError(const char* commandName, const G4String& value, const std::exception& error) const;
    void PrintSummary() const;

    OutputManager* outputManager_ = nullptr;
    std::unique_ptr<G4UIdirectory> directory_;
    std::unique_ptr<G4UIcmdWithAString> setDirCmd_;
    std::unique_ptr<G4UIcmdWithABool> setThreadSuffixCmd_;
    std::unique_ptr<G4UIcmdWithoutParameter> printCmd_;
    std::unique_ptr<G4UIcmdWithoutParameter> flushCmd_;
    std::unique_ptr<G4UIcmdWithoutParameter> closeCmd_;
};
