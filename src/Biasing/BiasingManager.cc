#include "Biasing/BiasingManager.hh"

#include "Biasing/BiasingMultiParticleXS.hh"
#include "Biasing/BiasingXS.hh"
#include "Config/ConfigManager.hh"
#include "Geometry/GeometryRegistry.hh"
#include "Utils/StringUtils.hh"

#include "G4LogicalVolume.hh"
#include "G4AutoDelete.hh"
#include "G4Threading.hh"

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>

namespace {

std::string MakeLegacyRuleName(const std::string& particleName)
{
    return "xs_legacy_" + StringUtils::ToLower(StringUtils::Trim(particleName));
}

std::string MakeProcessRuleName(const std::string& particleName, const std::string& processName)
{
    return "xs_" + StringUtils::Trim(particleName) + "_" + StringUtils::Trim(processName);
}

std::string NormalizeVolumeKey(const std::string& volumeName)
{
    return StringUtils::ToLower(StringUtils::Trim(volumeName));
}

bool ContainsVolumeName(const std::vector<std::string>& names, const std::string& volumeName)
{
    const auto key = NormalizeVolumeKey(volumeName);
    return std::any_of(names.begin(), names.end(), [&](const std::string& item) {
        return NormalizeVolumeKey(item) == key;
    });
}

std::string Join(const std::vector<std::string>& values, const std::string& emptyText = "<none>")
{
    if (values.empty()) return emptyText;
    std::string result;
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i > 0) result += ",";
        result += values[i];
    }
    return result;
}

std::vector<std::string> SplitSectionName(const std::string& section)
{
    return StringUtils::Split(section, '.', true);
}

}  // namespace

struct BiasingManager::ThreadState {
    std::vector<std::unique_ptr<BiasingMultiParticleXS>> owned;
    std::vector<BiasingMultiParticleXS*> active;
    std::vector<G4LogicalVolume*> targets;
    std::string failure;
    WorkerEvidence current;
};

BiasingManager::BiasingManager() = default;
BiasingManager::~BiasingManager() = default;

void BiasingManager::Enable(bool enable)
{
    if (enable && interactiveSessionMode_) {
        throw std::runtime_error("XS biasing is not supported in an interactive session because geometry reinitialization can invalidate attached operators. Use a batch macro in a fresh process instead.");
    }
    config_.enabled = enable;
}

bool BiasingManager::IsEnabled() const
{
    return config_.enabled;
}

void BiasingManager::SetInteractiveSessionMode(bool interactive)
{
    if (interactive && IsEnabled()) {
        throw std::runtime_error("XS biasing is not supported in an interactive session because geometry reinitialization can invalidate attached operators. Use a batch macro in a fresh process instead.");
    }
    interactiveSessionMode_ = interactive;
}

bool BiasingManager::IsInteractiveSessionMode() const
{
    return interactiveSessionMode_;
}

void BiasingManager::RecordInteractiveReject(const std::string& command, const std::string& message)
{
    ++interactiveRejectCount_;
    lastInteractiveReject_ = command.empty() ? message : command + ": " + message;
}

std::size_t BiasingManager::GetInteractiveRejectCount() const
{
    return interactiveRejectCount_;
}

const std::string& BiasingManager::GetLastInteractiveReject() const
{
    return lastInteractiveReject_;
}

void BiasingManager::Clear()
{
    ClearOperators();
    config_.Clear();
    globalBiasVolumes_.clear();
    legacyWarningEmitted_ = false;
    legacyDetailWarnings_.clear();
}

void BiasingManager::AddXSProcessBiasRule(const XSProcessBiasRule& rule)
{
    XSProcessBiasRule copy = rule;
    copy.particleName = TrimRequired(copy.particleName, "particleName");
    copy.processName = TrimRequired(copy.processName, "processName");
    if (copy.applyToSecondaries) copy.onlyPrimary = false;
    if (copy.onlyPrimary) copy.applyToSecondaries = false;
    if (copy.name.empty()) copy.name = MakeProcessRuleName(copy.particleName, copy.processName);
    copy.Validate();
    config_.AddProcessRule(copy);
}

XSProcessBiasRule& BiasingManager::CreateOrGetXSProcessBiasRule(
    const std::string& particleName,
    const std::string& processName)
{
    const std::string particle = TrimRequired(particleName, "particleName");
    const std::string process = TrimRequired(processName, "processName");
    const std::string key = ProcessRuleKey(particle, process);
    for (XSProcessBiasRule& rule : config_.xsProcessRules) {
        if (ProcessRuleKey(rule.particleName, rule.processName) == key) return rule;
    }

    XSProcessBiasRule rule;
    rule.name = MakeProcessRuleName(particle, process);
    rule.particleName = particle;
    rule.processName = process;
    rule.volumeNames = globalBiasVolumes_;
    config_.xsProcessRules.push_back(rule);
    return config_.xsProcessRules.back();
}

