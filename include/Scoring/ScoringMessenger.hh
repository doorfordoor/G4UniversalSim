#pragma once

#include "G4UImessenger.hh"

class G4UIcmdWithABool;
class G4UIcmdWithAString;
class G4UIcmdWithAnInteger;
class G4UIcmdWithoutParameter;
class G4UIcommand;
class G4UIdirectory;
class ScoringManager;

class ScoringMessenger : public G4UImessenger {
public:
    explicit ScoringMessenger(ScoringManager* manager);
    ~ScoringMessenger() override;

    void SetNewValue(G4UIcommand* command, G4String newValue) override;

private:
    ScoringManager* manager_ = nullptr; // not owned

    G4UIdirectory* scoringDir_ = nullptr;
    G4UIcmdWithABool* enableCmd_ = nullptr;
    G4UIcmdWithABool* hitsCmd_ = nullptr;
    G4UIcmdWithABool* eventEdepCmd_ = nullptr;
    G4UIcmdWithABool* edepCmd_ = nullptr;
    G4UIcmdWithABool* letCmd_ = nullptr;
    G4UIcmdWithABool* doseCmd_ = nullptr;
    G4UIcmdWithABool* fluenceCmd_ = nullptr;
    G4UIcmdWithABool* autoCreateScorersCmd_ = nullptr;
    G4UIcmdWithAString* setEdepHistogramCmd_ = nullptr;
    G4UIcmdWithAString* setWeightedEdepHistogramCmd_ = nullptr;
    G4UIcmdWithAnInteger* verboseCmd_ = nullptr;
    G4UIcmdWithoutParameter* printCmd_ = nullptr;
};
