#pragma once

#include "G4Allocator.hh"
#include "G4String.hh"
#include "G4ThreeVector.hh"
#include "G4VHit.hh"
#include "globals.hh"

#include "Output/OutputRecord.hh"

#include <cstddef>

class G4Step;

class ParticleHit : public G4VHit {
public:
    ParticleHit();
    ~ParticleHit() override;

    ParticleHit(const ParticleHit& other);
    ParticleHit& operator=(const ParticleHit& other);

    void* operator new(std::size_t size);
    void operator delete(void* hit);

    void Draw() override;
    void Print() override;

    void SetEventID(int id);
    int GetEventID() const;

    void SetTrackID(int id);
    int GetTrackID() const;

    void SetParentID(int id);
    int GetParentID() const;

    void SetName(const G4String& name);
    const G4String& GetName() const;

    void SetEdep(G4double value);
    G4double GetEdep() const;

    void SetNdep(G4double value);
    G4double GetNdep() const;

    void SetStepLength(G4double value);
    G4double GetStepLength() const;

    void SetFirstPos(const G4ThreeVector& pos);
    const G4ThreeVector& GetFirstPos() const;

    void SetLastPos(const G4ThreeVector& pos);
    const G4ThreeVector& GetLastPos() const;

    void SetMomentumDirection(const G4ThreeVector& dir);
    const G4ThreeVector& GetMomentumDirection() const;

    void SetEkin(G4double value);
    G4double GetEkin() const;

    void SetProcess(const G4String& process);
    const G4String& GetProcess() const;

    void SetVolume(const G4String& volume);
    const G4String& GetVolume() const;

    void SetWeight(G4double value);
    G4double GetWeight() const;

    void SetLETcalc(G4double value);
    G4double GetLETcalc() const;

    void SetLETstep(G4double value);
    G4double GetLETstep() const;

    void SetZ(int z);
    int GetZ() const;

    void SetA(int a);
    int GetA() const;

    HitRecord ToHitRecord() const;

    static ParticleHit* FromStep(const G4Step* step, int eventID = -1);

private:
    int eventID_ = -1;
    int trackID_ = -1;
    int parentID_ = -1;

    G4String particleName_;
    G4double edep_ = 0.0;
    G4double ndep_ = 0.0;
    G4double stepLength_ = 0.0;

    G4ThreeVector firstPosition_;
    G4ThreeVector lastPosition_;
    G4ThreeVector momentumDirection_;

    G4double kineticEnergy_ = 0.0;

    G4String processName_;
    G4String volumeName_;

    G4double weight_ = 1.0;

    G4double LETcalc_ = 0.0;
    G4double LETstep_ = 0.0;

    int z_ = 0;
    int a_ = 0;
};

extern G4ThreadLocal G4Allocator<ParticleHit>* ParticleHitAllocator;
