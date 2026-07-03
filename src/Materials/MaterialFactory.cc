#include "Materials/MaterialFactory.hh"

#include "Utils/StringUtils.hh"

#include "G4Element.hh"
#include "G4Exception.hh"
#include "G4Isotope.hh"
#include "G4Material.hh"
#include "G4NistManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4ios.hh"

#include <cmath>
#include <stdexcept>
#include <vector>

namespace {

constexpr double kFractionTolerance = 1.0e-6;
constexpr double kWarnNormalizeTolerance = 1.0e-12;
constexpr double kDensityMismatchWarning = 0.05;

struct ResolvedVolumeComponent {
    std::string name;
    G4Material* material = nullptr;
    double volumeFraction = 0.0;
    double density = 0.0;
    double massFraction = 0.0;
};

G4State ParseState(const std::string& state)
{
    const std::string value = StringUtils::ToLower(StringUtils::Trim(state));
    if (value.empty()) return kStateUndefined;
    if (value == "solid") return kStateSolid;
    if (value == "liquid") return kStateLiquid;
    if (value == "gas") return kStateGas;
    throw std::runtime_error("Unsupported material state: '" + state + "'");
}

G4Element* FindElement(const std::string& name, const std::map<std::string, G4Element*>& elements)
{
    const auto it = elements.find(StringUtils::ToLower(StringUtils::Trim(name)));
    if (it != elements.end()) return it->second;

    G4NistManager* nist = G4NistManager::Instance();
    G4Element* element = nist->FindOrBuildElement(name, false);
    if (!element && StringUtils::StartsWith(name, "G4_")) {
        element = nist->FindOrBuildElement(name.substr(3), false);
    }
    return element;
}

G4Material* FindMaterial(const std::string& name, const std::map<std::string, G4Material*>& materials)
{
    const auto it = materials.find(StringUtils::ToLower(StringUtils::Trim(name)));
    if (it != materials.end()) return it->second;
    return G4NistManager::Instance()->FindOrBuildMaterial(name, false);
}

void Warn(const std::string& code, const std::string& message)
{
    G4Exception("MaterialFactory", code.c_str(), JustWarning, message.c_str());
}

std::string DensityText(double density)
{
    return std::to_string(density / (g / cm3)) + " g/cm3";
}

}  // namespace

G4Isotope* MaterialFactory::BuildIsotope(const IsotopeDefinition& def)
{
    if (def.name.empty() || def.symbol.empty() || def.z <= 0 || def.n <= 0 || def.a <= 0.0) {
        throw std::runtime_error("Invalid isotope definition: '" + def.name + "'");
    }
    return new G4Isotope(def.name, def.z, def.n, def.a);
}

G4Element* MaterialFactory::BuildElement(
    const ElementDefinition& def,
    const std::map<std::string, G4Isotope*>& isotopes
)
{
    return def.useIsotopes ? BuildIsotopicElement(def, isotopes) : BuildSimpleElement(def);
}

G4Element* MaterialFactory::BuildSimpleElement(const ElementDefinition& def)
{
    if (def.name.empty() || def.symbol.empty() || def.z <= 0.0 || def.a <= 0.0) {
        throw std::runtime_error("Invalid simple element definition: '" + def.name + "'");
    }
    return new G4Element(def.name, def.symbol, def.z, def.a);
}

G4Element* MaterialFactory::BuildIsotopicElement(
    const ElementDefinition& def,
    const std::map<std::string, G4Isotope*>& isotopes
)
{
    if (def.name.empty() || def.symbol.empty() || def.isotopes.empty()) {
        throw std::runtime_error("Invalid isotopic element definition: '" + def.name + "'");
    }

    auto* element = new G4Element(def.name, def.symbol, static_cast<G4int>(def.isotopes.size()));
    double sum = 0.0;
    for (const IsotopeComponent& component : def.isotopes) {
        sum += component.abundance;
    }
    if (std::abs(sum - 1.0) > 1.0e-6) {
        throw std::runtime_error(
            "Element '" + def.name + "' isotope abundances must sum to 1.0; got "
            + std::to_string(sum)
        );
    }
    for (const IsotopeComponent& component : def.isotopes) {
        const auto it = isotopes.find(Normalize(component.isotopeName));
        if (it == isotopes.end()) {
            throw std::runtime_error(
                "Element '" + def.name + "' references unknown isotope '" + component.isotopeName + "'"
            );
        }
        element->AddIsotope(it->second, component.abundance);
    }
    return element;
}

G4Material* MaterialFactory::BuildNistMaterial(const std::string& nistName)
{
    G4Material* material = G4NistManager::Instance()->FindOrBuildMaterial(nistName, false);
    if (!material) throw std::runtime_error("Unknown NIST material: '" + nistName + "'");
    return material;
}