bool BiasingManager::HasXSProcessBiasRule(
    const std::string& particleName,
    const std::string& processName) const
{
    const std::string key = ProcessRuleKey(particleName, processName);
    return std::any_of(config_.xsProcessRules.begin(), config_.xsProcessRules.end(), [&](const XSProcessBiasRule& rule) {
        return ProcessRuleKey(rule.particleName, rule.processName) == key;
    });
}

const XSProcessBiasRule& BiasingManager::GetXSProcessBiasRule(
    const std::string& particleName,
    const std::string& processName) const
{
    const std::string key = ProcessRuleKey(particleName, processName);
    for (const XSProcessBiasRule& rule : config_.xsProcessRules) {
        if (ProcessRuleKey(rule.particleName, rule.processName) == key) return rule;
    }
    throw std::runtime_error("BiasingManager::GetXSProcessBiasRule not found for particle/process '"
        + particleName + "/" + processName + "'");
}

XSProcessBiasRule& BiasingManager::GetXSProcessBiasRuleMutable(
    const std::string& particleName,
    const std::string& processName)
{
    const std::string key = ProcessRuleKey(particleName, processName);
    for (XSProcessBiasRule& rule : config_.xsProcessRules) {
        if (ProcessRuleKey(rule.particleName, rule.processName) == key) return rule;
    }
    throw std::runtime_error("BiasingManager::GetXSProcessBiasRuleMutable not found for particle/process '"
        + particleName + "/" + processName + "'");
}

const std::vector<XSProcessBiasRule>& BiasingManager::GetXSProcessBiasRules() const
{
    return config_.xsProcessRules;
}

std::vector<XSProcessBiasRule> BiasingManager::GetEnabledXSProcessBiasRules() const
{
    std::vector<XSProcessBiasRule> result;
    for (const XSProcessBiasRule& rule : BuildExpandedProcessRules(false)) {
        if (rule.enabled) result.push_back(rule);
    }
    return result;
}

void BiasingManager::SetXSProcessBiasFactor(
    const std::string& particleName,
    const std::string& processName,
    double factor)
{
    if (factor <= 0.0) throw std::runtime_error("BiasingManager::SetXSProcessBiasFactor factor must be > 0");
    CreateOrGetXSProcessBiasRule(particleName, processName).factor = factor;
}

void BiasingManager::AddXSProcessBiasVolume(
    const std::string& particleName,
    const std::string& processName,
    const std::string& volumeName)
{
    AddUnique(CreateOrGetXSProcessBiasRule(particleName, processName).volumeNames, TrimRequired(volumeName, "volumeName"));
}

void BiasingManager::SetXSProcessOnlyPrimary(
    const std::string& particleName,
    const std::string& processName,
    bool onlyPrimary)
{
    XSProcessBiasRule& rule = CreateOrGetXSProcessBiasRule(particleName, processName);
    rule.onlyPrimary = onlyPrimary;
    if (onlyPrimary) rule.applyToSecondaries = false;
}

void BiasingManager::SetXSProcessApplyToSecondaries(
    const std::string& particleName,
    const std::string& processName,
    bool applyToSecondaries)
{
    XSProcessBiasRule& rule = CreateOrGetXSProcessBiasRule(particleName, processName);
    rule.applyToSecondaries = applyToSecondaries;
    if (applyToSecondaries) rule.onlyPrimary = false;
}

void BiasingManager::SetXSProcessMinWeight(
    const std::string& particleName,
    const std::string& processName,
    double minWeight)
{
    if (minWeight < 0.0) throw std::runtime_error("BiasingManager::SetXSProcessMinWeight minWeight must be >= 0");
    CreateOrGetXSProcessBiasRule(particleName, processName).minWeight = minWeight;
}

void BiasingManager::SetXSProcessMaxInteractions(
    const std::string& particleName,
    const std::string& processName,
    int maxInteractions)
{
    if (maxInteractions < -1) {
        throw std::runtime_error("BiasingManager::SetXSProcessMaxInteractions maxInteractions must be -1 or >= 0");
    }
    CreateOrGetXSProcessBiasRule(particleName, processName).maxInteractions = maxInteractions;
}

