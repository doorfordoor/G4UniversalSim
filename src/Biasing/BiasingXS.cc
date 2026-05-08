#include "Biasing/BiasingXS.hh"

#include "Utils/StringUtils.hh"

#include "G4BOptnChangeCrossSection.hh"
#include "G4BiasingProcessInterface.hh"
#include "G4Exception.hh"
#include "G4ParticleDefinition.hh"
#include "G4ParticleTable.hh"
#include "G4Track.hh"
#include "G4VParticleChange.hh"
#include "G4VProcess.hh"
#include "G4ios.hh"

#include <cfloat>
#include <stdexcept>

namespace {

XSBiasRule NormalizeRule(XSBiasRule rule)
{
    rule.particleName = StringUtils::Trim(rule.particleName);
    if (rule.name.empty()) rule.name = "xs_" + StringUtils::ToLower(rule.particleName);
    if (rule.applyToSecondaries) rule.onlyPrimary = false;
    if (rule.onlyPrimary) rule.applyToSecondaries = false;
    for (std::string& process : rule.processNames) process = StringUtils::Trim(process);
    rule.Validate();
    return rule;
}

G4String OperatorNameFor(const std::string& particleName)
{
    return G4String("AIHL_XS_") + G4String(StringUtils::Trim(particleName));
}

} // namespace

BiasingXS::BiasingXS(const XSBiasRule& rule)
    : G4VBiasingOperator(OperatorNameFor(rule.particleName))
{
    SetRule(rule);
}

BiasingXS::BiasingXS(const G4String& particleName, G4double factor)
    : G4VBiasingOperator(G4String("AIHL_XS_") + particleName)
{
    XSBiasRule rule;
    rule.name = "xs_" + StringUtils::ToLower(std::string(particleName));
    rule.particleName = particleName;
    rule.factor = factor;
    SetRule(rule);
}

BiasingXS::~BiasingXS() = default;

void BiasingXS::SetRule(const XSBiasRule& rule)
{
    rule_ = NormalizeRule(rule);
    particleName_ = rule_.particleName;
    factor_ = rule_.factor;
    processNames_ = rule_.processNames;
    onlyPrimary_ = rule_.onlyPrimary;
    applyToSecondaries_ = rule_.applyToSecondaries;
    minWeight_ = rule_.minWeight;
    maxInteractions_ = rule_.maxInteractions;
    operations_.clear();
}

const XSBiasRule& BiasingXS::GetRule() const
{
    return rule_;
}

void BiasingXS::SetXSBiasFactor(G4double factor)
{
    if (factor <= 0.0) {
        throw std::runtime_error("BiasingXS::SetXSBiasFactor failed for particle '" +
                                 std::string(particleName_) + "': factor must be > 0");
    }
    factor_ = factor;
    rule_.factor = factor;
}

G4double BiasingXS::GetXSBiasFactor() const
{
    return factor_;
}

void BiasingXS::SetProcessNames(const std::vector<std::string>& names)
{
    processNames_.clear();
    for (const auto& name : names) {
        const auto trimmed = StringUtils::Trim(name);
        if (!trimmed.empty()) processNames_.push_back(trimmed);
    }
    rule_.processNames = processNames_;
}

const std::vector<std::string>& BiasingXS::GetProcessNames() const
{
    return processNames_;
}

void BiasingXS::SetOnlyPrimary(G4bool value)
{
    onlyPrimary_ = value;
    if (value) applyToSecondaries_ = false;
    rule_.onlyPrimary = onlyPrimary_;
    rule_.applyToSecondaries = applyToSecondaries_;
}

G4bool BiasingXS::GetOnlyPrimary() const
{
    return onlyPrimary_;
}

void BiasingXS::SetApplyToSecondaries(G4bool value)
{
    applyToSecondaries_ = value;
    if (value) onlyPrimary_ = false;
    rule_.onlyPrimary = onlyPrimary_;
    rule_.applyToSecondaries = applyToSecondaries_;
}

G4bool BiasingXS::GetApplyToSecondaries() const
{
    return applyToSecondaries_;
}

void BiasingXS::SetMinWeight(G4double value)
{
    if (value <= 0.0) {
        throw std::runtime_error("BiasingXS::SetMinWeight failed for particle '" +
                                 std::string(particleName_) + "': minWeight must be > 0");
    }
    minWeight_ = value;
    rule_.minWeight = value;
}

G4double BiasingXS::GetMinWeight() const
{
    return minWeight_;
}

void BiasingXS::SetMaxInteractions(G4int value)
{
    if (value < 0) {
        throw std::runtime_error("BiasingXS::SetMaxInteractions failed for particle '" +
                                 std::string(particleName_) + "': maxInteractions must be >= 0");
    }
    maxInteractions_ = value;
    rule_.maxInteractions = value;
}

