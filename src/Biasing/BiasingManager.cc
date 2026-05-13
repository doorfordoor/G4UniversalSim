#include "Biasing/BiasingManager.hh"

#include "Biasing/BiasingMultiParticleXS.hh"
#include "Config/ConfigManager.hh"
#include "Geometry/GeometryRegistry.hh"
#include "Utils/StringUtils.hh"

#include "G4LogicalVolume.hh"

#include <algorithm>
#include <iostream>
#include <map>
#include <set>
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

BiasingManager::BiasingManager() = default;
BiasingManager::~BiasingManager() = default;

void BiasingManager::Enable(bool enable)
{
    config_.enabled = enable;
}

bool BiasingManager::IsEnabled() const
{
    return config_.enabled;
}

void BiasingManager::Clear()
{
    ClearOperators();
    config_.Clear();
    globalBiasVolumes_.clear();
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
        std::cout << "  warning: Legacy particle-level XS bias syntax is configured. "
                  << "Legacy rules expand to particle+process rules with shared parameters.\n";
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
    for (const std::string& section : config.GetSections()) {
        const std::string lower = StringUtils::ToLower(StringUtils::Trim(section));
        if (!StringUtils::StartsWith(lower, "biasing.xs.") || lower == "biasing.xs") continue;
        const auto parts = SplitSectionName(section);
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

        auto op = std::make_unique<BiasingMultiParticleXS>(G4String("AIHL_XS_Bias_") + G4String(volumeName));
        for (const XSProcessBiasRule& rule : item.second) {
            op->AddProcessRule(rule);
        }

        op->AttachToVolume(logicalVolume);
        xsOperators_.push_back(std::move(op));
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
    operatorsAttached_ = false;
}

bool BiasingManager::AreOperatorsAttached() const
{
    return operatorsAttached_;
}

std::size_t BiasingManager::GetAttachedOperatorCount() const
{
    return xsOperators_.size();
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
            if (warnLegacy) {
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
                    if (warnLegacy) {
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
    std::cout << "[BiasingManager] warning: Legacy particle-level XS bias syntax is used"
              << " (" << detail << "). All listed processes share the same parameters. "
              << "Prefer process-level rules: [biasing.xs.<particle>.<process>] or "
              << "/AIHL/biasing/xs/addRule.\n";
}