void BiasingManager::AddXSBiasRule(const XSBiasRule& rule)
{
    WarnLegacySyntax("AddXSBiasRule");
    XSBiasRule copy = rule;
    copy.particleName = TrimRequired(copy.particleName, "particleName");
    if (copy.applyToSecondaries) copy.onlyPrimary = false;
    if (copy.onlyPrimary) copy.applyToSecondaries = false;
    if (copy.name.empty()) copy.name = MakeLegacyRuleName(copy.particleName);
    copy.legacy = true;
    copy.Validate();

    const std::string key = NormalizeParticleName(copy.particleName);
    for (XSBiasRule& existing : config_.xsRules) {
        if (NormalizeParticleName(existing.particleName) == key) {
            existing = copy;
            return;
        }
    }
    config_.xsRules.push_back(copy);
}

XSBiasRule& BiasingManager::CreateOrGetXSBiasRule(const std::string& particleName)
{
    WarnLegacySyntax("CreateOrGetXSBiasRule");
    const std::string trimmed = TrimRequired(particleName, "particleName");
    const std::string key = NormalizeParticleName(trimmed);
    for (XSBiasRule& rule : config_.xsRules) {
        if (NormalizeParticleName(rule.particleName) == key) return rule;
    }

    XSBiasRule rule;
    rule.name = MakeLegacyRuleName(trimmed);
    rule.particleName = trimmed;
    rule.volumeNames = globalBiasVolumes_;
    rule.legacy = true;
    config_.xsRules.push_back(rule);
    return config_.xsRules.back();
}

void BiasingManager::AddXSBiasParticle(const std::string& particleName)
{
    (void)CreateOrGetXSBiasRule(particleName);
}

void BiasingManager::AddXSBiasProcess(const std::string& particleName, const std::string& processName)
{
    XSBiasRule& rule = CreateOrGetXSBiasRule(particleName);
    AddUnique(rule.processNames, TrimRequired(processName, "processName"));
}

void BiasingManager::AddXSBiasProcess(const std::string& processName)
{
    WarnLegacySyntax("AddXSBiasProcess(process)");
    if (config_.xsRules.empty()) {
        throw std::runtime_error("BiasingManager::AddXSBiasProcess requires AddXSBiasParticle first");
    }
    if (config_.xsRules.size() > 1) {
        throw std::runtime_error("BiasingManager::AddXSBiasProcess is ambiguous with multiple legacy rules; use AddXSBiasProcess(particleName, processName)");
    }
    AddUnique(config_.xsRules.front().processNames, TrimRequired(processName, "processName"));
}

void BiasingManager::SetXSBiasFactor(const std::string& particleName, double factor)
{
    if (factor <= 0.0) throw std::runtime_error("BiasingManager::SetXSBiasFactor factor must be > 0");
    CreateOrGetXSBiasRule(particleName).factor = factor;
}

void BiasingManager::SetOnlyPrimary(const std::string& particleName, bool onlyPrimary)
{
    XSBiasRule& rule = CreateOrGetXSBiasRule(particleName);
    rule.onlyPrimary = onlyPrimary;
    if (onlyPrimary) rule.applyToSecondaries = false;
}

void BiasingManager::SetApplyToSecondaries(const std::string& particleName, bool applyToSecondaries)
{
    XSBiasRule& rule = CreateOrGetXSBiasRule(particleName);
    rule.applyToSecondaries = applyToSecondaries;
    if (applyToSecondaries) rule.onlyPrimary = false;
}

void BiasingManager::SetMinWeight(const std::string& particleName, double minWeight)
{
    if (minWeight < 0.0) throw std::runtime_error("BiasingManager::SetMinWeight minWeight must be >= 0");
    CreateOrGetXSBiasRule(particleName).minWeight = minWeight;
}

void BiasingManager::SetMaxInteractions(const std::string& particleName, int maxInteractions)
{
    if (maxInteractions < -1) throw std::runtime_error("BiasingManager::SetMaxInteractions maxInteractions must be -1 or >= 0");
    CreateOrGetXSBiasRule(particleName).maxInteractions = maxInteractions;
}

void BiasingManager::AddBiasVolume(const std::string& volumeName)
{
    AddUnique(globalBiasVolumes_, TrimRequired(volumeName, "volumeName"));
}

void BiasingManager::AddBiasVolumeForParticle(const std::string& particleName, const std::string& volumeName)
{
    AddUnique(CreateOrGetXSBiasRule(particleName).volumeNames, TrimRequired(volumeName, "volumeName"));
}

bool BiasingManager::HasXSBiasRule(const std::string& particleName) const
{
    const std::string key = NormalizeParticleName(particleName);
    return std::any_of(config_.xsRules.begin(), config_.xsRules.end(), [&](const XSBiasRule& rule) {
        return NormalizeParticleName(rule.particleName) == key;
    });
}

const XSBiasRule& BiasingManager::GetXSBiasRule(const std::string& particleName) const
{
    const std::string key = NormalizeParticleName(particleName);
    for (const XSBiasRule& rule : config_.xsRules) {
        if (NormalizeParticleName(rule.particleName) == key) return rule;
    }
    throw std::runtime_error("BiasingManager::GetXSBiasRule not found for particleName='" + particleName + "'");
}

