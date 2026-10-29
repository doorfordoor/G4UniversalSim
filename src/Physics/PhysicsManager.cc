#include "Config/EffectiveRuntime.hh"
#include "G4VModularPhysicsList.hh"
#include "G4VPhysicsConstructor.hh"
#include "G4ParticleTable.hh"
#include "G4ProcessManager.hh"
#include "G4VProcess.hh"
#include "G4RegionStore.hh"
#include "G4Region.hh"
#include "G4ProductionCuts.hh"
#include "Physics/PhysicsManager.hh"
#include "Config/ConfigSchemaTable.hh"

#include "Biasing/BiasingManager.hh"
#include "Config/ConfigManager.hh"
#include "Physics/PhysicsFactory.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4SystemOfUnits.hh"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <sstream>

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
    : defaultCut_(1.0 * CLHEP::mm),
      electronCaptureThreshold_(16.7 * CLHEP::eV)
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
    const std::string region = StringUtils::Trim(regionName);
    const std::string particle = NormalizeParticleName(particleName);
    if (region.empty()) throw std::runtime_error("PhysicsManager::SetRegionCut requires a region name");
    if (region == "DefaultRegionForTheWorld") {
        throw std::runtime_error("PhysicsManager::SetRegionCut: use [physics]/default_cut or [physics.cuts] for the world region");
    }
    if (particle != "gamma" && particle != "e-" && particle != "e+" && particle != "proton") {
        throw std::runtime_error("PhysicsManager region production cuts exist only for gamma, e-, e+ and proton; got '" +
                                 particle + "'");
    }
    if (!std::isfinite(cut) || cut <= 0.0) {
        throw std::runtime_error("PhysicsManager region cut for '" + particle + "' must be a finite length > 0");
    }
    regionPhysics_[region].cuts[particle] = cut;
    regionCuts_[region][particle] = cut;
}

void PhysicsManager::SetRegionPhysics(const std::string& regionName, const RegionPhysicsSettings& settings)
{
    const std::string region = StringUtils::Trim(regionName);
    if (region.empty()) throw std::runtime_error("PhysicsManager::SetRegionPhysics requires a region name");
    if (region == "DefaultRegionForTheWorld") {
        throw std::runtime_error("[physics.region.DefaultRegionForTheWorld] is not allowed; use [physics]/default_cut "
                                 "and [physics.cuts] for the world region");
    }
    for (const auto& item : settings.cuts) SetRegionCut(region, item.first, item.second);
    RegionPhysicsSettings& target = regionPhysics_[region];
    for (double value : {settings.maxStep, settings.maxTrackLength, settings.maxTime, settings.minKineticEnergy}) {
        if (!std::isfinite(value) || value < 0.0) {
            throw std::runtime_error("[physics.region." + region + "] limits must be finite and > 0");
        }
    }
    target.maxStep = settings.maxStep;
    target.maxTrackLength = settings.maxTrackLength;
    target.maxTime = settings.maxTime;
    target.minKineticEnergy = settings.minKineticEnergy;
    target.volumes = settings.volumes;
}

const std::map<std::string, RegionPhysicsSettings>& PhysicsManager::GetRegionPhysics() const
{
    return regionPhysics_;
}

bool PhysicsManager::NeedsStepLimiter() const
{
    for (const auto& item : regionPhysics_) {
        if (item.second.HasUserLimits()) return true;
    }
    return false;
}

void PhysicsManager::EnableRadioactiveDecay(bool enable)
{
    radioactiveDecayEnabled_ = enable;
}

bool PhysicsManager::IsRadioactiveDecayEnabled() const
{
    return radioactiveDecayEnabled_;
}

void PhysicsManager::SetRadioactiveDecayTimeThreshold(double time)
{
    if (!std::isfinite(time) || time <= 0.0) {
        throw std::runtime_error("[physics.radioactive_decay]/time_threshold must be a finite time > 0");
    }
    radioactiveDecayTimeThreshold_ = time;
}

