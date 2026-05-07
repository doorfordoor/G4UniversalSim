#pragma once

#include "G4UImessenger.hh"

#include <memory>

class G4UIcmdWithABool;
class G4UIcmdWithAString;
class G4UIcmdWithAnInteger;
class G4UIdirectory;
class G4UIcommand;
class G4String;
class SimulationManager;

class AppMessenger : public G4UImessenger {
public:
    explicit AppMessenger(SimulationManager* manager);
    ~AppMessenger() override;

    void SetNewValue(G4UIcommand* command, G4String value) override;

private:
    SimulationManager* manager_ = nullptr;

    std::unique_ptr<G4UIdirectory> appDir_;
    std::unique_ptr<G4UIcmdWithAString> setMainConfigCmd_;
    std::unique_ptr<G4UIcmdWithAString> setOutputDirCmd_;
    std::unique_ptr<G4UIcmdWithAnInteger> setNumThreadsCmd_;
    std::unique_ptr<G4UIcmdWithAnInteger> setSeedCmd_;
    std::unique_ptr<G4UIcmdWithAnInteger> setVerboseCmd_;
    std::unique_ptr<G4UIcmdWithABool> setCheckOverlapsCmd_;
    std::unique_ptr<G4UIcommand> printSummaryCmd_;
};
