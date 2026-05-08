#include "Physics/PhysicsManager.hh"

#include "Biasing/BiasingManager.hh"
#include "Config/ConfigManager.hh"
#include "Physics/PhysicsFactory.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4SystemOfUnits.hh"

#include <algorithm>
#include <iostream>
#include <stdexcept>

namespace {

std::string CategoryText(PhysicsCategory category)
{
    switch (category) {
    case PhysicsCategory::EM: return "EM";
    case PhysicsCategory::Hadronic: return "Hadronic";
    case PhysicsCategory::Elastic: return "Elastic";
    case PhysicsCategory::Ion: return "Ion";
    case PhysicsCategory::Decay: return "Decay";
    case PhysicsCategory::Stopping: return "Stopping";
    case PhysicsCategory::Optical: return "Optical";
    case PhysicsCategory::Biasing: return "Biasing";
    case PhysicsCategory::Other: return "Other";
    default: return "Unknown";
    }
}

std::string Join(const std::vector<std::string>& values)
{
    return StringUtils::Join(values, ", ");
}

} // namespace

PhysicsManager::PhysicsManager()
    : defaultCut_(1.0 * CLHEP::mm)
{
    AddPhysicsModule("decay");
}

PhysicsManager::~PhysicsManager() = default;

void PhysicsManager::SetVerboseLevel(int level)
{
    if (level < 0) {
        throw std::runtime_error("PhysicsManager::SetVerboseLevel failed: level must be >= 0");
    }
    verboseLevel_ = level;
}

int PhysicsManager::GetVerboseLevel() const
{
    return verboseLevel_;
}

void PhysicsManager::SetEMOption(const std::string& option)
{
    requestedEMOption_ = StringUtils::Trim(option);
    if (HasReferenceList()) {
        SetReferenceEMOption(option);
        return;
    }

    const auto canonical = PhysicsFactory::NormalizeOptionName(option);
    if (PhysicsFactory::Classify(canonical) != PhysicsCategory::EM) {
        throw std::runtime_error("PhysicsManager::SetEMOption failed: option is not EM physics: '" + option + "'");
    }
    emOption_ = canonical;
}

std::string PhysicsManager::GetEMOption() const
{
    return emOption_;
}

void PhysicsManager::SetReferenceList(const std::string& referenceName)
{
    const auto name = StringUtils::Trim(referenceName);
    if (name.empty()) {
        throw std::runtime_error("PhysicsManager::SetReferenceList failed: referenceName is empty");
    }
    referenceListName_ = name;
    baseReferenceListName_ = PhysicsFactory::StripEMSuffix(name);
    if (!requestedEMOption_.empty()) {
        referenceListName_ = BuildReferenceNameWithEM(baseReferenceListName_, requestedEMOption_);
    }
}

const std::string& PhysicsManager::GetReferenceList() const
{
    return referenceListName_;
}

bool PhysicsManager::HasReferenceList() const
{
    return !referenceListName_.empty();
}

void PhysicsManager::ClearReferenceList()
{
    referenceListName_.clear();
    baseReferenceListName_.clear();
    requestedEMOption_.clear();
}

void PhysicsManager::SetBaseReferenceList(const std::string& baseName)
{
    const auto base = PhysicsFactory::StripEMSuffix(StringUtils::Trim(baseName));
    if (base.empty()) {
        throw std::runtime_error("PhysicsManager::SetBaseReferenceList failed: baseName is empty");
    }
    baseReferenceListName_ = base;
    referenceListName_ = requestedEMOption_.empty()
        ? baseReferenceListName_
        : BuildReferenceNameWithEM(baseReferenceListName_, requestedEMOption_);
}

const std::string& PhysicsManager::GetBaseReferenceList() const
{
    return baseReferenceListName_;
}

void PhysicsManager::SetRequestedEMOption(const std::string& option)
{
    requestedEMOption_ = StringUtils::Trim(option);
}

const std::string& PhysicsManager::GetRequestedEMOption() const
{
    return requestedEMOption_;
}

bool PhysicsManager::IsReferenceMode() const
{
    return HasReferenceList();
}

bool PhysicsManager::IsManualMode() const
{
    return !HasReferenceList();
}

