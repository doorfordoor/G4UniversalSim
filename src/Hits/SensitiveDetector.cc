#include "Hits/SensitiveDetector.hh"

#include "Hits/ParticleHit.hh"
#include "Hits/ParticleHitCollection.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/DoseContext.hh"
#include "Scoring/ThreadLocalScoringContext.hh"

#include "G4Event.hh"
#include "G4Exception.hh"
#include "G4HCofThisEvent.hh"
#include "G4RunManager.hh"
#include "G4SDManager.hh"
#include "G4Step.hh"
#include "G4TouchableHistory.hh"
#include "G4ios.hh"
#ifdef G4MULTITHREADED
#include "G4Threading.hh"
#endif

#include <cmath>
#include <memory>
#include <stdexcept>

SensitiveDetector::SensitiveDetector(const G4String& name,
                                     ScoringManager* scoringManager)
    : G4VSensitiveDetector(name),
      scoringManager_(scoringManager)
{
    collectionName.insert(collectionName_);
}

SensitiveDetector::~SensitiveDetector() = default;

void SensitiveDetector::Initialize(G4HCofThisEvent* hce)
{
    hitsThisEvent_ = 0;
    rawEdepThisEvent_ = 0.0;
    weightedEdepThisEvent_ = 0.0;
    hitsCollection_ = nullptr;

    if (!hitCollectionEnabled_) return;

    if (!hce) {
        throw std::runtime_error("SensitiveDetector::Initialize failed: G4HCofThisEvent is null while hit collection is enabled");
    }

    hitsCollection_ = new ParticleHitCollection(SensitiveDetectorName, collectionName_);
    if (collectionID_ < 0) {
        G4SDManager* sdManager = G4SDManager::GetSDMpointer();
        if (!sdManager) {
            throw std::runtime_error("SensitiveDetector::Initialize failed: G4SDManager is null");
        }
        collectionID_ = sdManager->GetCollectionID(hitsCollection_);
    }
    hce->AddHitsCollection(collectionID_, hitsCollection_);
}

G4bool SensitiveDetector::ProcessHits(G4Step* step, G4TouchableHistory* history)
{
    (void)history;
    if (!step) return false;

    const G4double edep = step->GetTotalEnergyDeposit();
    const G4double ndep = step->GetNonIonizingEnergyDeposit();
    if (!zeroEdepHitsEnabled_ && edep <= 0.0 && ndep <= 0.0) {
        if (scoringEnabled_) {
            if (ScoringManager* manager = ResolveScoringManager();
                manager && (manager->IsFluenceScoringEnabled() || manager->IsLETScoringEnabled() ||
                            manager->IsDisplacementScoringEnabled()) &&
                step->GetStepLength() > 0.0) {
                try {
                    std::unique_ptr<ParticleHit> particle(ParticleHit::FromStep(step, GetCurrentEventID()));
                    auto record = particle->ToHitRecord();
                    PopulateDoseContext(step, record);
                    if (manager->IsFluenceScoringEnabled()) manager->ScoreFluenceStep(record);
                    if (manager->IsDisplacementScoringEnabled()) manager->ScoreDisplacementStep(record);
                    if (manager->IsLETScoringEnabled()) {
                        record.LETstep = ElectronicStoppingPower(step);
                        manager->ScoreLETStep(record);
                    }
                } catch (const std::exception& error) {
                    manager->ReportFluenceTransportFailure(error.what());
                }
            }
        }
        return false;
    }

    std::unique_ptr<ParticleHit> hit(ParticleHit::FromStep(step, GetCurrentEventID()));

    ++hitsThisEvent_;
    rawEdepThisEvent_ += hit->GetEdep();
    weightedEdepThisEvent_ += hit->GetEdep() * hit->GetWeight();

    if (scoringEnabled_) {
        if (ScoringManager* scoringManager = ResolveScoringManager()) {
            auto record = hit->ToHitRecord();
            if (scoringManager->IsDoseScoringEnabled() || scoringManager->IsFluenceScoringEnabled() ||
                scoringManager->IsLETScoringEnabled() || scoringManager->IsDisplacementScoringEnabled()) {
                PopulateDoseContext(step, record);
            }
            if (scoringManager->IsLETScoringEnabled()) record.LETstep = ElectronicStoppingPower(step);
            scoringManager->ScoreHit(record);
        }
    }

    if (hitCollectionEnabled_ && hitsCollection_) {
        hitsCollection_->insert(hit.release());
    }

    return true;
}

