#include "Biasing/BiasingMultiParticleXS.hh"

#include "Utils/StringUtils.hh"

#include "G4LogicalVolume.hh"
#include "G4ParticleDefinition.hh"
#include "G4ParticleTable.hh"
#include "G4Track.hh"
#include "G4ios.hh"

#include <stdexcept>

BiasingMultiParticleXS::BiasingMultiParticleXS(const G4String& name)
    : G4VBiasingOperator(name)
{
}

BiasingMultiParticleXS::~BiasingMultiParticleXS() = default;

void BiasingMultiParticleXS::AddParticle(const XSBiasRule& rule)
{
    const G4String particleName(rule.particleName);
    if (!G4ParticleTable::GetParticleTable()->FindParticle(particleName)) {
        throw std::runtime_error("BiasingMultiParticleXS::AddParticle failed: particle '" +
                                 rule.particleName + "' was not found in G4ParticleTable");
    }

    particleOperators_[NormalizeParticleKey(particleName)] = std::make_unique<BiasingXS>(rule);
}

void BiasingMultiParticleXS::AddParticle(const G4String& particleName, G4double factor)
{
    XSBiasRule rule;
    rule.name = "xs_" + StringUtils::ToLower(std::string(particleName));
    rule.particleName = particleName;
    rule.factor = factor;
    AddParticle(rule);
}

bool BiasingMultiParticleXS::HasParticle(const G4String& particleName) const
{
    return particleOperators_.find(NormalizeParticleKey(particleName)) != particleOperators_.end();
}

void BiasingMultiParticleXS::ClearParticles()
{
    currentOperator_ = nullptr;
    particleOperators_.clear();
}

void BiasingMultiParticleXS::SetOnlyPrimary(G4bool value)
{
    for (auto& item : particleOperators_) item.second->SetOnlyPrimary(value);
}

void BiasingMultiParticleXS::SetApplyToSecondaries(G4bool value)
{
    for (auto& item : particleOperators_) item.second->SetApplyToSecondaries(value);
}

void BiasingMultiParticleXS::SetMinWeight(G4double value)
{
    for (auto& item : particleOperators_) item.second->SetMinWeight(value);
}

void BiasingMultiParticleXS::SetMaxInteractions(G4int value)
{
    for (auto& item : particleOperators_) item.second->SetMaxInteractions(value);
}

void BiasingMultiParticleXS::AttachToVolume(G4LogicalVolume* logicalVolume)
{
    if (!logicalVolume) {
        throw std::runtime_error("BiasingMultiParticleXS::AttachToVolume failed: logicalVolume is null");
    }
    AttachTo(logicalVolume);
    attachedLogicalVolume_ = logicalVolume;
}

void BiasingMultiParticleXS::StartRun()
{
    for (auto& item : particleOperators_) item.second->StartRun();
}

void BiasingMultiParticleXS::StartTracking(const G4Track* track)
{
    currentOperator_ = nullptr;
    if (!track || !track->GetDefinition()) return;

    const auto key = NormalizeParticleKey(track->GetDefinition()->GetParticleName());
    auto iter = particleOperators_.find(key);
    if (iter == particleOperators_.end()) return;

    currentOperator_ = iter->second.get();
    currentOperator_->StartTracking(track);
}

G4VBiasingOperation* BiasingMultiParticleXS::ProposeOccurenceBiasingOperation(
    const G4Track* track,
    const G4BiasingProcessInterface* callingProcess)
{
    if (!currentOperator_) return nullptr;
    return currentOperator_->GetProposedOccurenceBiasingOperation(track, callingProcess);
}

G4VBiasingOperation* BiasingMultiParticleXS::ProposeFinalStateBiasingOperation(
    const G4Track* track,
    const G4BiasingProcessInterface* callingProcess)
{
    if (!currentOperator_) return nullptr;
    return currentOperator_->GetProposedFinalStateBiasingOperation(track, callingProcess);
}

G4VBiasingOperation* BiasingMultiParticleXS::ProposeNonPhysicsBiasingOperation(
    const G4Track* track,
    const G4BiasingProcessInterface* callingProcess)
{
    if (!currentOperator_) return nullptr;
    return currentOperator_->GetProposedNonPhysicsBiasingOperation(track, callingProcess);
}

void BiasingMultiParticleXS::OperationApplied(
    const G4BiasingProcessInterface* callingProcess,
    G4BiasingAppliedCase biasingCase,
    G4VBiasingOperation* occurenceOperationApplied,
    G4double weightForOccurenceInteraction,
    G4VBiasingOperation* finalStateOperationApplied,
    const G4VParticleChange* particleChangeProduced)
{
    if (!currentOperator_) return;
    currentOperator_->ReportOperationApplied(
        callingProcess,
        biasingCase,
        occurenceOperationApplied,
        weightForOccurenceInteraction,
        finalStateOperationApplied,
        particleChangeProduced);
}

void BiasingMultiParticleXS::PrintSummary() const
{
    G4cout << "[BiasingMultiParticleXS] name=" << GetName()
           << ", attachedLV=" << (attachedLogicalVolume_ ? attachedLogicalVolume_->GetName() : G4String("<none>"))
           << ", particles=" << particleOperators_.size() << G4endl;
    for (const auto& item : particleOperators_) {
        G4cout << "  - " << item.second->GetParticleName()
               << " factor=" << item.second->GetXSBiasFactor() << G4endl;
    }
}

std::string BiasingMultiParticleXS::NormalizeParticleKey(const G4String& particleName) const
{
    return StringUtils::ToLower(StringUtils::Trim(std::string(particleName)));
}