void PhysicsManager::AddExtraModule(const std::string& option)
{
    const auto canonical = PhysicsFactory::NormalizeOptionName(option);
    if (PhysicsFactory::Classify(canonical) == PhysicsCategory::EM) {
        throw std::runtime_error("PhysicsManager::AddExtraModule failed: use SetEMOption/reference suffix for EM option '" +
                                 option + "'");
    }
    if (PhysicsFactory::Classify(canonical) == PhysicsCategory::Biasing) {
        EnableBiasingPhysics(true);
        AddUnique(extraModules_, canonical);
        return;
    }
    AddUnique(extraModules_, canonical);
}

void PhysicsManager::RemoveExtraModule(const std::string& option)
{
    const auto canonical = PhysicsFactory::NormalizeOptionName(option);
    extraModules_.erase(
        std::remove(extraModules_.begin(), extraModules_.end(), canonical),
        extraModules_.end());
}

void PhysicsManager::ClearExtraModules()
{
    extraModules_.clear();
}

bool PhysicsManager::HasExtraModule(const std::string& option) const
{
    const auto canonical = PhysicsFactory::NormalizeOptionName(option);
    return std::find(extraModules_.begin(), extraModules_.end(), canonical) != extraModules_.end();
}

std::vector<std::string> PhysicsManager::GetExtraModules() const
{
    return extraModules_;
}

void PhysicsManager::SetReferenceEMOption(const std::string& emOption)
{
    requestedEMOption_ = StringUtils::Trim(emOption);
    if (!HasReferenceList() && baseReferenceListName_.empty()) {
        throw std::runtime_error("PhysicsManager::SetReferenceEMOption failed: no reference list/base reference list is set");
    }
    const auto base = !baseReferenceListName_.empty()
        ? baseReferenceListName_
        : PhysicsFactory::StripEMSuffix(referenceListName_);
    referenceListName_ = BuildReferenceNameWithEM(base, requestedEMOption_);
}

std::string PhysicsManager::BuildReferenceNameWithEM(const std::string& baseReference,
                                                     const std::string& emOption) const
{
    return PhysicsFactory::ApplyEMSuffixToReference(baseReference, emOption);
}

void PhysicsManager::AddPhysicsModule(const std::string& option)
{
    if (HasReferenceList()) {
        AddExtraModule(option);
        return;
    }

    const auto canonical = PhysicsFactory::NormalizeOptionName(option);
    const auto category = PhysicsFactory::Classify(canonical);
    if (category == PhysicsCategory::EM) {
        SetEMOption(canonical);
        return;
    }
    if (category == PhysicsCategory::Biasing) {
        EnableBiasingPhysics(true);
        return;
    }
    AddUnique(modules_, canonical);
}

void PhysicsManager::RemovePhysicsModule(const std::string& option)
{
    if (HasReferenceList()) {
        RemoveExtraModule(option);
        return;
    }

    const auto canonical = PhysicsFactory::NormalizeOptionName(option);
    modules_.erase(
        std::remove(modules_.begin(), modules_.end(), canonical),
        modules_.end());
}

void PhysicsManager::ClearPhysicsModules()
{
    if (HasReferenceList()) {
        ClearExtraModules();
        return;
    }
    modules_.clear();
}

void PhysicsManager::AddHadronicOption(const std::string& option)
{
    AddPhysicsModule(option);
}

void PhysicsManager::AddOtherOption(const std::string& option)
{
    AddPhysicsModule(option);
}

bool PhysicsManager::HasPhysicsModule(const std::string& option) const
{
    const auto canonical = PhysicsFactory::NormalizeOptionName(option);
    const auto& list = HasReferenceList() ? extraModules_ : modules_;
    return std::find(list.begin(), list.end(), canonical) != list.end();
}

std::vector<std::string> PhysicsManager::GetPhysicsModules() const
{
    return HasReferenceList() ? extraModules_ : modules_;
}

void PhysicsManager::SetDefaultCut(double cut)
{
    if (cut <= 0.0) {
        throw std::runtime_error("PhysicsManager::SetDefaultCut failed: cut must be > 0");
    }
    defaultCut_ = cut;
}

double PhysicsManager::GetDefaultCut() const
{
    return defaultCut_;
}

void PhysicsManager::SetParticleCut(const std::string& particleName, double cut)
{
    if (cut <= 0.0) {
        throw std::runtime_error("PhysicsManager::SetParticleCut failed for particle '" +
                                 particleName + "': cut must be > 0");
    }
    particleCuts_[NormalizeParticleName(particleName)] = cut;
}

