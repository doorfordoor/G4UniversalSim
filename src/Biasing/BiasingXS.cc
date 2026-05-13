#include "Biasing/BiasingXS.hh"

#include "Utils/StringUtils.hh"

#include "G4BOptnChangeCrossSection.hh"
#include "G4BiasingProcessInterface.hh"
#include "G4Exception.hh"
#include "G4ParticleDefinition.hh"
#include "G4ParticleTable.hh"
#include "G4ProcessManager.hh"
#include "G4Track.hh"
#include "G4VParticleChange.hh"
#include "G4VProcess.hh"
#include "G4ios.hh"

#include <algorithm>
#include <cfloat>
#include <set>
#include <stdexcept>

namespace {

XSBiasRule NormalizeLegacyRule(XSBiasRule rule)
{
    rule.particleName = StringUtils::Trim(rule.particleName);
    if (rule.name.empty()) rule.name = "xs_legacy_" + StringUtils::ToLower(rule.particleName);
    if (rule.applyToSecondaries) rule.onlyPrimary = false;
    if (rule.onlyPrimary) rule.applyToSecondaries = false;
    for (std::string& process : rule.processNames) process = StringUtils::Trim(process);
    rule.Validate();
    return rule;
}

XSProcessBiasRule NormalizeProcessRule(XSProcessBiasRule rule)
{
    rule.particleName = StringUtils::Trim(rule.particleName);
    rule.processName = StringUtils::Trim(rule.processName);
    if (rule.name.empty()) rule.name = "xs_" + rule.particleName + "_" + rule.processName;
    if (rule.applyToSecondaries) rule.onlyPrimary = false;
    if (rule.onlyPrimary) rule.applyToSecondaries = false;
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

BiasingXS::BiasingXS(const XSProcessBiasRule& rule)
    : G4VBiasingOperator(OperatorNameFor(rule.particleName))
{
    particleName_ = StringUtils::Trim(rule.particleName);
    AddProcessRule(rule);
}

BiasingXS::BiasingXS(const G4String& particleName, G4double factor)
    : G4VBiasingOperator(G4String("AIHL_XS_") + particleName)
{
    XSBiasRule rule;
    rule.name = "xs_legacy_" + StringUtils::ToLower(std::string(particleName));
    rule.particleName = particleName;
    rule.factor = factor;
    SetRule(rule);
}

BiasingXS::~BiasingXS() = default;

void BiasingXS::AddProcessRule(const XSProcessBiasRule& rule)
{
    XSProcessBiasRule copy = NormalizeProcessRule(rule);
    if (!particleName_.empty() && StringUtils::ToLower(std::string(particleName_)) != StringUtils::ToLower(copy.particleName)) {
        throw std::runtime_error("BiasingXS::AddProcessRule failed: operator particle '" +
            std::string(particleName_) + "' does not match rule particle '" + copy.particleName + "'");
    }
    particleName_ = copy.particleName;
    processRules_[NormalizeProcessKey(copy.processName)] = copy;

    // Keep legacy accessors meaningful by mirroring the latest rule.
    factor_ = copy.factor;
    onlyPrimary_ = copy.onlyPrimary;
    applyToSecondaries_ = copy.applyToSecondaries;
    minWeight_ = copy.minWeight;
    maxInteractions_ = copy.maxInteractions;
    if (std::find(processNames_.begin(), processNames_.end(), copy.processName) == processNames_.end()) {
        processNames_.push_back(copy.processName);
    }
}

bool BiasingXS::HasProcessRule(const std::string& processName) const
{
    return processRules_.find(NormalizeProcessKey(processName)) != processRules_.end();
}

std::vector<XSProcessBiasRule> BiasingXS::GetProcessRules() const
{
    std::vector<XSProcessBiasRule> rules;
    for (const auto& item : processRules_) rules.push_back(item.second);
    return rules;
}

void BiasingXS::SetRule(const XSBiasRule& rule)
{
    rule_ = NormalizeLegacyRule(rule);
    particleName_ = rule_.particleName;
    factor_ = rule_.factor;
    processNames_ = rule_.processNames;
    onlyPrimary_ = rule_.onlyPrimary;
    applyToSecondaries_ = rule_.applyToSecondaries;
    minWeight_ = rule_.minWeight;
    maxInteractions_ = rule_.maxInteractions;
    operations_.clear();
    processRules_.clear();

    for (const std::string& processName : rule_.processNames) {
        const std::string process = StringUtils::Trim(processName);
        if (process.empty()) continue;
        XSProcessBiasRule processRule;
        processRule.name = rule_.name + "_" + process;
        processRule.particleName = rule_.particleName;
        processRule.processName = process;
        processRule.factor = rule_.factor;
        processRule.volumeNames = rule_.volumeNames;
        processRule.onlyPrimary = rule_.onlyPrimary;
        processRule.applyToSecondaries = rule_.applyToSecondaries;
        if (processRule.applyToSecondaries) processRule.onlyPrimary = false;
        if (processRule.onlyPrimary) processRule.applyToSecondaries = false;
        processRule.minWeight = rule_.minWeight;
        processRule.maxInteractions = rule_.maxInteractions;
        processRule.enabled = rule_.enabled;
        processRule.legacyGenerated = true;
        AddProcessRule(processRule);
    }
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
    for (auto& item : processRules_) item.second.factor = factor;
}

G4double BiasingXS::GetXSBiasFactor() const
{
    return factor_;
}

void BiasingXS::SetProcessNames(const std::vector<std::string>& names)
{
    processNames_.clear();
    processRules_.clear();
    for (const auto& name : names) {
        const auto trimmed = StringUtils::Trim(name);
        if (trimmed.empty()) continue;
        processNames_.push_back(trimmed);

        XSProcessBiasRule rule;
        rule.name = "xs_" + std::string(particleName_) + "_" + trimmed;
        rule.particleName = particleName_;
        rule.processName = trimmed;
        rule.factor = factor_;
        rule.onlyPrimary = onlyPrimary_;
        rule.applyToSecondaries = applyToSecondaries_;
        rule.minWeight = minWeight_;
        rule.maxInteractions = maxInteractions_;
        rule.legacyGenerated = true;
        AddProcessRule(rule);
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
    for (auto& item : processRules_) {
        item.second.onlyPrimary = onlyPrimary_;
        item.second.applyToSecondaries = applyToSecondaries_;
    }
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
    for (auto& item : processRules_) {
        item.second.onlyPrimary = onlyPrimary_;
        item.second.applyToSecondaries = applyToSecondaries_;
    }
}

G4bool BiasingXS::GetApplyToSecondaries() const
{
    return applyToSecondaries_;
}

void BiasingXS::SetMinWeight(G4double value)
{
    if (value < 0.0) {
        throw std::runtime_error("BiasingXS::SetMinWeight failed for particle '" +
                                 std::string(particleName_) + "': minWeight must be >= 0");
    }
    minWeight_ = value;
    rule_.minWeight = value;
    for (auto& item : processRules_) item.second.minWeight = value;
}

G4double BiasingXS::GetMinWeight() const
{
    return minWeight_;
}

void BiasingXS::SetMaxInteractions(G4int value)
{
    if (value < -1) {
        throw std::runtime_error("BiasingXS::SetMaxInteractions failed for particle '" +
                                 std::string(particleName_) + "': maxInteractions must be -1 or >= 0");
    }
    maxInteractions_ = value;
    rule_.maxInteractions = value;
    for (auto& item : processRules_) item.second.maxInteractions = value;
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
    ValidateProcessRulesForParticle();
}

void BiasingXS::StartTracking(const G4Track*)
{
    currentTrackBiasInteractions_ = 0;
    currentTrackBiasInteractionsByProcess_.clear();
}

G4VBiasingOperation* BiasingXS::ProposeOccurenceBiasingOperation(
    const G4Track* track,
    const G4BiasingProcessInterface* callingProcess)
{
    if (!callingProcess || !callingProcess->GetWrappedProcess()) return nullptr;

    const G4String processName = callingProcess->GetWrappedProcess()->GetProcessName();
    const XSProcessBiasRule* rule = FindProcessRule(processName);
    if (!rule) return nullptr;
    if (!ShouldBiasTrack(track, *rule, processName)) return nullptr;

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
        operation->SetBiasedCrossSection(rule->factor * analogXS);
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
            operation->SetBiasedCrossSection(rule->factor * analogXS);
            operation->Sample();
        } else {
            operation->UpdateForStep(callingProcess->GetPreviousStepSize());
            operation->SetBiasedCrossSection(rule->factor * analogXS);
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
        ++currentTrackBiasInteractionsByProcess_[NormalizeProcessKey(std::string(processName))];
    }
}

std::string BiasingXS::NormalizeProcessKey(const std::string& processName)
{
    return StringUtils::Trim(processName);
}

const XSProcessBiasRule* BiasingXS::FindProcessRule(const G4String& processName) const
{
    const auto iter = processRules_.find(NormalizeProcessKey(std::string(processName)));
    return iter == processRules_.end() ? nullptr : &iter->second;
}

void BiasingXS::ValidateProcessRulesForParticle() const
{
    auto* particle = G4ParticleTable::GetParticleTable()->FindParticle(particleName_);
    if (!particle) {
        throw std::runtime_error("BiasingXS::StartRun failed: particle '" +
                                 std::string(particleName_) + "' was not found in G4ParticleTable");
    }

    auto* processManager = particle->GetProcessManager();
    if (!processManager) {
        throw std::runtime_error("BiasingXS::StartRun failed: particle '" +
                                 std::string(particleName_) + "' has no process manager");
    }

    std::set<std::string> processNames;
    auto* processList = processManager->GetProcessList();
    if (processList) {
        for (G4int i = 0; i < static_cast<G4int>(processList->size()); ++i) {
            G4VProcess* process = (*processList)[i];
            if (!process) continue;
            processNames.insert(StringUtils::Trim(std::string(process->GetProcessName())));
            auto* biasingProcess = dynamic_cast<G4BiasingProcessInterface*>(process);
            if (biasingProcess && biasingProcess->GetWrappedProcess()) {
                processNames.insert(StringUtils::Trim(std::string(biasingProcess->GetWrappedProcess()->GetProcessName())));
            }
        }
    }

    for (const auto& item : processRules_) {
        const XSProcessBiasRule& rule = item.second;
        if (!rule.enabled) continue;
        if (processNames.find(rule.processName) == processNames.end()) {
            std::ostringstream message;
            message << "Configured XS bias process '" << rule.processName
                    << "' was not found for particle '" << rule.particleName
                    << "'. The rule will not bias any process unless the selected physics list "
                    << "later exposes a matching wrapped process name. Available processes:";
            for (const auto& processName : processNames) {
                message << ' ' << processName;
            }
            G4Exception(
                "BiasingXS::StartRun",
                "AIHLBiasingXSProcess001",
                JustWarning,
                message.str().c_str());
        }
    }

    if (particle->GetPDGCharge() != 0.0 && !processRules_.empty()) {
        G4Exception(
            "BiasingXS::StartRun",
            "AIHLBiasingXSCharged001",
            JustWarning,
            ("XS biasing for charged particle '" + std::string(particleName_)
             + "' may require special validation because cross sections can vary during a step due to energy loss. Validate results carefully.").c_str());
    }
}

bool BiasingXS::ShouldBiasTrack(const G4Track* track, const XSProcessBiasRule& rule, const G4String& processName) const
{
    if (!track || !track->GetDefinition()) return false;
    if (track->GetDefinition()->GetParticleName() != particleName_) return false;

    const bool secondary = track->GetParentID() != 0;
    if (rule.onlyPrimary && secondary) return false;
    if (!rule.applyToSecondaries && secondary) return false;
    if (track->GetWeight() < rule.minWeight) return false;
    const auto countIter = currentTrackBiasInteractionsByProcess_.find(NormalizeProcessKey(std::string(processName)));
    const G4int count = countIter == currentTrackBiasInteractionsByProcess_.end() ? 0 : countIter->second;
    if (rule.maxInteractions >= 0 && count >= rule.maxInteractions) return false;
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
