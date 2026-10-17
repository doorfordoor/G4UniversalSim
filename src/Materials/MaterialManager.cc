#include "Materials/MaterialManager.hh"

#include "Materials/MaterialFactory.hh"
#include "Materials/MaterialIniReader.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include "G4Element.hh"
#include "G4Isotope.hh"
#include "G4Material.hh"
#include "G4NistManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4ios.hh"

#include <cmath>
#include <cstdlib>
#include <set>
#include <stdexcept>

namespace {

bool IsVolumeFractionMaterial(const MaterialDefinition& def)
{
    return !def.components.empty()
        && def.components.front().mode == MaterialComponentMode::ByVolumeFraction;
}

std::string DensityText(double density)
{
    return std::to_string(density / (g / cm3)) + " g/cm3";
}

bool MaterialLifecycleTraceEnabled()
{
#ifdef _WIN32
    char* value = nullptr;
    std::size_t size = 0;
    const errno_t result = _dupenv_s(&value, &size, "G4USIM_TEST_MATERIAL_LIFECYCLE");
    const bool enabled = result == 0 && value != nullptr;
    std::free(value);
    return enabled;
#else
    return std::getenv("G4USIM_TEST_MATERIAL_LIFECYCLE") != nullptr;
#endif
}

}  // namespace

MaterialManager::MaterialManager() = default;
MaterialManager::~MaterialManager() = default;

void MaterialManager::LoadMaterials(const std::string& filename)
{
    EnsureUnlocked("load materials");
    MaterialIniReader reader;
    reader.Load(filename);
    try {
        for (const std::string& nistName : reader.GetNistMaterialNames()) nistMaterialDefinitions_.push_back(nistName);
        for (const std::string& name : reader.GetIsotopeNames()) AddIsotopeDefinition(reader.GetIsotopeDefinition(name));
        for (const std::string& name : reader.GetElementNames()) AddElementDefinition(reader.GetElementDefinition(name));
        for (const std::string& name : reader.GetMaterialNames()) AddMaterialDefinition(reader.GetMaterialDefinition(name));
        if (MaterialLifecycleTraceEnabled()) {
            G4cout << "[MaterialLifecycle] build_started" << G4endl;
        }
        BuildAll();
        loadedConfigFiles_.push_back(FileUtils::AbsolutePath(filename));
    } catch (...) {
        // BuildAll may have installed a subset of definitions/Geant4 objects.
        // An unsuccessful load must never be reported as a clean source.
        incompleteConfigLoad_ = true;
        throw;
    }
}

const std::vector<std::string>& MaterialManager::GetLoadedConfigFiles() const
{
    return loadedConfigFiles_;
}

bool MaterialManager::HasNonFileConfigMutations() const
{
    return nonFileConfigMutations_;
}

bool MaterialManager::HasIncompleteConfigLoad() const
{
    return incompleteConfigLoad_;
}

void MaterialManager::MarkNonFileConfigMutation()
{
    nonFileConfigMutations_ = true;
}

std::size_t MaterialManager::GetCommandFailureCount() const
{
    return commandFailureCount_;
}

const std::string& MaterialManager::GetLastCommandFailure() const
{
    return lastCommandFailure_;
}

void MaterialManager::RecordCommandFailure(const std::string& error)
{
    ++commandFailureCount_;
    lastCommandFailure_ = error;
}

void MaterialManager::AddIsotopeDefinition(const IsotopeDefinition& def)
{
    EnsureUnlocked("add isotope definition");
    if (def.name.empty()) throw std::runtime_error("Cannot add isotope definition with empty name");
    isotopeDefinitions_[Normalize(def.name)] = def;
}

void MaterialManager::AddElementDefinition(const ElementDefinition& def)
{
    EnsureUnlocked("add element definition");
    if (def.name.empty()) throw std::runtime_error("Cannot add element definition with empty name");
    elementDefinitions_[Normalize(def.name)] = def;
}