XSBiasRule& BiasingManager::GetXSBiasRuleMutable(const std::string& particleName)
{
    const std::string key = NormalizeParticleName(particleName);
    for (XSBiasRule& rule : config_.xsRules) {
        if (NormalizeParticleName(rule.particleName) == key) return rule;
    }
    throw std::runtime_error("BiasingManager::GetXSBiasRuleMutable not found for particleName='" + particleName + "'");
}

const std::vector<XSBiasRule>& BiasingManager::GetXSBiasRules() const
{
    return config_.xsRules;
}

std::vector<XSBiasRule> BiasingManager::GetEnabledXSBiasRules() const
{
    return config_.GetEnabledXSRules();
}

std::vector<std::string> BiasingManager::GetBiasedParticles() const
{
    std::vector<std::string> particles;
    for (const XSProcessBiasRule& rule : GetEnabledXSProcessBiasRules()) {
        AddUnique(particles, rule.particleName);
    }
    return particles;
}

std::vector<std::string> BiasingManager::GetBiasedProcesses(const std::string& particleName) const
{
    const std::string key = NormalizeParticleName(particleName);
    std::vector<std::string> processes;
    for (const XSProcessBiasRule& rule : GetEnabledXSProcessBiasRules()) {
        if (NormalizeParticleName(rule.particleName) == key) AddUnique(processes, rule.processName);
    }
    return processes;
}

std::vector<std::string> BiasingManager::GetBiasVolumes() const
{
    std::vector<std::string> volumes = globalBiasVolumes_;
    for (const XSBiasRule& rule : config_.xsRules) {
        for (const std::string& volume : rule.volumeNames) AddUnique(volumes, volume);
    }
    for (const XSProcessBiasRule& rule : BuildExpandedProcessRules(false)) {
        for (const std::string& volume : rule.volumeNames) AddUnique(volumes, volume);
    }
    return volumes;
}

void BiasingManager::Validate() const
{
    config_.Validate();
    for (const XSProcessBiasRule& rule : BuildExpandedProcessRules(true)) {
        if (rule.enabled) rule.Validate();
    }
}

void BiasingManager::PrintSummary() const
{
    const auto expandedRules = BuildExpandedProcessRules(true);
    std::cout << "[BiasingManager] enabled=" << (config_.enabled ? "true" : "false")
              << ", processRules=" << expandedRules.size()
              << ", explicitProcessRules=" << config_.xsProcessRules.size()
              << ", legacyRules=" << config_.xsRules.size()
              << ", operatorsAttached=" << (operatorsAttached_ ? "true" : "false")
              << ", operatorCount=" << xsOperators_.size()
              << ", globalBiasVolumes=" << Join(globalBiasVolumes_, "<none>")
              << '\n';
    if (!config_.xsRules.empty()) {
        for (const XSBiasRule& rule : config_.xsRules) {
            std::cout << "  legacy: " << rule.ToString() << '\n';
        }
    }
    for (const XSProcessBiasRule& rule : expandedRules) {
        std::cout << "  process-rule: " << rule.ToString() << '\n';
    }
}

