#pragma once
#include "Scoring/PhaseSpace.hh"
class G4Track;
class G4Step;
class G4StepPoint;
class G4PrimaryParticle;
class G4ParticleDefinition;
namespace phase_space_replay {
enum class RestoreResult { NotMarked, Restored, AlreadyRestored };
PhaseSpaceDynamicState CaptureDynamicState(const G4Track&, const G4StepPoint&);
void ValidateForDefinition(const PhaseSpaceParticle&, const G4ParticleDefinition&, const std::string& file);
void AttachPrimaryState(G4PrimaryParticle&, const PhaseSpaceParticle&, const std::string& file);
RestoreResult RestoreBeforeTracking(G4Track&);
void ObserveFirstStep(const G4Step&);
}