bool PhysicsManager::HasParticleCut(const std::string& particleName) const
{
    return particleCuts_.find(NormalizeParticleName(particleName)) != particleCuts_.end();
}

double PhysicsManager::GetParticleCut(const std::string& particleName) const
{
    const auto key = NormalizeParticleName(particleName);
    const auto iter = particleCuts_.find(key);
    if (iter == particleCuts_.end()) {
        throw std::runtime_error("PhysicsManager::GetParticleCut failed: no cut for particle '" +
                                 particleName + "'");
    }
    return iter->second;
}

const std::map<std::string, double>& PhysicsManager::GetParticleCuts() const
{
    return particleCuts_;
}

void PhysicsManager::SetRegionCut(const std::string& regionName,
                                  const std::string& particleName,
                                  double cut)
{
    const auto region = StringUtils::Trim(regionName);
    if (region.empty()) {
        throw std::runtime_error("PhysicsManager::SetRegionCut failed: regionName is empty");
    }
    if (cut <= 0.0) {
        throw std::runtime_error("PhysicsManager::SetRegionCut failed for region '" + region +
                                 "', particle '" + particleName + "': cut must be > 0");
    }
    regionCuts_[region][NormalizeParticleName(particleName)] = cut;
}

bool PhysicsManager::HasRegionCuts() const
{
    return !regionCuts_.empty();
}

const std::map<std::string, std::map<std::string, double>>& PhysicsManager::GetRegionCuts() const
{
    return regionCuts_;
}

void PhysicsManager::SetBiasingManager(BiasingManager* biasingManager)
{
    biasingManager_ = biasingManager;
}

BiasingManager* PhysicsManager::GetBiasingManager()
{
    return biasingManager_;
}

const BiasingManager* PhysicsManager::GetBiasingManager() const
{
    return biasingManager_;
}

void PhysicsManager::EnableBiasingPhysics(bool enable)
{
    biasingPhysicsEnabled_ = enable;
}

bool PhysicsManager::IsBiasingPhysicsEnabled() const
{
    return biasingPhysicsEnabled_;
}

void PhysicsManager::LoadFromConfig(const ConfigManager& config)
{
    if (!config.HasSection("physics")) {
        return;
    }

    if (config.HasKey("physics", "reference")) {
        const auto reference = StringUtils::Trim(config.GetString("physics", "reference", ""));
        if (reference.empty()) {
            ClearReferenceList();
        } else {
            SetReferenceList(reference);
        }
    }
    const bool hasReference = HasReferenceList();

    if (config.HasKey("physics", "em")) {
        const auto option = StringUtils::Trim(config.GetString("physics", "em", ""));
        if (!option.empty()) SetEMOption(option);
    } else if (config.HasKey("physics", "list")) {
        const auto option = StringUtils::Trim(config.GetString("physics", "list", ""));
        if (!option.empty()) AddPhysicsModule(option);
    }

    bool referenceExtraCleared = false;
    if (config.HasKey("physics", "modules")) {
        if (hasReference) {
            std::cerr << "PhysicsManager: reference mode treats [physics]/modules as extra_modules for compatibility.\n";
            ClearExtraModules();
            referenceExtraCleared = true;
        } else {
            ClearPhysicsModules();
        }
        for (const auto& module : config.GetVector("physics", "modules")) {
            if (!StringUtils::Trim(module).empty()) AddPhysicsModule(module);
        }
    }

    if (config.HasKey("physics", "extra_modules")) {
        if (hasReference) {
            if (!referenceExtraCleared) {
                ClearExtraModules();
                referenceExtraCleared = true;
            }
            for (const auto& module : config.GetVector("physics", "extra_modules")) {
                if (!StringUtils::Trim(module).empty()) AddExtraModule(module);
            }
        } else {
            std::cerr << "PhysicsManager: [physics]/extra_modules is mainly for reference mode; adding to manual modules.\n";
            for (const auto& module : config.GetVector("physics", "extra_modules")) {
                if (!StringUtils::Trim(module).empty()) AddPhysicsModule(module);
            }
        }
    }

    if (config.HasKey("physics", "default_cut")) {
        SetDefaultCut(UnitParser::ParseLength(config.GetString("physics", "default_cut")));
    }
    if (config.HasKey("physics", "biasing")) {
        EnableBiasingPhysics(config.GetBool("physics", "biasing", biasingPhysicsEnabled_));
    }
    if (config.HasKey("physics", "verbose")) {
        SetVerboseLevel(config.GetInt("physics", "verbose", verboseLevel_));
    }

    if (config.HasSection("physics.cuts")) {
        for (const auto& key : config.GetKeys("physics.cuts")) {
            SetParticleCut(key, UnitParser::ParseLength(config.GetString("physics.cuts", key)));
        }
    }

    for (const auto& section : config.GetSections()) {
        const std::string prefix = "physics.region.";
        if (!StringUtils::StartsWith(section, prefix)) continue;
        const auto region = section.substr(prefix.size());
        for (const auto& key : config.GetKeys(section)) {
            SetRegionCut(region, key, UnitParser::ParseLength(config.GetString(section, key)));
        }
    }
}