void BiasingManager::LoadFromConfig(const ConfigManager& config)
{
    Clear();
    if (!config.HasSection("biasing")) {
        Enable(false);
        return;
    }

    Enable(config.GetBool("biasing", "enabled", false));
    if (!IsEnabled()) return;

    // New process-level syntax: [biasing.xs.<particle>.<process>].
    for (const auto& info : config.GetSectionInfo()) {
        const std::string& section = info.section;
        const std::string lower = StringUtils::ToLower(StringUtils::Trim(section));
        if (!StringUtils::StartsWith(lower, "biasing.xs.") || lower == "biasing.xs") continue;
        const auto parts = SplitSectionName(info.originalSection.empty() ? section : info.originalSection);
        if (parts.size() != 4) {
            throw std::runtime_error(
                "BiasingManager::LoadFromConfig failed: section '" + section
                + "' must be [biasing.xs.<particle>.<process>]. Process names containing '.' are not supported yet.");
        }

        XSProcessBiasRule rule;
        rule.particleName = config.GetString(section, "particle", parts[2]);
        rule.processName = config.GetString(section, "process", parts[3]);
        if (StringUtils::Trim(rule.particleName) != StringUtils::Trim(parts[2])) {
            std::cout << "[BiasingManager] warning: section '" << section << "' overrides particle='"
                      << parts[2] << "' with particle='" << rule.particleName << "'.\n";
        }
        if (StringUtils::Trim(rule.processName) != StringUtils::Trim(parts[3])) {
            std::cout << "[BiasingManager] warning: section '" << section << "' overrides process='"
                      << parts[3] << "' with process='" << rule.processName << "'.\n";
        }
        rule.name = config.GetString(section, "name", MakeProcessRuleName(rule.particleName, rule.processName));
        rule.enabled = config.GetBool(section, "enabled", true);
        rule.factor = config.GetDouble(section, "factor", 1.0);
        rule.onlyPrimary = config.GetBool(section, "only_primary", true);
        rule.applyToSecondaries = config.GetBool(section, "apply_to_secondaries", false);
        if (rule.applyToSecondaries) rule.onlyPrimary = false;
        if (rule.onlyPrimary) rule.applyToSecondaries = false;
        rule.minWeight = config.GetDouble(section, "min_weight", 0.05);
        rule.maxInteractions = config.GetInt(section, "max_interactions", 5);
        rule.volumeNames = config.GetVector(section, "volumes", std::vector<std::string>{});
        rule.legacyGenerated = false;
        AddXSProcessBiasRule(rule);
    }

    // Legacy particle-level shorthand: [biasing.xs].
    if (config.HasSection("biasing.xs")) {
        WarnLegacySyntax("[biasing.xs]");
        const auto particles = config.GetVector("biasing.xs", "particles", std::vector<std::string>{});
        const auto processes = config.GetVector("biasing.xs", "processes", std::vector<std::string>{});
        const auto volumes = config.GetVector("biasing.xs", "volumes", std::vector<std::string>{});

        const double factor = config.GetDouble("biasing.xs", "factor", 1.0);
        const bool onlyPrimary = config.GetBool("biasing.xs", "only_primary", true);
        const bool applyToSecondaries = config.GetBool("biasing.xs", "apply_to_secondaries", false);
        const double minWeight = config.GetDouble("biasing.xs", "min_weight", 0.05);
        const int maxInteractions = config.GetInt("biasing.xs", "max_interactions", 5);

        for (const std::string& volume : volumes) AddBiasVolume(volume);

        for (const std::string& particle : particles) {
            XSBiasRule& rule = CreateOrGetXSBiasRule(particle);
            rule.factor = factor;
            rule.onlyPrimary = onlyPrimary;
            rule.applyToSecondaries = applyToSecondaries;
            if (rule.applyToSecondaries) rule.onlyPrimary = false;
            if (rule.onlyPrimary) rule.applyToSecondaries = false;
            rule.minWeight = minWeight;
            rule.maxInteractions = maxInteractions;
            for (const std::string& process : processes) AddUnique(rule.processNames, process);
            for (const std::string& volume : volumes) AddUnique(rule.volumeNames, volume);
        }
    }

    Validate();
}

void BiasingManager::AttachOperators(const GeometryRegistry& registry)
{
    if (!IsEnabled()) return;
    Validate();
    ClearOperators();

    const std::vector<XSProcessBiasRule> rules = GetEnabledXSProcessBiasRules();
    if (rules.empty()) {
        std::cout << "[BiasingManager] Biasing is enabled but no enabled process-level XS rules are configured." << '\n';
        return;
    }

    std::map<std::string, std::vector<XSProcessBiasRule>> rulesByVolume;
    const std::vector<std::string> registryBiasVolumes = registry.GetBiasVolumeNames();

    for (const XSProcessBiasRule& rule : rules) {
        std::vector<std::string> targetVolumes;
        if (!rule.volumeNames.empty()) {
            targetVolumes = rule.volumeNames;
            for (const std::string& volumeName : targetVolumes) {
                if (!registry.HasLogicalVolume(volumeName)) {
                    throw std::runtime_error("BiasingManager::AttachOperators failed: explicit volume '" +
                                             volumeName + "' for rule '" + rule.Key() + "' is not registered as a logical volume");
                }
            }
        } else if (!globalBiasVolumes_.empty()) {
            targetVolumes = globalBiasVolumes_;
            for (const std::string& volumeName : targetVolumes) {
                if (!registry.HasLogicalVolume(volumeName)) {
                    throw std::runtime_error("BiasingManager::AttachOperators failed: global volume '" +
                                             volumeName + "' is not registered as a logical volume");
                }
            }
        } else {
            targetVolumes = registryBiasVolumes;
        }

        if (targetVolumes.empty()) {
            std::cout << "[BiasingManager] warning: rule '" << rule.Key()
                      << "' has no volumes and GeometryRegistry has no marked bias volumes; skipping rule.\n";
            continue;
        }

        std::vector<std::string> uniqueTargets;
        for (const std::string& volume : targetVolumes) AddUnique(uniqueTargets, volume);
        for (const std::string& volumeName : uniqueTargets) {
            rulesByVolume[volumeName].push_back(rule);
        }
    }

    if (rulesByVolume.empty()) {
        std::cout << "[BiasingManager] Biasing is enabled but no target logical volumes were resolved." << '\n';
        return;
    }

    std::map<G4LogicalVolume*, std::vector<XSProcessBiasRule>> rulesByLogical;
    for (const auto& item : rulesByVolume) {
        const std::string& volumeName = item.first;
        if (!registry.HasLogicalVolume(volumeName)) {
            throw std::runtime_error("BiasingManager::AttachOperators failed: volume '" +
                                     volumeName + "' is not registered as a logical volume");
        }

        G4LogicalVolume* logicalVolume = registry.GetLogicalVolume(volumeName);
        if (!logicalVolume) {
            throw std::runtime_error("BiasingManager::AttachOperators failed: logical volume pointer is null for '" +
                                     volumeName + "'");
        }

        auto& merged = rulesByLogical[logicalVolume];
        for (const auto& rule : item.second) {
            const auto key = ProcessRuleKey(rule.particleName, rule.processName);
            if (std::none_of(merged.begin(), merged.end(), [&](const XSProcessBiasRule& existing) {
                    return ProcessRuleKey(existing.particleName, existing.processName) == key;
                })) merged.push_back(rule);
        }
    }
    for (const auto& item : rulesByLogical) {
        auto op = std::make_unique<BiasingMultiParticleXS>("AIHL_XS_Bias");
        for (const auto& rule : item.second) op->AddProcessRule(rule);
        op->AttachToVolume(item.first);
        xsOperators_.push_back(std::move(op));
        attachmentPlan_.push_back({item.first, item.second});
    }

    operatorsAttached_ = !xsOperators_.empty();
    std::cout << "[BiasingManager] Attached " << xsOperators_.size()
              << " process-level XS biasing operator(s) to geometry logical volume(s)." << '\n';
}

