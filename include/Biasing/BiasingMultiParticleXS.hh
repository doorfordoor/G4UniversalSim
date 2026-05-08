#pragma once

#include "Biasing/BiasingConfig.hh"
#include "Biasing/BiasingXS.hh"

#include "G4VBiasingOperator.hh"
#include "globals.hh"

#include <map>
#include <memory>
#include <string>

class G4BiasingProcessInterface;
class G4LogicalVolume;
class G4Track;
class G4VBiasingOperation;
class G4VParticleChange;

// Volume-level operator attached to a logical volume. It dispatches each track
// to the per-particle BiasingXS operator that owns the cross-section operation.
class BiasingMultiParticleXS : public G4VBiasingOperator {
public:
    explicit BiasingMultiParticleXS(const G4String& name);
    ~BiasingMultiParticleXS() override;

    void AddParticle(const XSBiasRule& rule);
    void AddParticle(const G4String& particleName, G4double factor);
    bool HasParticle(const G4String& particleName) const;
    void ClearParticles();

    void SetOnlyPrimary(G4bool value);
    void SetApplyToSecondaries(G4bool value);
    void SetMinWeight(G4double value);
    void SetMaxInteractions(G4int value);

    void AttachToVolume(G4LogicalVolume* logicalVolume);

    void StartRun() override;
    void StartTracking(const G4Track* track) override;

    G4VBiasingOperation* ProposeOccurenceBiasingOperation(
        const G4Track* track,
        const G4BiasingProcessInterface* callingProcess) override;

    G4VBiasingOperation* ProposeFinalStateBiasingOperation(
        const G4Track* track,
        const G4BiasingProcessInterface* callingProcess) override;

    G4VBiasingOperation* ProposeNonPhysicsBiasingOperation(
        const G4Track* track,
        const G4BiasingProcessInterface* callingProcess) override;

    void OperationApplied(
        const G4BiasingProcessInterface* callingProcess,
        G4BiasingAppliedCase biasingCase,
        G4VBiasingOperation* occurenceOperationApplied,
        G4double weightForOccurenceInteraction,
        G4VBiasingOperation* finalStateOperationApplied,
        const G4VParticleChange* particleChangeProduced) override;

    void PrintSummary() const;

private:
    std::string NormalizeParticleKey(const G4String& particleName) const;

    std::map<std::string, std::unique_ptr<BiasingXS>> particleOperators_;
    BiasingXS* currentOperator_ = nullptr;
    G4LogicalVolume* attachedLogicalVolume_ = nullptr;
};