void MaterialManager::AddMaterialDefinition(const MaterialDefinition& def)
{
    EnsureUnlocked("add material definition");
    if (def.name.empty()) throw std::runtime_error("Cannot add material definition with empty name");
    if (!StringUtils::Trim(def.temperatureText).empty() || !StringUtils::Trim(def.pressureText).empty()) {
        throw std::runtime_error(
            "Material '" + def.name + "' uses unsupported temperature/pressure fields. "
            "Remove temperature and pressure; current materials support density, state, and composition only."
        );
    }
    materialDefinitions_[Normalize(def.name)] = def;
}

G4Isotope* MaterialManager::BuildIsotope(const std::string& name)
{
    const std::string key = Normalize(name);
    const auto existing = isotopes_.find(key);
    if (existing != isotopes_.end()) return existing->second;
    const auto defIt = isotopeDefinitions_.find(key);
    if (defIt == isotopeDefinitions_.end()) throw std::runtime_error("Unknown isotope definition: '" + name + "'");

    MaterialFactory factory;
    G4Isotope* isotope = factory.BuildIsotope(defIt->second);
    RegisterIsotope(defIt->second.name, isotope);
    return isotope;
}

G4Element* MaterialManager::BuildElement(const std::string& name)
{
    const std::string key = Normalize(name);
    const auto existing = elements_.find(key);
    if (existing != elements_.end()) return existing->second;

    const auto defIt = elementDefinitions_.find(key);
    if (defIt == elementDefinitions_.end()) {
        G4Element* element = G4NistManager::Instance()->FindOrBuildElement(name, false);
        if (!element && StringUtils::StartsWith(name, "G4_")) {
            element = G4NistManager::Instance()->FindOrBuildElement(name.substr(3), false);
        }
        if (!element) throw std::runtime_error("Unknown element definition or NIST element: '" + name + "'");
        RegisterElement(name, element);
        return element;
    }

    const ElementDefinition& def = defIt->second;
    if (def.useIsotopes) {
        for (const IsotopeComponent& component : def.isotopes) BuildIsotope(component.isotopeName);
    }
    MaterialFactory factory;
    G4Element* element = factory.BuildElement(def, isotopes_);
    RegisterElement(def.name, element);
    return element;
}

G4Material* MaterialManager::BuildMaterial(const std::string& name)
{
    const std::string key = Normalize(name);
    const auto existing = materials_.find(key);
    if (existing != materials_.end()) return existing->second;

    const auto defIt = materialDefinitions_.find(key);
    if (defIt == materialDefinitions_.end()) return BuildNistMaterial(name);

    if (buildingMaterials_.count(key)) {
        std::string path;
        bool inCycle = false;
        for (const std::string& stackKey : buildingMaterialStack_) {
            if (stackKey == key) inCycle = true;
            if (!inCycle) continue;
            if (!path.empty()) path += " -> ";
            const auto stackIt = materialDefinitions_.find(stackKey);
            path += stackIt == materialDefinitions_.end() ? stackKey : stackIt->second.name;
        }
        if (!path.empty()) path += " -> ";
        path += defIt->second.name;
        throw std::runtime_error("Circular material dependency detected: " + path);
    }
    buildingMaterials_.insert(key);
    buildingMaterialStack_.push_back(key);
    try {
        G4Material* material = BuildCustomMaterial(defIt->second);
        buildingMaterials_.erase(key);
        buildingMaterialStack_.pop_back();
        return material;
    } catch (...) {
        buildingMaterials_.erase(key);
        buildingMaterialStack_.pop_back();
        throw;
    }
}

void MaterialManager::BuildAll()
{
    for (const std::string& nistName : nistMaterialDefinitions_) BuildNistMaterial(nistName);
    for (const auto& item : isotopeDefinitions_) BuildIsotope(item.second.name);
    for (const auto& item : elementDefinitions_) BuildElement(item.second.name);

    for (const auto& item : materialDefinitions_) BuildMaterial(item.second.name);
}