void PhysicsManager::Validate() const
{
    if (HasReferenceList()) {
        if (StringUtils::Trim(referenceListName_).empty()) {
            throw std::runtime_error("PhysicsManager::Validate failed: referenceListName is empty in reference mode");
        }
        for (const auto& module : extraModules_) {
            if (!PhysicsFactory::IsKnownOption(module)) {
                throw std::runtime_error("PhysicsManager::Validate failed: unknown extra module '" + module + "'");
            }
            if (PhysicsFactory::Classify(module) == PhysicsCategory::EM) {
                throw std::runtime_error("PhysicsManager::Validate failed: EM extra module is not allowed in reference mode '" + module + "'");
            }
        }
    } else {
        if (PhysicsFactory::Classify(emOption_) != PhysicsCategory::EM) {
            throw std::runtime_error("PhysicsManager::Validate failed: EM option is not EM: '" + emOption_ + "'");
        }
        for (const auto& module : modules_) {
            if (!PhysicsFactory::IsKnownOption(module)) {
                throw std::runtime_error("PhysicsManager::Validate failed: unknown module '" + module + "'");
            }
            if (PhysicsFactory::Classify(module) == PhysicsCategory::EM) {
                throw std::runtime_error("PhysicsManager::Validate failed: EM module duplicated in module list '" + module + "'");
            }
        }
    }
    if (defaultCut_ <= 0.0) {
        throw std::runtime_error("PhysicsManager::Validate failed: default cut must be > 0");
    }
}

void PhysicsManager::PrintSummary() const
{
    std::cout << "PhysicsManager Summary\n";
    std::cout << "  mode            : " << (HasReferenceList() ? "reference" : "manual") << '\n';
    std::cout << "  verbose_level   : " << verboseLevel_ << '\n';
    std::cout << "  reference       : " << referenceListName_ << '\n';
    std::cout << "  base_reference  : " << baseReferenceListName_ << '\n';
    std::cout << "  requested_em    : " << requestedEMOption_ << '\n';
    std::cout << "  em_option       : " << emOption_ << '\n';
    std::cout << "  manual_modules  : " << Join(modules_) << '\n';
    for (const auto& module : modules_) {
        std::cout << "    - " << module << " [" << CategoryText(PhysicsFactory::Classify(module)) << "]\n";
    }
    std::cout << "  extra_modules   : " << Join(extraModules_) << '\n';
    for (const auto& module : extraModules_) {
        std::cout << "    + " << module << " [" << CategoryText(PhysicsFactory::Classify(module)) << "]\n";
    }
    std::cout << "  default_cut     : " << defaultCut_ << '\n';
    std::cout << "  particle_cuts   : " << particleCuts_.size() << '\n';
    std::cout << "  region_cuts     : " << regionCuts_.size() << '\n';
    std::cout << "  biasing_physics : " << (biasingPhysicsEnabled_ ? "true" : "false") << '\n';
    std::cout << "  biasing_manager : " << (biasingManager_ ? "connected" : "null") << '\n';
}

std::string PhysicsManager::NormalizeParticleName(const std::string& particleName)
{
    const auto name = StringUtils::Trim(particleName);
    if (name.empty()) {
        throw std::runtime_error("PhysicsManager particle name is empty");
    }
    return name;
}

void PhysicsManager::AddUnique(std::vector<std::string>& values, const std::string& value)
{
    if (std::find(values.begin(), values.end(), value) == values.end()) {
        values.push_back(value);
    }
}