void BiasingManager::ClearOperators()
{
    // Geant4 stores the operator pointer on logical volumes; call this before a
    // geometry rebuild or before attaching to freshly rebuilt volumes. Do not
    // use it as a live run-time detach operation.
    xsOperators_.clear();
    attachmentPlan_.clear();
    {
        std::lock_guard<std::mutex> lock(evidenceMutex_);
        workerEvidence_.clear();
        firstConstructionFailure_.clear();
    }
    operatorsAttached_ = false;
    matchedProcessRuleCount_ = 0;
}

void BiasingManager::ConstructThreadOperators(const GeometryRegistry&) const
{
    if (!IsEnabled() || !G4Threading::IsWorkerThread()) return;
    if (threadState_.Get()) return; // never delete registered operators between runs
    const int threadId = G4Threading::G4GetThreadId();
    try {
        auto* state = new ThreadState();
        threadState_.Put(state);
        G4AutoDelete::Register(state); // one owner; destructor never dereferences Manager/LV
        state->owned.reserve(attachmentPlan_.size());
        state->active.reserve(attachmentPlan_.size());
        state->targets.reserve(attachmentPlan_.size());
        const char* fault = std::getenv("G4USIM_TEST_OUTPUT_FAULT");
        if (threadId == 0 && fault && std::string(fault) == "biasing_thread_construct_t0")
            throw std::runtime_error("test-injected worker bias construction failure");
        for (const auto& attachment : attachmentPlan_) {
            // Retain each constructed operator even if a later setup step fails:
            // G4VBiasingOperator has no unregistering destructor.
            state->owned.emplace_back(std::make_unique<BiasingMultiParticleXS>("AIHL_XS_Worker"));
            auto* op = state->owned.back().get();
            for (const auto& rule : attachment.rules) op->AddProcessRule(rule);
            op->AttachToVolume(attachment.logical);
            if (G4VBiasingOperator::GetBiasingOperator(attachment.logical) != op)
                throw std::runtime_error("Worker biasing TLS attachment verification failed");
            state->active.push_back(op);
            state->targets.push_back(attachment.logical);
        }
        if (state->active.empty()) throw std::runtime_error("Worker has no configured bias operators");
    } catch (const std::exception& error) {
        if (auto* state = threadState_.Get()) state->failure = error.what();
        std::lock_guard<std::mutex> lock(evidenceMutex_);
        if (firstConstructionFailure_.empty())
            firstConstructionFailure_ = "worker " + std::to_string(threadId) + ": " + error.what();
    } catch (...) {
        if (auto* state = threadState_.Get()) state->failure = "unknown worker bias construction exception";
        std::lock_guard<std::mutex> lock(evidenceMutex_);
        if (firstConstructionFailure_.empty())
            firstConstructionFailure_ = "worker " + std::to_string(threadId) + ": unknown bias construction exception";
    }
}

