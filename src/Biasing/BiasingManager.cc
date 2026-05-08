#include "Biasing/BiasingManager.hh"

#include "Biasing/BiasingMultiParticleXS.hh"
#include "Config/ConfigManager.hh"
#include "Geometry/GeometryRegistry.hh"
#include "Utils/StringUtils.hh"

#include "G4LogicalVolume.hh"

#include <algorithm>
#include <iostream>
#include <set>
#include <stdexcept>

namespace {

std::string MakeRuleName(const std::string& particleName)
{
    return "xs_" + StringUtils::ToLower(StringUtils::Trim(particleName));
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

void BiasingManager::AddXSBiasRule(const XSBiasRule& rule)
{
    XSBiasRule copy = rule;
    copy.particleName = TrimRequired(copy.particleName, "particleName");
    if (copy.name.empty()) copy.name = MakeRuleName(copy.particleName);
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
    const std::string trimmed = TrimRequired(particleName, "particleName");
    const std::string key = NormalizeParticleName(trimmed);
    for (XSBiasRule& rule : config_.xsRules) {
        if (NormalizeParticleName(rule.particleName) == key) return rule;
    }

    XSBiasRule rule;
    rule.name = MakeRuleName(trimmed);
    rule.particleName = trimmed;
    rule.volumeNames = globalBiasVolumes_;
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
    if (config_.xsRules.empty()) {
        throw std::runtime_error("BiasingManager::AddXSBiasProcess requires AddXSBiasParticle first");
    }
    if (config_.xsRules.size() > 1) {
        throw std::runtime_error("BiasingManager::AddXSBiasProcess is ambiguous with multiple rules; use AddXSBiasProcess(particleName, processName)");
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
    if (minWeight <= 0.0) throw std::runtime_error("BiasingManager::SetMinWeight minWeight must be > 0");
    CreateOrGetXSBiasRule(particleName).minWeight = minWeight;
}

void BiasingManager::SetMaxInteractions(const std::string& particleName, int maxInteractions)
{
    if (maxInteractions < 0) throw std::runtime_error("BiasingManager::SetMaxInteractions maxInteractions must be >= 0");
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
    for (const XSBiasRule& rule : config_.xsRules) {
        if (rule.enabled) AddUnique(particles, rule.particleName);
    }
    return particles;
}

std::vector<std::string> BiasingManager::GetBiasedProcesses(const std::string& particleName) const
{
    return GetXSBiasRule(particleName).processNames;
}

std::vector<std::string> BiasingManager::GetBiasVolumes() const
{
    std::vector<std::string> volumes = globalBiasVolumes_;
    for (const XSBiasRule& rule : config_.xsRules) {
        for (const std::string& volume : rule.volumeNames) AddUnique(volumes, volume);
    }
    return volumes;
}

void BiasingManager::Validate() const
{
    config_.Validate();
}

void BiasingManager::PrintSummary() const
{
    std::cout << "[BiasingManager] enabled=" << (config_.enabled ? "true" : "false")
              << ", xsRules=" << config_.xsRules.size()
              << ", operatorsAttached=" << (operatorsAttached_ ? "true" : "false")
              << ", operatorCount=" << xsOperators_.size()
              << ", globalBiasVolumes=";
    const auto volumes = GetBiasVolumes();
    if (volumes.empty()) {
        std::cout << "<none>";
    } else {
        for (std::size_t i = 0; i < volumes.size(); ++i) {
            if (i > 0) std::cout << ",";
            std::cout << volumes[i];
        }
    }
    std::cout << '\n';
    for (const XSBiasRule& rule : config_.xsRules) {
        std::cout << "  " << rule.ToString() << '\n';
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

    if (!config.HasSection("biasing.xs")) {
        // TODO: support multi-rule sections such as [biasing.xs.proton].
        return;
    }

    const auto particles = config.HasKey("biasing.xs", "particles")
        ? config.GetVector("biasing.xs", "particles")
        : std::vector<std::string>{};
    const auto processes = config.HasKey("biasing.xs", "processes")
        ? config.GetVector("biasing.xs", "processes")
        : std::vector<std::string>{};
    const auto volumes = config.HasKey("biasing.xs", "volumes")
        ? config.GetVector("biasing.xs", "volumes")
        : std::vector<std::string>{};

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
        for (const std::string& process : processes) AddUnique(rule.processNames, StringUtils::Trim(process));
        for (const std::string& volume : volumes) AddUnique(rule.volumeNames, StringUtils::Trim(volume));
    }

    Validate();
}

void BiasingManager::AttachOperators(const GeometryRegistry& registry)
{
    if (!IsEnabled()) return;
    Validate();
    ClearOperators();

    const std::vector<XSBiasRule> rules = GetEnabledXSBiasRules();
    if (rules.empty()) {
        std::cout << "[BiasingManager] Biasing is enabled but no enabled XS rules are configured." << '\n';
        return;
    }

    std::vector<std::string> targetVolumeNames = GetBiasVolumes();
    if (targetVolumeNames.empty()) {
        targetVolumeNames = registry.GetBiasVolumeNames();
    }

    if (targetVolumeNames.empty()) {
        std::cout << "[BiasingManager] Biasing is enabled but no target bias volumes are configured or marked in GeometryRegistry." << '\n';
        return;
    }

    std::vector<std::string> uniqueTargets;
    for (const std::string& volume : targetVolumeNames) AddUnique(uniqueTargets, volume);

    for (const std::string& volumeName : uniqueTargets) {
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
        std::size_t ruleCount = 0;
        for (const XSBiasRule& rule : rules) {
            const bool globalTarget = ContainsVolumeName(globalBiasVolumes_, volumeName);
            const bool ruleHasLocalTargets = !rule.volumeNames.empty();
            const bool ruleTarget = ContainsVolumeName(rule.volumeNames, volumeName);

            if (globalTarget || !ruleHasLocalTargets || ruleTarget) {
                op->AddParticle(rule);
                ++ruleCount;
            }
        }

        if (ruleCount == 0) continue;

        op->AttachToVolume(logicalVolume);
        xsOperators_.push_back(std::move(op));
    }

    operatorsAttached_ = !xsOperators_.empty();
    std::cout << "[BiasingManager] Attached " << xsOperators_.size()
              << " XS biasing operator(s) to geometry logical volume(s)." << '\n';
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
