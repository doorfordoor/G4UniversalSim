#pragma once

#include "Biasing/BiasingConfig.hh"

#include "G4VBiasingOperator.hh"
#include "globals.hh"

#include <map>
#include <memory>
#include <string>
#include <vector>

class G4BOptnChangeCrossSection;
class G4BiasingProcessInterface;
class G4Track;
class G4VBiasingOperation;
class G4VParticleChange;

// Single-particle cross-section biasing operator. It owns only biasing
// operations and data copied from XSBiasRule; geometry attachment is handled
// by BiasingMultiParticleXS/BiasingManager.
class BiasingXS : public G4VBiasingOperator {
public:
    explicit BiasingXS(const XSBiasRule& rule);
    BiasingXS(const G4String& particleName, G4double factor = 1.0);
    ~BiasingXS() override;

    void SetRule(const XSBiasRule& rule);
    const XSBiasRule& GetRule() const;

    void SetXSBiasFactor(G4double factor);
    G4double GetXSBiasFactor() const;

    void SetProcessNames(const std::vector<std::string>& names);
    const std::vector<std::string>& GetProcessNames() const;

    void SetOnlyPrimary(G4bool value);
    G4bool GetOnlyPrimary() const;

    void SetApplyToSecondaries(G4bool value);
    G4bool GetApplyToSecondaries() const;

    void SetMinWeight(G4double value);
    G4double GetMinWeight() const;

    void SetMaxInteractions(G4int value);
    G4int GetMaxInteractions() const;

    const G4String& GetParticleName() const;

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

private:
    bool IsTargetProcess(const G4String& processName) const;
    bool ShouldBiasTrack(const G4Track* track) const;
    G4BOptnChangeCrossSection* GetOrCreateOperation(const G4String& processName);

    XSBiasRule rule_;
    G4String particleName_;
    G4double factor_ = 1.0;
    std::vector<std::string> processNames_;
    G4bool onlyPrimary_ = true;
    G4bool applyToSecondaries_ = false;
    G4double minWeight_ = 0.05;
    G4int maxInteractions_ = 5;
    G4int currentTrackBiasInteractions_ = 0;

    std::map<G4String, std::unique_ptr<G4BOptnChangeCrossSection>> operations_;
};