G4Material* MaterialFactory::BuildCustomMaterial(
    const MaterialDefinition& def,
    const std::map<std::string, G4Element*>& elements,
    const std::map<std::string, G4Material*>& materials
)
{
    if (def.source == MaterialSourceType::Nist) {
        return BuildNistMaterial(def.nistName.empty() ? def.name : def.nistName);
    }
    if (def.name.empty() || def.components.empty()) {
        throw std::runtime_error("Invalid material definition: '" + def.name + "'");
    }

    const bool isVolumeFraction =
        !def.components.empty() && def.components.front().mode == MaterialComponentMode::ByVolumeFraction;
    if (isVolumeFraction) {
        return BuildVolumeFractionMaterial(def, elements, materials);
    }

    if (def.IsDensityAuto()) {
        throw std::runtime_error(
            "Material '" + def.name + "' uses density=auto, but auto density is only supported for volume_fraction"
        );
    }
    if (!def.HasExplicitDensity() || def.density <= 0.0 || !std::isfinite(def.density)) {
        throw std::runtime_error(
            "Material '" + def.name + "' requires a finite positive explicit density for mass_fraction/atom_count"
        );
    }

    ValidateMassFractions(def);
    auto* material = new G4Material(
        def.name,
        def.density,
        static_cast<G4int>(def.components.size()),
        ParseState(def.state)
    );

    for (const MaterialComponent& component : def.components) {
        G4Element* element = FindElement(component.name, elements);
        G4Material* subMaterial = element ? nullptr : FindMaterial(component.name, materials);
        if (!element && !subMaterial) {
            throw std::runtime_error(
                "Material '" + def.name + "' references unknown component '" + component.name + "'"
            );
        }

        if (component.mode == MaterialComponentMode::ByAtomCount) {
            if (!element) {
                throw std::runtime_error(
                    "Material '" + def.name + "' uses atom_count with non-element component '"
                    + component.name + "'"
                );
            }
            material->AddElement(element, component.atomCount);
        } else if (component.mode == MaterialComponentMode::ByMassFraction) {
            if (element) material->AddElement(element, component.fraction);
            else material->AddMaterial(subMaterial, component.fraction);
        } else {
            throw std::runtime_error(
                "Material '" + def.name + "' mixes unsupported component modes; use one mode per material"
            );
        }
    }

    return material;
}