void BiasingManager::BeginThreadRun(int runId) const
{
    if (!IsEnabled()) return;
    const bool worker = G4Threading::IsWorkerThread();
    const int threadId = worker ? G4Threading::G4GetThreadId() : 0;
    auto* state = threadState_.Get();
    if (!state && !worker) {
        state = new ThreadState();
        threadState_.Put(state);
        G4AutoDelete::Register(state);
        for (std::size_t i = 0; i < xsOperators_.size(); ++i) {
            state->active.push_back(xsOperators_[i].get());
            state->targets.push_back(attachmentPlan_.at(i).logical);
        }
    }
    WorkerEvidence evidence;
    evidence.runId = runId;
    evidence.threadId = threadId;
    try {
        {
            std::lock_guard<std::mutex> lock(evidenceMutex_);
            if (!firstConstructionFailure_.empty()) throw std::runtime_error(firstConstructionFailure_);
        }
        if (!state || !state->failure.empty() || state->active.empty())
            throw std::runtime_error(state && !state->failure.empty() ? state->failure : "Execution thread has no bias operator state");
        evidence.operators = state->active.size();
        for (std::size_t i = 0; i < state->active.size(); ++i) {
            if (G4VBiasingOperator::GetBiasingOperator(state->targets[i]) != state->active[i])
                throw std::runtime_error("Execution thread bias operator TLS mapping changed");
            state->active[i]->ResetRunDiagnostics();
        }
        evidence.tlsVerified = true;
        std::set<std::string> matched;
        for (const auto& rule : GetEnabledXSProcessBiasRules()) {
            if (matched.insert(ProcessRuleKey(rule.particleName, rule.processName)).second) {
                BiasingXS::ValidateActiveProcessRule(rule); // this thread's actual process manager
            }
        }
        evidence.matchedRules = matched.size();
        if (evidence.matchedRules == 0) throw std::runtime_error("Execution thread has no active wrapped bias rule");
    } catch (const std::exception& error) {
        evidence.failure = error.what();
        if (state) state->current = evidence;
        std::lock_guard<std::mutex> lock(evidenceMutex_);
        workerEvidence_[{runId, threadId}] = evidence;
        throw;
    } catch (...) {
        evidence.failure = "unknown execution-thread bias validation exception";
        if (state) state->current = evidence;
        std::lock_guard<std::mutex> lock(evidenceMutex_);
        workerEvidence_[{runId, threadId}] = evidence;
        throw;
    }
    state->current = evidence;
    std::lock_guard<std::mutex> lock(evidenceMutex_);
    workerEvidence_[{runId, threadId}] = evidence;
}

void BiasingManager::EndThreadRun(int runId) const
{
    if (!IsEnabled()) return;
    auto* state = threadState_.Get();
    if (!state || state->current.runId != runId) return;
    auto evidence = state->current;
    evidence.endRunCompleted = true;
    for (auto* op : state->active) {
        evidence.proposals += op->GetProposalCount();
        evidence.applied += op->GetAppliedCount();
    }
    std::lock_guard<std::mutex> lock(evidenceMutex_);
    workerEvidence_[{evidence.runId, evidence.threadId}] = evidence;
    std::ostringstream line;
    line << "[G4USimBiasing] {\"schema\":\"g4usim_biasing_worker_v1\",\"run_id\":" << evidence.runId
         << ",\"thread_id\":" << evidence.threadId << ",\"operators\":" << evidence.operators
         << ",\"matched_rules\":" << evidence.matchedRules << ",\"tls_verified\":"
         << (evidence.tlsVerified ? "true" : "false") << ",\"proposals\":" << evidence.proposals
         << ",\"end_run_completed\":true,\"applied_callbacks\":" << evidence.applied << ",\"failed\":"
         << (evidence.failure.empty() ? "false" : "true") << "}\n";
    std::cout << line.str();
}

std::vector<BiasingManager::WorkerEvidence> BiasingManager::GetWorkerEvidence() const
{
    std::lock_guard<std::mutex> lock(evidenceMutex_);
    std::vector<WorkerEvidence> result;
    for (const auto& item : workerEvidence_) result.push_back(item.second);
    return result;
}

bool BiasingManager::AreOperatorsAttached() const
{
    return operatorsAttached_;
}

std::size_t BiasingManager::GetAttachedOperatorCount() const
{
    return xsOperators_.size();
}