G4int BiasingXS::GetMaxInteractions() const
{
    return maxInteractions_;
}

const G4String& BiasingXS::GetParticleName() const
{
    return particleName_;
}

void BiasingXS::StartRun()
{
    auto* particle = G4ParticleTable::GetParticleTable()->FindParticle(particleName_);
    if (!particle) {
        throw std::runtime_error("BiasingXS::StartRun failed: particle '" +
                                 std::string(particleName_) + "' was not found in G4ParticleTable");
    }
}

void BiasingXS::StartTracking(const G4Track*)
{
    currentTrackBiasInteractions_ = 0;
}

G4VBiasingOperation* BiasingXS::ProposeOccurenceBiasingOperation(
    const G4Track* track,
    const G4BiasingProcessInterface* callingProcess)
{
    if (!ShouldBiasTrack(track) || !callingProcess || !callingProcess->GetWrappedProcess()) {
        return nullptr;
    }

    const G4String processName = callingProcess->GetWrappedProcess()->GetProcessName();
    if (!IsTargetProcess(processName)) return nullptr;

    const G4double analogInteractionLength =
        callingProcess->GetWrappedProcess()->GetCurrentInteractionLength();
    if (analogInteractionLength <= 0.0 || analogInteractionLength > DBL_MAX / 10.0) {
        return nullptr;
    }

    const G4double analogXS = 1.0 / analogInteractionLength;
    G4BOptnChangeCrossSection* operation = GetOrCreateOperation(processName);
    G4VBiasingOperation* previousOperation =
        callingProcess->GetPreviousOccurenceBiasingOperation();

    if (!previousOperation) {
        operation->SetBiasedCrossSection(factor_ * analogXS);
        operation->Sample();
    } else {
        if (previousOperation != operation) {
            G4Exception(
                "BiasingXS::ProposeOccurenceBiasingOperation",
                "AIHLBiasingXS001",
                JustWarning,
                "Previous occurrence operation differs from this process operation; skipping bias for this step.");
            return nullptr;
        }

        if (operation->GetInteractionOccured()) {
            operation->SetBiasedCrossSection(factor_ * analogXS);
            operation->Sample();
        } else {
            operation->UpdateForStep(callingProcess->GetPreviousStepSize());
            operation->SetBiasedCrossSection(factor_ * analogXS);
            operation->UpdateForStep(0.0);
        }
    }

    return operation;
}

G4VBiasingOperation* BiasingXS::ProposeFinalStateBiasingOperation(
    const G4Track*,
    const G4BiasingProcessInterface*)
{
    return nullptr;
}

G4VBiasingOperation* BiasingXS::ProposeNonPhysicsBiasingOperation(
    const G4Track*,
    const G4BiasingProcessInterface*)
{
    return nullptr;
}

void BiasingXS::OperationApplied(
    const G4BiasingProcessInterface* callingProcess,
    G4BiasingAppliedCase,
    G4VBiasingOperation* occurenceOperationApplied,
    G4double,
    G4VBiasingOperation*,
    const G4VParticleChange*)
{
    if (!callingProcess || !callingProcess->GetWrappedProcess()) return;

    const G4String processName = callingProcess->GetWrappedProcess()->GetProcessName();
    auto iter = operations_.find(processName);
    if (iter != operations_.end() && iter->second.get() == occurenceOperationApplied) {
        iter->second->SetInteractionOccured();
        ++currentTrackBiasInteractions_;
    }
}

bool BiasingXS::IsTargetProcess(const G4String& processName) const
{
    if (processNames_.empty()) return true;
    const auto trimmed = StringUtils::Trim(std::string(processName));
    for (const auto& target : processNames_) {
        if (StringUtils::Trim(target) == trimmed) return true;
    }
    return false;
}

bool BiasingXS::ShouldBiasTrack(const G4Track* track) const
{
    if (!track || !track->GetDefinition()) return false;
    if (track->GetDefinition()->GetParticleName() != particleName_) return false;

    const bool secondary = track->GetParentID() != 0;
    if (onlyPrimary_ && secondary) return false;
    if (!applyToSecondaries_ && secondary) return false;
    if (track->GetWeight() < minWeight_) return false;
    if (maxInteractions_ > 0 && currentTrackBiasInteractions_ >= maxInteractions_) return false;
    return true;
}

G4BOptnChangeCrossSection* BiasingXS::GetOrCreateOperation(const G4String& processName)
{
    auto iter = operations_.find(processName);
    if (iter != operations_.end()) return iter->second.get();

    const G4String operationName =
        G4String("AIHL_XSChange_") + particleName_ + G4String("_") + processName;
    auto operation = std::make_unique<G4BOptnChangeCrossSection>(operationName);
    auto* raw = operation.get();
    operations_[processName] = std::move(operation);
    return raw;
}