G4Material* MaterialFactory::BuildVolumeFractionMaterial(
    const MaterialDefinition& def,
    const std::map<std::string, G4Element*>& elements,
    const std::map<std::string, G4Material*>& materials
)
{
    if (def.components.empty()) {
        throw std::runtime_error(
            "Material '" + def.name + "' volume_fraction requires at least one material component"
        );
    }
    if (def.HasExplicitDensity() && (def.density <= 0.0 || !std::isfinite(def.density))) {
        throw std::runtime_error(
            "Material '" + def.name + "' explicit density must be finite and > 0 for volume_fraction"
        );
    }

    std::vector<ResolvedVolumeComponent> resolved;
    resolved.reserve(def.components.size());
    double volumeSum = 0.0;

    for (const MaterialComponent& component : def.components) {
        if (component.mode != MaterialComponentMode::ByVolumeFraction) {
            throw std::runtime_error(
                "Material '" + def.name + "' mixes volume_fraction with another component mode for component '"
                + component.name + "'. Use one mode per material."
            );
        }
        const std::string componentName = StringUtils::Trim(component.name);
        if (componentName.empty()) {
            throw std::runtime_error("Material '" + def.name + "' has an empty volume_fraction component name");
        }
        if (!std::isfinite(component.fraction) || component.fraction <= 0.0) {
            throw std::runtime_error(
                "Material '" + def.name + "' component '" + componentName
                + "' has invalid volume fraction " + std::to_string(component.fraction)
                + ". Use a finite value > 0."
            );
        }

        G4Material* subMaterial = FindMaterial(componentName, materials);
        if (!subMaterial) {
            G4Element* element = FindElement(componentName, elements);
            if (element) {
                throw std::runtime_error(
                    "Material '" + def.name + "' volume_fraction requires material components; element '"
                    + componentName + "' is not supported without an explicit material density. "
                    "Define a material for this element first, then reference that material."
                );
            }
            throw std::runtime_error(
                "Material '" + def.name + "' volume_fraction references unknown material component '"
                + componentName + "'. Use a NIST material or a previously defined custom material."
            );
        }

        const double componentDensity = subMaterial->GetDensity();
        if (!std::isfinite(componentDensity) || componentDensity <= 0.0) {
            throw std::runtime_error(
                "Material '" + def.name + "' component '" + componentName
                + "' has invalid density " + DensityText(componentDensity)
                + ". volume_fraction requires finite positive component densities."
            );
        }

        ResolvedVolumeComponent item;
        item.name = componentName;
        item.material = subMaterial;
        item.volumeFraction = component.fraction;
        item.density = componentDensity;
        resolved.push_back(item);
        volumeSum += component.fraction;
    }

    if (!std::isfinite(volumeSum) || volumeSum <= 0.0) {
        throw std::runtime_error(
            "Material '" + def.name + "' volume fraction sum is invalid: " + std::to_string(volumeSum)
        );
    }
    if (std::abs(volumeSum - 1.0) > kFractionTolerance) {
        throw std::runtime_error(
            "Material '" + def.name + "' volume fractions must sum to 1.0; got "
            + std::to_string(volumeSum) + ". Normalize the component fractions."
        );
    }
    if (std::abs(volumeSum - 1.0) > kWarnNormalizeTolerance) {
        Warn(
            "AIHLMatVFNormalize001",
            "Material '" + def.name + "' volume fractions sum to " + std::to_string(volumeSum)
            + "; normalizing within tolerance."
        );
        for (auto& component : resolved) component.volumeFraction /= volumeSum;
        volumeSum = 1.0;
    }

    double idealDensity = 0.0;
    for (const auto& component : resolved) {
        idealDensity += component.volumeFraction * component.density;
    }
    if (!std::isfinite(idealDensity) || idealDensity <= 0.0) {
        throw std::runtime_error(
            "Material '" + def.name + "' calculated ideal density is invalid: " + DensityText(idealDensity)
        );
    }

    const double finalDensity = def.HasExplicitDensity() ? def.density : idealDensity;
    if (def.HasExplicitDensity()) {
        const double relDiff = std::abs(def.density - idealDensity) / idealDensity;
        if (relDiff > kDensityMismatchWarning) {
            Warn(
                "AIHLMatVFDensity001",
                "Material '" + def.name + "' explicit density " + DensityText(def.density)
                + " differs from ideal volume-additive density " + DensityText(idealDensity)
                + " by " + std::to_string(relDiff * 100.0)
                + "%. Converted mass fractions still use component volume fractions and densities; "
                "the final G4Material uses the explicit density."
            );
        }
    }

    double massSum = 0.0;
    for (auto& component : resolved) {
        component.massFraction = component.volumeFraction * component.density / idealDensity;
        if (!std::isfinite(component.massFraction) || component.massFraction <= 0.0) {
            throw std::runtime_error(
                "Material '" + def.name + "' component '" + component.name
                + "' produced invalid mass fraction " + std::to_string(component.massFraction)
            );
        }
        massSum += component.massFraction;
    }
    if (!std::isfinite(massSum) || std::abs(massSum - 1.0) > kFractionTolerance) {
        throw std::runtime_error(
            "Material '" + def.name + "' converted mass fractions must sum to 1.0; got "
            + std::to_string(massSum)
        );
    }
    if (std::abs(massSum - 1.0) > kWarnNormalizeTolerance) {
        for (auto& component : resolved) component.massFraction /= massSum;
    }

    auto* material = new G4Material(
        def.name,
        finalDensity,
        static_cast<G4int>(resolved.size()),
        ParseState(def.state)
    );

    G4cout << "[MaterialFactory] Built volume_fraction material '" << def.name << "' using ideal additive volumes."
           << " idealDensity=" << DensityText(idealDensity)
           << ", finalDensity=" << DensityText(finalDensity) << G4endl;
    for (const auto& component : resolved) {
        G4cout << "  component " << component.name
               << ": v=" << component.volumeFraction
               << ", rho=" << DensityText(component.density)
               << ", w=" << component.massFraction << G4endl;
        material->AddMaterial(component.material, component.massFraction);
    }

    return material;
}

G4Material* MaterialFactory::BuildMaterial(
    const MaterialDefinition& def,
    const std::map<std::string, G4Element*>& elements,
    const std::map<std::string, G4Material*>& materials
)
{
    return def.source == MaterialSourceType::Nist
        ? BuildNistMaterial(def.nistName.empty() ? def.name : def.nistName)
        : BuildCustomMaterial(def, elements, materials);
}

std::string MaterialFactory::Normalize(const std::string& name)
{
    return StringUtils::ToLower(StringUtils::Trim(name));
}

void MaterialFactory::ValidateMassFractions(const MaterialDefinition& def)
{
    bool allMass = true;
    double sum = 0.0;
    for (const MaterialComponent& component : def.components) {
        if (component.mode != MaterialComponentMode::ByMassFraction) {
            allMass = false;
            break;
        }
        sum += component.fraction;
    }
    if (allMass && std::abs(sum - 1.0) > 1.0e-6) {
        throw std::runtime_error(
            "Material '" + def.name + "' mass fractions must sum to 1.0; got "
            + std::to_string(sum)
        );
    }
}