void BiasingManager::ValidateActiveProcessRules()
{
    matchedProcessRuleCount_ = 0;
    if (!IsEnabled()) return;
    const auto rules = GetEnabledXSProcessBiasRules();
    if (rules.empty()) {
        throw std::runtime_error("XS biasing is enabled but no process-level rule is active. Add a rule or disable biasing.");
    }
    if (!operatorsAttached_) {
        throw std::runtime_error("XS biasing has active rules but no operator is attached to a geometry volume. Configure a valid rule volume or disable biasing.");
    }
    std::set<std::string> matched;
    for (const auto& rule : rules) {
        const std::string key = ProcessRuleKey(rule.particleName, rule.processName);
        if (matched.insert(key).second) {
            BiasingXS::ValidateActiveProcessRule(rule);
        }
    }
    matchedProcessRuleCount_ = matched.size();
}

std::size_t BiasingManager::GetMatchedProcessRuleCount() const
{
    return matchedProcessRuleCount_;
}

std::string BiasingManager::NormalizeParticleName(const std::string& particleName)
{
    return StringUtils::ToLower(StringUtils::Trim(particleName));
}

std::string BiasingManager::ProcessRuleKey(const std::string& particleName, const std::string& processName)
{
    return NormalizeParticleName(particleName) + "|" + StringUtils::Trim(processName);
}

std::string BiasingManager::TrimRequired(const std::string& value, const std::string& label)
{
    const std::string trimmed = StringUtils::Trim(value);
    if (trimmed.empty()) throw std::runtime_error("BiasingManager requires non-empty " + label);
    return trimmed;
}

void BiasingManager::AddUnique(std::vector<std::string>& values, const std::string& value)
{
    const std::string trimmed = StringUtils::Trim(value);
    if (trimmed.empty()) return;
    if (std::find(values.begin(), values.end(), trimmed) == values.end()) values.push_back(trimmed);
}

std::vector<XSProcessBiasRule> BiasingManager::BuildExpandedProcessRules(bool warnLegacy) const
{
    std::vector<XSProcessBiasRule> rules = config_.xsProcessRules;

    if (!config_.xsRules.empty() && warnLegacy) {
        WarnLegacySyntax("BuildExpandedProcessRules");
    }

    for (const XSBiasRule& legacyRule : config_.xsRules) {
        if (!legacyRule.enabled) continue;
        legacyRule.Validate();
        if (legacyRule.processNames.empty()) {
            if (warnLegacy && legacyDetailWarnings_.insert("empty:" + legacyRule.particleName).second) {
                std::cout << "[BiasingManager] warning: legacy rule for particle '" << legacyRule.particleName
                          << "' has no processes. Process-level biasing requires explicit process names; skipping expansion.\n";
            }
            continue;
        }

        for (const std::string& rawProcess : legacyRule.processNames) {
            const std::string process = StringUtils::Trim(rawProcess);
            if (process.empty()) continue;

            XSProcessBiasRule processRule;
            processRule.name = legacyRule.name.empty()
                ? MakeProcessRuleName(legacyRule.particleName, process)
                : legacyRule.name + "_" + process;
            processRule.particleName = legacyRule.particleName;
            processRule.processName = process;
            processRule.factor = legacyRule.factor;
            processRule.volumeNames = legacyRule.volumeNames;
            processRule.onlyPrimary = legacyRule.onlyPrimary;
            processRule.applyToSecondaries = legacyRule.applyToSecondaries;
            if (processRule.applyToSecondaries) processRule.onlyPrimary = false;
            if (processRule.onlyPrimary) processRule.applyToSecondaries = false;
            processRule.minWeight = legacyRule.minWeight;
            processRule.maxInteractions = legacyRule.maxInteractions;
            processRule.enabled = legacyRule.enabled;
            processRule.legacyGenerated = true;
            processRule.Validate();

            bool skipLegacy = false;
            for (const XSProcessBiasRule& existing : rules) {
                if (!existing.legacyGenerated
                    && ProcessRuleKey(existing.particleName, existing.processName)
                        == ProcessRuleKey(processRule.particleName, processRule.processName)) {
                    skipLegacy = true;
                    if (warnLegacy && legacyDetailWarnings_.insert("override:" + ProcessRuleKey(processRule.particleName, processRule.processName)).second) {
                        std::cout << "[BiasingManager] warning: explicit process-level rule for '"
                                  << processRule.particleName << "/" << processRule.processName
                                  << "' overrides legacy expansion.\n";
                    }
                    break;
                }
            }
            if (!skipLegacy) rules.push_back(processRule);
        }
    }

    return rules;
}

void BiasingManager::WarnLegacySyntax(const std::string& detail) const
{
    if (legacyWarningEmitted_) return;
    legacyWarningEmitted_ = true;
    std::cout << "[BiasingManager] warning: Legacy particle-level XS bias syntax is used"
              << " (" << detail << "). All listed processes share the same parameters. "
              << "Prefer process-level rules: [biasing.xs.<particle>.<process>] or "
              << "/AIHL/biasing/xs/addRule.\n";
}