void SensitiveDetector::EndOfEvent(G4HCofThisEvent* hce)
{
    (void)hce;
    if (verboseLevel_ > 0) {
        G4cout << "[SensitiveDetector] " << SensitiveDetectorName
               << " hits=" << hitsThisEvent_
               << " rawEdep=" << rawEdepThisEvent_
               << " weightedEdep=" << weightedEdepThisEvent_
               << G4endl;
    }
}

void SensitiveDetector::SetScoringManager(ScoringManager* scoringManager)
{
    scoringManager_ = scoringManager;
}

ScoringManager* SensitiveDetector::GetScoringManager()
{
    return scoringManager_;
}

const ScoringManager* SensitiveDetector::GetScoringManager() const
{
    return scoringManager_;
}

void SensitiveDetector::SetVerboseLevel(int level)
{
    if (level < 0) throw std::runtime_error("SensitiveDetector::SetVerboseLevel failed: level must be >= 0");
    verboseLevel_ = level;
}

int SensitiveDetector::GetVerboseLevel() const
{
    return verboseLevel_;
}

void SensitiveDetector::EnableZeroEdepHits(bool enable)
{
    zeroEdepHitsEnabled_ = enable;
}

bool SensitiveDetector::IsZeroEdepHitsEnabled() const
{
    return zeroEdepHitsEnabled_;
}

void SensitiveDetector::EnableHitCollection(bool enable)
{
    hitCollectionEnabled_ = enable;
}

bool SensitiveDetector::IsHitCollectionEnabled() const
{
    return hitCollectionEnabled_;
}

void SensitiveDetector::EnableScoring(bool enable)
{
    scoringEnabled_ = enable;
}

bool SensitiveDetector::IsScoringEnabled() const
{
    return scoringEnabled_;
}

int SensitiveDetector::GetHitsThisEvent() const
{
    return hitsThisEvent_;
}

double SensitiveDetector::GetRawEdepThisEvent() const
{
    return rawEdepThisEvent_;
}

double SensitiveDetector::GetWeightedEdepThisEvent() const
{
    return weightedEdepThisEvent_;
}

const G4String& SensitiveDetector::GetCollectionName() const
{
    return collectionName_;
}

G4int SensitiveDetector::GetCollectionID() const
{
    return collectionID_;
}

int SensitiveDetector::GetCurrentEventID() const
{
    const G4RunManager* runManager = G4RunManager::GetRunManager();
    if (!runManager) return -1;
    const G4Event* event = runManager->GetCurrentEvent();
    if (!event) return -1;
    return event->GetEventID();
}

double SensitiveDetector::ElectronicStoppingPower(const G4Step* step)
{
    if (!step || step->GetStepLength() <= 0.0) return 0.0;
    const G4Track* track = step->GetTrack();
    const G4StepPoint* pre = step->GetPreStepPoint();
    const G4StepPoint* post = step->GetPostStepPoint();
    if (!track || !pre || !post || !pre->GetMaterial()) return 0.0;
    const G4ParticleDefinition* particle = track->GetParticleDefinition();
    if (!particle || particle->GetPDGCharge() == 0.0) return 0.0;
    const G4double meanEnergy = 0.5 * (pre->GetKineticEnergy() + post->GetKineticEnergy());
    if (meanEnergy <= 0.0) return 0.0;
    const G4double dedx = emCalculator_.ComputeElectronicDEDX(meanEnergy, particle, pre->GetMaterial());
    return std::isfinite(dedx) && dedx > 0.0 ? dedx : 0.0;
}

ScoringManager* SensitiveDetector::ResolveScoringManager()
{
    if (ScoringManager* scoringManager = AIHL::GetCurrentThreadScoringManager()) {
        return scoringManager;
    }

#ifdef G4MULTITHREADED
    if (scoringManager_ && !fallbackWarningIssued_ &&
        G4Threading::G4GetThreadId() >= 0) {
        fallbackWarningIssued_ = true;
        G4Exception(
            "SensitiveDetector::ResolveScoringManager",
            "AIHLSDMT001",
            JustWarning,
            "Thread-local ScoringManager is not registered for this worker; falling back to the global ScoringManager. Multi-thread scoring output may be unsafe."
        );
    }
#endif

    return scoringManager_;
}
