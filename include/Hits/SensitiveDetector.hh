#pragma once

#include "G4EmCalculator.hh"
#include "G4String.hh"
#include "G4VSensitiveDetector.hh"
#include "globals.hh"

#include "Hits/ParticleHitCollection.hh"

class G4HCofThisEvent;
class G4Step;
class G4TouchableHistory;
class ScoringManager;

class SensitiveDetector : public G4VSensitiveDetector {
public:
    explicit SensitiveDetector(const G4String& name,
                               ScoringManager* scoringManager = nullptr);
    ~SensitiveDetector() override;

    void Initialize(G4HCofThisEvent* hce) override;
    G4bool ProcessHits(G4Step* step, G4TouchableHistory* history) override;
    void EndOfEvent(G4HCofThisEvent* hce) override;

    void SetScoringManager(ScoringManager* scoringManager);
    ScoringManager* GetScoringManager();
    const ScoringManager* GetScoringManager() const;

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

    void EnableZeroEdepHits(bool enable);
    bool IsZeroEdepHitsEnabled() const;

    void EnableHitCollection(bool enable);
    bool IsHitCollectionEnabled() const;

    void EnableScoring(bool enable);
    bool IsScoringEnabled() const;

    int GetHitsThisEvent() const;
    double GetRawEdepThisEvent() const;
    double GetWeightedEdepThisEvent() const;

    const G4String& GetCollectionName() const;
    G4int GetCollectionID() const;

private:
    void InjectBoundaryFault(bool initialize);
    void ReportBoundaryFailure(const char* stage, const char* message);
    int GetCurrentEventID() const;
    ScoringManager* ResolveScoringManager();
    // Unrestricted electronic stopping power at the step's mean kinetic energy
    // (Geant4 units); 0 for neutral particles or zero-length steps.
    double ElectronicStoppingPower(const G4Step* step);

    ScoringManager* scoringManager_ = nullptr; // not owned
    ParticleHitCollection* hitsCollection_ = nullptr; // owned by Geant4 event after insertion
    G4int collectionID_ = -1;
    G4String collectionName_ = "ParticleHits";

    bool zeroEdepHitsEnabled_ = false;
    bool hitCollectionEnabled_ = true;
    bool scoringEnabled_ = true;

    int verboseLevel_ = 0;
    bool fallbackWarningIssued_ = false;
    bool callbackFailed_ = false;
    enum class BoundaryFault { None, Context, ContextUnknown, Initialize, InitializeUnknown };
    BoundaryFault boundaryFault_ = BoundaryFault::None;
    bool boundaryFaultInjected_ = false;
    bool boundaryFaultAnyWorker_ = false;
    G4EmCalculator emCalculator_;
    int hitsThisEvent_ = 0;
    double rawEdepThisEvent_ = 0.0;
    double weightedEdepThisEvent_ = 0.0;
};
