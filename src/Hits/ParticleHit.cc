#include "Hits/ParticleHit.hh"

#include "G4ParticleDefinition.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh"
#include "G4Track.hh"
#include "G4TouchableHandle.hh"
#include "G4VPhysicalVolume.hh"
#include "G4VProcess.hh"
#include "G4ios.hh"

#include <stdexcept>

G4ThreadLocal G4Allocator<ParticleHit>* ParticleHitAllocator = nullptr;

ParticleHit::ParticleHit() = default;
ParticleHit::~ParticleHit() = default;
ParticleHit::ParticleHit(const ParticleHit& other) = default;
ParticleHit& ParticleHit::operator=(const ParticleHit& other) = default;

void* ParticleHit::operator new(std::size_t)
{
    if (!ParticleHitAllocator) {
        ParticleHitAllocator = new G4Allocator<ParticleHit>;
    }
    return ParticleHitAllocator->MallocSingle();
}

void ParticleHit::operator delete(void* hit)
{
    if (!ParticleHitAllocator) {
        ParticleHitAllocator = new G4Allocator<ParticleHit>;
    }
    ParticleHitAllocator->FreeSingle(static_cast<ParticleHit*>(hit));
}

void ParticleHit::Draw()
{
}

void ParticleHit::Print()
{
    G4cout << "[ParticleHit] event=" << eventID_
           << " track=" << trackID_
           << " parent=" << parentID_
           << " particle=" << particleName_
           << " edep=" << edep_
           << " weight=" << weight_
           << " volume=" << volumeName_
           << " process=" << processName_
           << G4endl;
}

void ParticleHit::SetEventID(int id) { eventID_ = id; }
int ParticleHit::GetEventID() const { return eventID_; }

void ParticleHit::SetTrackID(int id) { trackID_ = id; }
int ParticleHit::GetTrackID() const { return trackID_; }

void ParticleHit::SetParentID(int id) { parentID_ = id; }
int ParticleHit::GetParentID() const { return parentID_; }

void ParticleHit::SetName(const G4String& name) { particleName_ = name; }
const G4String& ParticleHit::GetName() const { return particleName_; }

void ParticleHit::SetEdep(G4double value) { edep_ = value; }
G4double ParticleHit::GetEdep() const { return edep_; }

void ParticleHit::SetNdep(G4double value) { ndep_ = value; }
G4double ParticleHit::GetNdep() const { return ndep_; }

void ParticleHit::SetStepLength(G4double value) { stepLength_ = value; }
G4double ParticleHit::GetStepLength() const { return stepLength_; }

void ParticleHit::SetFirstPos(const G4ThreeVector& pos) { firstPosition_ = pos; }
const G4ThreeVector& ParticleHit::GetFirstPos() const { return firstPosition_; }

void ParticleHit::SetLastPos(const G4ThreeVector& pos) { lastPosition_ = pos; }
const G4ThreeVector& ParticleHit::GetLastPos() const { return lastPosition_; }

void ParticleHit::SetMomentumDirection(const G4ThreeVector& dir) { momentumDirection_ = dir; }
const G4ThreeVector& ParticleHit::GetMomentumDirection() const { return momentumDirection_; }

void ParticleHit::SetEkin(G4double value) { kineticEnergy_ = value; }
G4double ParticleHit::GetEkin() const { return kineticEnergy_; }

void ParticleHit::SetProcess(const G4String& process) { processName_ = process; }
const G4String& ParticleHit::GetProcess() const { return processName_; }

void ParticleHit::SetVolume(const G4String& volume) { volumeName_ = volume; }
const G4String& ParticleHit::GetVolume() const { return volumeName_; }

void ParticleHit::SetWeight(G4double value) { weight_ = value; }
G4double ParticleHit::GetWeight() const { return weight_; }

void ParticleHit::SetLETcalc(G4double value) { LETcalc_ = value; }
G4double ParticleHit::GetLETcalc() const { return LETcalc_; }

void ParticleHit::SetLETstep(G4double value) { LETstep_ = value; }
G4double ParticleHit::GetLETstep() const { return LETstep_; }

void ParticleHit::SetZ(int z) { z_ = z; }
int ParticleHit::GetZ() const { return z_; }

void ParticleHit::SetA(int a) { a_ = a; }
int ParticleHit::GetA() const { return a_; }

HitRecord ParticleHit::ToHitRecord() const
{
    HitRecord record;
    record.eventID = eventID_;
    record.trackID = trackID_;
    record.parentID = parentID_;
    record.particleName = particleName_;
    record.edep = edep_;
    record.ndep = ndep_;
    record.stepLength = stepLength_;
    record.x0 = firstPosition_.x();
    record.y0 = firstPosition_.y();
    record.z0 = firstPosition_.z();
    record.x1 = lastPosition_.x();
    record.y1 = lastPosition_.y();
    record.z1 = lastPosition_.z();
    record.px = momentumDirection_.x();
    record.py = momentumDirection_.y();
    record.pz = momentumDirection_.z();
    record.kineticEnergy = kineticEnergy_;
    record.processName = processName_;
    record.volumeName = volumeName_;
    record.weight = weight_;
    record.LETcalc = LETcalc_;
    record.LETstep = LETstep_;
    return record;
}

ParticleHit* ParticleHit::FromStep(const G4Step* step, int eventID)
{
    if (!step) {
        throw std::runtime_error("ParticleHit::FromStep failed: step is null");
    }

    const G4Track* track = step->GetTrack();
    if (!track) {
        throw std::runtime_error("ParticleHit::FromStep failed: step has null track");
    }

    const G4StepPoint* pre = step->GetPreStepPoint();
    const G4StepPoint* post = step->GetPostStepPoint();

    auto* hit = new ParticleHit;
    hit->SetEventID(eventID);
    hit->SetTrackID(track->GetTrackID());
    hit->SetParentID(track->GetParentID());
    hit->SetEdep(step->GetTotalEnergyDeposit());
    hit->SetNdep(step->GetNonIonizingEnergyDeposit());
    hit->SetStepLength(step->GetStepLength());
    hit->SetWeight(track->GetWeight());

    const G4ParticleDefinition* particle = track->GetDefinition();
    if (particle) {
        hit->SetName(particle->GetParticleName());
        hit->SetZ(static_cast<int>(particle->GetAtomicNumber()));
        hit->SetA(static_cast<int>(particle->GetAtomicMass()));
    }

    if (pre) {
        hit->SetFirstPos(pre->GetPosition());
        hit->SetMomentumDirection(pre->GetMomentumDirection());
        hit->SetEkin(pre->GetKineticEnergy());
        const G4TouchableHandle& touchable = pre->GetTouchableHandle();
        if (touchable && touchable->GetVolume()) {
            hit->SetVolume(touchable->GetVolume()->GetName());
        } else {
            hit->SetVolume("unknown");
        }
    } else {
        hit->SetVolume("unknown");
    }

    if (post) {
        hit->SetLastPos(post->GetPosition());
        const G4VProcess* process = post->GetProcessDefinedStep();
        hit->SetProcess(process ? process->GetProcessName() : "none");
    } else {
        hit->SetProcess("none");
    }

    return hit;
}