bool PhysicsManager::HasRadioactiveDecayTimeThreshold() const
{
    return radioactiveDecayTimeThreshold_ > 0.0;
}

double PhysicsManager::GetRadioactiveDecayTimeThreshold() const
{
    return radioactiveDecayTimeThreshold_;
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

void PhysicsManager::EnableMicroElec(bool enable)
{
    microElecEnabled_ = enable;
}

bool PhysicsManager::IsMicroElecEnabled() const
{
    return microElecEnabled_;
}

void PhysicsManager::SetMicroElecRegion(const std::string& regionName)
{
    microElecRegionName_ = StringUtils::Trim(regionName);
}

const std::string& PhysicsManager::GetMicroElecRegion() const
{
    return microElecRegionName_;
}

void PhysicsManager::EnableElectronCapture(bool enable)
{
    electronCaptureEnabled_ = enable;
}

bool PhysicsManager::IsElectronCaptureEnabled() const
{
    return electronCaptureEnabled_;
}

void PhysicsManager::SetElectronCaptureThreshold(double threshold)
{
    if (threshold <= 0.0) {
        throw std::runtime_error("PhysicsManager::SetElectronCaptureThreshold failed: threshold must be > 0");
    }
    electronCaptureThreshold_ = threshold;
}

double PhysicsManager::GetElectronCaptureThreshold() const
{
    return electronCaptureThreshold_;
}

void PhysicsManager::LoadFromConfig(const ConfigManager& config)
{
    LoadFromConfigImpl(config);
    effective_->reader=config.GetMainReader();
    effective_->Accept(config.GetMainReader(),ProjectEffectiveConfigFields());
}

void PhysicsManager::LoadFromConfigImpl(const ConfigManager& config)
{
    if (config.HasSection("physics") && config.HasKey("physics", "reference")) {
        const auto reference = StringUtils::Trim(config.GetString("physics", "reference", ""));
        if (reference.empty()) {
            ClearReferenceList();
        } else {
            SetReferenceList(reference);
        }
    }
    const bool hasReference = HasReferenceList();

    if (config.HasSection("physics") && config.HasKey("physics", "em")) {
        const auto option = StringUtils::Trim(config.GetString("physics", "em", ""));
        if (!option.empty()) SetEMOption(option);
    } else if (config.HasSection("physics") && config.HasKey("physics", "list")) {
        const auto option = StringUtils::Trim(config.GetString("physics", "list", ""));
        if (!option.empty()) AddPhysicsModule(option);
    }

    bool referenceExtraCleared = false;
    if (config.HasSection("physics") && config.HasKey("physics", "modules")) {
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

    if (config.HasSection("physics") && config.HasKey("physics", "extra_modules")) {
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

    if (config.HasSection("physics") && config.HasKey("physics", "default_cut")) {
        SetDefaultCut(UnitParser::ParseLength(config.GetString("physics", "default_cut")));
    }
    if (config.HasSection("physics") && config.HasKey("physics", "biasing")) {
        EnableBiasingPhysics(config.GetBool("physics", "biasing", biasingPhysicsEnabled_));
    }
    if (config.HasSection("physics") && config.HasKey("physics", "verbose")) {
        SetVerboseLevel(config.GetInt("physics", "verbose", verboseLevel_));
    }

    if (config.HasSection("physics.microelec")) {
        EnableMicroElec(config.GetBool("physics.microelec", "enabled", microElecEnabled_));
        if (config.HasKey("physics.microelec", "region")) {
            SetMicroElecRegion(config.GetString("physics.microelec", "region", microElecRegionName_));
        }
        if (config.HasKey("physics.microelec", "electron_capture")) {
            EnableElectronCapture(config.GetBool("physics.microelec", "electron_capture", electronCaptureEnabled_));
        }
        if (config.HasKey("physics.microelec", "electron_capture_threshold")) {
            SetElectronCaptureThreshold(
                UnitParser::ParseEnergy(config.GetString("physics.microelec", "electron_capture_threshold")));
        }
    }

    if (config.HasSection("physics.cuts")) {
        for (const auto& key : config.GetKeys("physics.cuts")) {
            SetParticleCut(key, UnitParser::ParseLength(config.GetString("physics.cuts", key)));
        }
    }

    // Geant4 region names are case-sensitive; section lookups use the
    // normalized name, the region keeps the spelling from the INI.
    for (const auto& info : config.GetSectionInfo()) {
        const std::string prefix = "physics.region.";
        const std::string section = info.section;
        if (!StringUtils::StartsWith(StringUtils::ToLower(section), prefix)) continue;
        const std::string original = info.originalSection.empty() ? section : info.originalSection;
        const auto region = StringUtils::Trim(original).substr(prefix.size());
        if (region.empty() || region.find('.') != std::string::npos) {
            throw std::runtime_error("[" + section + "] must be [physics.region.<region name>]");
        }
        RegionPhysicsSettings settings;
        for (const auto& key : config.GetKeys(section)) {
            const std::string name = StringUtils::ToLower(StringUtils::Trim(key));
            const std::string value = config.GetString(section, key);
            const auto positive = [&](double parsed) {
                if (!std::isfinite(parsed) || parsed <= 0.0) {
                    throw std::runtime_error("[" + section + "]/" + key + " must be > 0");
                }
                return parsed;
            };
            if (name == "gamma" || name == "e-" || name == "e+" || name == "proton") {
                settings.cuts[name] = positive(UnitParser::ParseLength(value));
            } else if (name == "max_step") {
                settings.maxStep = positive(UnitParser::ParseLength(value));
            } else if (name == "max_track_length") {
                settings.maxTrackLength = positive(UnitParser::ParseLength(value));
            } else if (name == "max_time") {
                settings.maxTime = positive(UnitParser::ParseTime(value));
            } else if (name == "min_kinetic_energy") {
                settings.minKineticEnergy = positive(UnitParser::ParseEnergy(value));
            } else if (name == "volumes") {
                for (const auto& part : StringUtils::Split(value, ',')) {
                    const std::string volume = StringUtils::Trim(part);
                    if (!volume.empty()) settings.volumes.push_back(volume);
                }
                if (settings.volumes.empty()) throw std::runtime_error("[" + section + "]/volumes lists no volume");
            } else {
                throw std::runtime_error("unknown key [" + section + "]/" + key +
                                         "; supported: gamma, e-, e+, proton (production cuts), max_step, "
                                         "max_track_length, max_time, min_kinetic_energy, volumes");
            }
        }
        SetRegionPhysics(region, settings);
    }

    if (config.HasSection("physics.radioactive_decay")) {
        const std::string section = "physics.radioactive_decay";
        for (const auto& key : config.GetKeys(section)) {
            const std::string name = StringUtils::ToLower(StringUtils::Trim(key));
            if (!ConfigSchema::HasKey("main_ini", "physics.radioactive_decay", name)) {
                throw std::runtime_error("unknown key [" + section + "]/" + key + "; supported: enabled, time_threshold");
            }
        }
        EnableRadioactiveDecay(config.GetBool(section, "enabled", true));
        if (config.HasKey(section, "time_threshold")) {
            SetRadioactiveDecayTimeThreshold(UnitParser::ParseTime(config.GetString(section, "time_threshold")));
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
    if (electronCaptureThreshold_ <= 0.0) {
        throw std::runtime_error("PhysicsManager::Validate failed: electron capture threshold must be > 0");
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
    std::cout << "  region_physics  : " << regionPhysics_.size() << '\n';
    std::cout << "  radioactive_decay: " << (radioactiveDecayEnabled_ ? "true" : "false")
              << ", time_threshold=" << radioactiveDecayTimeThreshold_ << '\n';
    std::cout << "  biasing_physics : " << (biasingPhysicsEnabled_ ? "true" : "false") << '\n';
    std::cout << "  biasing_manager : " << (biasingManager_ ? "connected" : "null") << '\n';
    std::cout << "  microelec       : " << (microElecEnabled_ ? "true" : "false") << '\n';
    std::cout << "  microelec_region: " << microElecRegionName_ << '\n';
    std::cout << "  electron_capture: " << (electronCaptureEnabled_ ? "true" : "false") << '\n';
    std::cout << "  ecap_threshold  : " << electronCaptureThreshold_ << '\n';
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

std::vector<effective_config::Field> PhysicsManager::ProjectEffectiveConfigFields() const
{
 using namespace effective_config;std::vector<Field> result;
 const auto add=[&](const char* key,Value value,const char* unit,const char* section,std::initializer_list<const char*> keys){result.push_back(effective_->Make(FieldPath("physics",key),std::move(value),unit,section,keys));};
 const bool hasEMKey=effective_->reader.HasKey("physics","em");
 const bool acceptedEM=hasEMKey && !StringUtils::Trim(effective_->reader.GetString("physics","em","")).empty();
 const auto ignoredEM=[&](Field& field){
  if(!hasEMKey || acceptedEM)return;
  auto ignored=effective_->Make(field.path,field.resolved,field.unit,"physics",{"em"});
  for(auto origin:ignored.origins)if(origin.kind=="main_ini"){origin.disposition="shadowed";field.origins.push_back(std::move(origin));}
  field.reason+="; explicit empty em is ignored by the consumer";
 };
 add("mode",HasReferenceList()?"reference":"manual","","physics",{"reference"});
 add("verbose",verboseLevel_,"","physics",{"verbose"});
 if(HasReferenceList()){
  add("reference",referenceListName_,"","physics",acceptedEM?std::initializer_list<const char*>{"reference","em"}:std::initializer_list<const char*>{"reference"});
  ignoredEM(result.back());
  add("base_reference",baseReferenceListName_,"","physics",{"reference"});
  if(!requestedEMOption_.empty())add("requested_em",requestedEMOption_,"","physics",{"em"});
  add("extra_modules",List(extraModules_),"","physics",{"modules","extra_modules"});
 }else{
  add("em",emOption_,"","physics",acceptedEM?std::initializer_list<const char*>{"em"}:hasEMKey?std::initializer_list<const char*>{}:std::initializer_list<const char*>{"list"});
  ignoredEM(result.back());
  // Manual module lists may themselves select EM, after the explicit
  // em/list consumer. Record only module declarations that actually select EM.
  auto& emField=result.back();
  for(const auto* key:{"modules","extra_modules"}) {
   const auto value=effective_->reader.GetString("physics",key,"");bool hasEM=false;
   for(const auto& option:StringUtils::Split(value,',')) {
    if(StringUtils::Trim(option).empty())continue;
    try {hasEM=hasEM || PhysicsFactory::Classify(PhysicsFactory::NormalizeOptionName(option))==PhysicsCategory::EM;}catch(const std::exception&){}
   }
   if(!hasEM)continue;
   const auto declarations=effective_->reader.GetDeclarations();
   std::size_t last=0;for(const auto& d:declarations)if(d.normalizedSection=="physics" && d.normalizedKey==key)last=d.lineNumber;
   for(const auto& d:declarations)if(d.normalizedSection=="physics" && d.normalizedKey==key) {
    Origin origin;origin.kind="main_ini";origin.file=effective_->reader.GetFilename();origin.input_sha256=effective_->reader.GetInputSha256();
    origin.section=d.originalSection;origin.key=d.originalKey;origin.alias=d.originalKey;origin.line=d.lineNumber;origin.raw=d.value;
    origin.disposition=d.lineNumber==last?"accepted":"shadowed";
    if(origin.disposition=="accepted") {for(auto& old:emField.origins)if(old.disposition=="accepted")old.disposition="shadowed";emField.requested=d.value;emField.requested_known=true;}
    emField.origins.push_back(std::move(origin));
   }
  }
  add("modules",List(modules_),"","physics",hasEMKey?std::initializer_list<const char*>{"modules","extra_modules"}:std::initializer_list<const char*>{"list","modules","extra_modules"});
 }
 add("default_cut",defaultCut_/mm,"mm","physics",{"default_cut"});
 for(const auto& cut:particleCuts_)result.push_back(effective_->Make(ObjectFieldPath("physics", "particle:"+cut.first,"cut"),cut.second/mm,"mm","physics.cuts",{cut.first.c_str()}));
 for(const auto& region:regionCuts_)for(const auto& cut:region.second)
  result.push_back(effective_->Make(ObjectFieldPath("physics","region:"+region.first,"cut_"+cut.first),cut.second/mm,"mm","physics.region."+StringUtils::ToLower(region.first),{cut.first.c_str()}));
 for(const auto& region:regionPhysics_) {
  const auto section="physics.region."+StringUtils::ToLower(region.first);const auto& s=region.second;
  const auto item=[&](const std::string& key,Value value,const char* unit){result.push_back(effective_->Make(ObjectFieldPath("physics","region:"+region.first,key),std::move(value),unit,section,{key.c_str()}));};
  for(const auto& cut:s.cuts)item(cut.first,cut.second/mm,"mm");
  item("volumes",List(s.volumes),"");
  if(s.maxStep>0)item("max_step",s.maxStep/mm,"mm");
  if(s.maxTrackLength>0)item("max_track_length",s.maxTrackLength/mm,"mm");
  if(s.maxTime>0)item("max_time",s.maxTime/ns,"ns");
  if(s.minKineticEnergy>0)item("min_kinetic_energy",s.minKineticEnergy/MeV,"MeV");
 }
 add("radioactive_decay",radioactiveDecayEnabled_,"","physics.radioactive_decay",{"enabled"});
 if(HasRadioactiveDecayTimeThreshold())add("radioactive_decay_time_threshold",radioactiveDecayTimeThreshold_/ns,"ns","physics.radioactive_decay",{"time_threshold"});
 add("biasing",biasingPhysicsEnabled_,"","physics",{"biasing"});
 add("microelec",microElecEnabled_,"","physics.microelec",{"enabled"});
 if(microElecEnabled_){
  add("microelec_region",microElecRegionName_,"","physics.microelec",{"region"});
  add("electron_capture",electronCaptureEnabled_,"","physics.microelec",{"electron_capture"});
  if(electronCaptureEnabled_)add("electron_capture_threshold",electronCaptureThreshold_/MeV,"MeV","physics.microelec",{"electron_capture_threshold"});
 }
 return result;
}
std::vector<effective_config::Field> PhysicsManager::ExportEffectiveConfigFields() const {return effective_->accepted?effective_->fields:ProjectEffectiveConfigFields();}
effective_config::Value PhysicsManager::ExportEffectiveConfigEvidence() const {return effective_->Evidence();}
void PhysicsManager::ConfirmEffectiveConfigMutation(const std::string& command,const effective_config::Origin& origin)
{
 auto fields=ProjectEffectiveConfigFields();std::vector<std::string> targets;
 const auto name=StringUtils::ToLower(command.substr(0,command.find_first_of(" \t")));
 for(const auto& f:fields){const auto key=f.path.substr(f.path.find_last_of('/')+1);
  const bool em=name.find("setem")!=std::string::npos && (key=="em" || key=="requested_em" || key=="reference");
  const bool reference=name.find("referencelist")!=std::string::npos && (key=="reference" || key=="base_reference" || key=="mode");
  const bool module=(name.find("module")!=std::string::npos || name.find("addhadronic")!=std::string::npos || name.find("addother")!=std::string::npos) && (key=="modules" || key=="extra_modules");
  const bool exact=name.find("defaultcut")!=std::string::npos && key=="default_cut";
  const bool option=(name.find("microelec")!=std::string::npos && key.find("microelec")!=std::string::npos) ||
   (name.find("electroncapture")!=std::string::npos && key.find("electron_capture")!=std::string::npos) ||
   (name.find("biasing")!=std::string::npos && key=="biasing") || (name.find("verbose")!=std::string::npos && key=="verbose");
  if(em || reference || module || exact || option)targets.push_back(f.path);
 }
 // Particle/region setters encode the exact object name as their first argument.
 std::istringstream arguments(command);std::string cmd,object;arguments>>cmd>>object;
 if(name.find("setcut")!=std::string::npos)targets.push_back(effective_config::ObjectFieldPath("physics","particle:"+NormalizeParticleName(object),"cut"));
 if(name.find("setregioncut")!=std::string::npos){std::string particle;arguments>>particle;targets.push_back(effective_config::ObjectFieldPath("physics","region:"+object,"cut_"+NormalizeParticleName(particle)));}
 effective_->Confirm(std::move(fields),command,origin,false,targets);
}
void PhysicsManager::ObserveEffectiveConfigPhysics(const G4VModularPhysicsList& list,const std::string& stage) const
{
    using namespace effective_config;
    Value::Array constructors;
    for(int i=0;;++i){const auto* physics=list.GetPhysics(i);if(!physics)break;constructors.emplace_back(physics->GetPhysicsName());}
    // Registered constructor names neither identify a reference-list name nor
    // have the same semantics as accepted factory aliases. Keep an independent
    // inventory with no fabricated configuration-valued observation.
    Value::Object inventory{{"path",FieldPath("physics","mode")},{"stage",stage},
        {"thread_id",G4Threading::G4GetThreadId()},
        {"run_id",G4RunManager::GetRunManager() && G4RunManager::GetRunManager()->GetCurrentRun()?
            Value(G4RunManager::GetRunManager()->GetCurrentRun()->GetRunID()):Value()},
        {"application_status","unknown"},{"evidence_level","none"},
        {"evidence_source","Actual G4VModularPhysicsList inventory; constructor names do not prove configured list identity"},
        {"registered_constructors",constructors}};
    if(stage=="physics_process") {
        auto* table=G4ParticleTable::GetParticleTable();auto* iterator=table->GetIterator();iterator->reset();
        Value::Object processes;
        while((*iterator)()) {
            auto* particle=iterator->value();auto* manager=particle->GetProcessManager();if(!manager)continue;
            Value::Array names;auto* actual=manager->GetProcessList();
            for(int i=0;i<manager->GetProcessListLength();++i)names.emplace_back((*actual)[i]->GetProcessName());
            processes[particle->GetParticleName()]=std::move(names);
        }
        inventory["particle_processes"]=std::move(processes);
    }
    effective_->Record(std::move(inventory));
    effective_->Record(Receipt(FieldPath("physics","verbose"),list.GetVerboseLevel(),stage,"Actual physics-list verbosity readback"));
    if(stage=="physics_cuts") {
        effective_->Record(Receipt(FieldPath("physics","default_cut"),list.GetDefaultCutValue()/mm,stage,"Actual physics-list default cut readback"));
        for(const auto& cut:particleCuts_)
            effective_->Record(Receipt(ObjectFieldPath("physics","particle:"+cut.first,"cut"),list.GetCutValue(cut.first)/mm,stage,"Actual physics-list particle production cut readback"));
        for(const auto& settings:regionPhysics_) {
            const auto* region=G4RegionStore::GetInstance()->GetRegion(settings.first,false);
            if(!region || !region->GetProductionCuts())continue;
            for(const auto& cut:settings.second.cuts)
                effective_->Record(Receipt(ObjectFieldPath("physics","region:"+settings.first,cut.first),
                    region->GetProductionCuts()->GetProductionCut(cut.first)/mm,stage,"Actual named-region production cut readback"));
        }
    }
}