G4Material* MaterialManager::GetMaterial(const std::string& name) const
{
    const auto it = materials_.find(Normalize(name));
    if (it != materials_.end()) return it->second;
    G4Material* nist = G4NistManager::Instance()->FindOrBuildMaterial(name, false);
    if (nist) {
        const_cast<MaterialManager*>(this)->RegisterMaterial(name, nist);
        return nist;
    }
    throw std::runtime_error("Material not found: '" + name + "'");
}

G4Element* MaterialManager::GetElement(const std::string& name) const
{
    const auto it = elements_.find(Normalize(name));
    if (it != elements_.end()) return it->second;
    throw std::runtime_error("Element not found: '" + name + "'");
}

G4Isotope* MaterialManager::GetIsotope(const std::string& name) const
{
    const auto it = isotopes_.find(Normalize(name));
    if (it != isotopes_.end()) return it->second;
    throw std::runtime_error("Isotope not found: '" + name + "'");
}

bool MaterialManager::HasMaterial(const std::string& name) const
{
    return materials_.count(Normalize(name)) || materialDefinitions_.count(Normalize(name))
        || G4NistManager::Instance()->FindOrBuildMaterial(name, false) != nullptr;
}

bool MaterialManager::HasElement(const std::string& name) const
{
    return elements_.count(Normalize(name)) || elementDefinitions_.count(Normalize(name));
}

bool MaterialManager::HasIsotope(const std::string& name) const
{
    return isotopes_.count(Normalize(name)) || isotopeDefinitions_.count(Normalize(name));
}

G4Material* MaterialManager::BuildNistMaterial(const std::string& name)
{
    MaterialFactory factory;
    G4Material* material = factory.BuildNistMaterial(name);
    RegisterMaterial(name, material);
    return material;
}

G4Material* MaterialManager::BuildCustomMaterial(const MaterialDefinition& desc)
{
    if (desc.source == MaterialSourceType::Nist) {
        G4Material* material = BuildNistMaterial(desc.nistName.empty() ? desc.name : desc.nistName);
        RegisterMaterial(desc.name, material);
        return material;
    }
    for (const MaterialComponent& component : desc.components) {
        const std::string key = Normalize(component.name);
        if (component.mode == MaterialComponentMode::ByVolumeFraction) {
            if (materialDefinitions_.count(key)) BuildMaterial(component.name);
            else if (elementDefinitions_.count(key)) BuildElement(component.name);
        } else {
            if (elementDefinitions_.count(key)) BuildElement(component.name);
            else if (materialDefinitions_.count(key)) BuildMaterial(component.name);
        }
    }
    MaterialFactory factory;
    G4Material* material = factory.BuildCustomMaterial(desc, elements_, materials_);
    RegisterMaterial(desc.name, material);
    return material;
}

void MaterialManager::RegisterMaterial(const std::string& name, G4Material* material)
{
    if (!material) throw std::runtime_error("Cannot register null material: '" + name + "'");
    materials_[Normalize(name)] = material;
}

void MaterialManager::RegisterElement(const std::string& name, G4Element* element)
{
    if (!element) throw std::runtime_error("Cannot register null element: '" + name + "'");
    elements_[Normalize(name)] = element;
}

void MaterialManager::RegisterIsotope(const std::string& name, G4Isotope* isotope)
{
    if (!isotope) throw std::runtime_error("Cannot register null isotope: '" + name + "'");
    isotopes_[Normalize(name)] = isotope;
}

std::vector<std::string> MaterialManager::GetMaterialNames() const
{
    std::vector<std::string> names;
    for (const auto& item : materials_) names.push_back(item.first);
    return names;
}

std::vector<std::string> MaterialManager::GetElementNames() const
{
    std::vector<std::string> names;
    for (const auto& item : elements_) names.push_back(item.first);
    return names;
}

std::vector<std::string> MaterialManager::GetIsotopeNames() const
{
    std::vector<std::string> names;
    for (const auto& item : isotopes_) names.push_back(item.first);
    return names;
}

void MaterialManager::PrintMaterials() const
{
    G4cout << "[MaterialManager] Materials:" << G4endl;
    for (const auto& item : materials_) {
        G4cout << "  " << item.first << " -> " << item.second->GetName();
        const auto defIt = materialDefinitions_.find(item.first);
        if (defIt != materialDefinitions_.end() && IsVolumeFractionMaterial(defIt->second)) {
            const MaterialDefinition& def = defIt->second;
            double idealDensity = 0.0;
            struct PrintComponent {
                std::string name;
                double volumeFraction = 0.0;
                double density = 0.0;
                double massFraction = 0.0;
            };
            std::vector<PrintComponent> components;
            bool printable = true;
            for (const auto& component : def.components) {
                G4Material* subMaterial = nullptr;
                const auto subIt = materials_.find(Normalize(component.name));
                if (subIt != materials_.end()) subMaterial = subIt->second;
                else subMaterial = G4NistManager::Instance()->FindOrBuildMaterial(component.name, false);
                if (!subMaterial || subMaterial->GetDensity() <= 0.0 || !std::isfinite(subMaterial->GetDensity())) {
                    printable = false;
                    break;
                }
                PrintComponent pc;
                pc.name = component.name;
                pc.volumeFraction = component.fraction;
                pc.density = subMaterial->GetDensity();
                components.push_back(pc);
                idealDensity += pc.volumeFraction * pc.density;
            }
            G4cout << " (mode=volume_fraction";
            if (def.HasExplicitDensity()) G4cout << ", configuredDensity=" << DensityText(def.density);
            else G4cout << ", configuredDensity=auto";
            if (printable && idealDensity > 0.0) {
                G4cout << ", idealDensity=" << DensityText(idealDensity)
                       << ", finalDensity=" << DensityText(item.second->GetDensity());
            }
            G4cout << ")";
            if (printable && idealDensity > 0.0) {
                G4cout << G4endl;
                for (auto& component : components) {
                    component.massFraction = component.volumeFraction * component.density / idealDensity;
                    G4cout << "    " << component.name
                           << ": v=" << component.volumeFraction
                           << ", rho=" << DensityText(component.density)
                           << ", w=" << component.massFraction << G4endl;
                }
                continue;
            }
        }
        G4cout << G4endl;
    }
}

void MaterialManager::PrintElements() const
{
    G4cout << "[MaterialManager] Elements:" << G4endl;
    for (const auto& item : elements_) G4cout << "  " << item.first << " -> " << item.second->GetName() << G4endl;
}

void MaterialManager::PrintIsotopes() const
{
    G4cout << "[MaterialManager] Isotopes:" << G4endl;
    for (const auto& item : isotopes_) G4cout << "  " << item.first << " -> " << item.second->GetName() << G4endl;
}

void MaterialManager::PrintAll() const
{
    PrintIsotopes();
    PrintElements();
    PrintMaterials();
}

void MaterialManager::Clear()
{
    nonFileConfigMutations_ = true;
    isotopeDefinitions_.clear();
    elementDefinitions_.clear();
    materialDefinitions_.clear();
    nistMaterialDefinitions_.clear();
    isotopes_.clear();
    elements_.clear();
    materials_.clear();
    buildingMaterials_.clear();
    buildingMaterialStack_.clear();
}

void MaterialManager::SetLocked(bool locked)
{
    locked_ = locked;
    if (locked_) G4cout << "[MaterialManager] Locked. New definitions will be rejected." << G4endl;
}

bool MaterialManager::IsLocked() const
{
    return locked_;
}

std::string MaterialManager::Normalize(const std::string& name)
{
    return StringUtils::ToLower(StringUtils::Trim(name));
}

void MaterialManager::EnsureUnlocked(const std::string& action) const
{
    if (locked_) {
        throw std::runtime_error(
            "MaterialManager is locked; cannot " + action
            + ". Existing geometry will not update automatically after material changes."
        );
    }
}
