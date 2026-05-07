#include "Materials/MaterialFactory.hh"

#include "Utils/StringUtils.hh"

#include "G4Element.hh"
#include "G4Isotope.hh"
#include "G4Material.hh"
#include "G4NistManager.hh"
#include "G4State.hh"
#include "G4SystemOfUnits.hh"

#include <cmath>
#include <stdexcept>

namespace {

G4State ParseState(const std::string& state)
{
    const std::string value = StringUtils::ToLower(StringUtils::Trim(state));
    if (value.empty()) return kStateUndefined;
    if (value == "solid") return kStateSolid;
    if (value == "liquid") return kStateLiquid;
    if (value == "gas") return kStateGas;
    throw std::runtime_error("Unsupported material state: '" + state + "'");
}

G4Element* FindElement(
    const std::string& name,
    const std::map<std::string, G4Element*>& elements
)
{
    const auto key = StringUtils::ToLower(StringUtils::Trim(name));
    const auto it = elements.find(key);
    if (it != elements.end()) return it->second;

    G4NistManager* nist = G4NistManager::Instance();
    G4Element* element = nist->FindOrBuildElement(name, false);
    if (!element && StringUtils::StartsWith(name, "G4_")) {
        element = nist->FindOrBuildElement(name.substr(3), false);
    }
    return element;
}

G4Material* FindMaterial(
    const std::string& name,
    const std::map<std::string, G4Material*>& materials
)
{
    const auto key = StringUtils::ToLower(StringUtils::Trim(name));
    const auto it = materials.find(key);
    if (it != materials.end()) return it->second;

    return G4NistManager::Instance()->FindOrBuildMaterial(name, false);
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
    if (!material) {
        throw std::runtime_error("Unknown NIST material: '" + nistName + "'");
    }
    return material;
}

G4Material* MaterialFactory::BuildCustomMaterial(
    const MaterialDefinition& def,
    const std::map<std::string, G4Element*>& elements,
    const std::map<std::string, G4Material*>& materials
)
{
    if (def.name.empty() || def.density <= 0.0 || def.components.empty()) {
        throw std::runtime_error("Invalid material definition: '" + def.name + "'");
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
            if (element) {
                material->AddElement(element, component.fraction);
            } else {
                material->AddMaterial(subMaterial, component.fraction);
            }
        } else {
            throw std::runtime_error(
                "Material '" + def.name + "' volume_fraction mode is reserved but not implemented"
            );
        }
    }

    return material;
}

G4Material* MaterialFactory::BuildMaterial(
    const MaterialDefinition& def,
    const std::map<std::string, G4Element*>& elements,
    const std::map<std::string, G4Material*>& materials
)
{
    if (def.source == MaterialSourceType::Nist) {
        return BuildNistMaterial(def.nistName.empty() ? def.name : def.nistName);
    }
    return BuildCustomMaterial(def, elements, materials);
}

std::string MaterialFactory::Normalize(const std::string& name)
{
    return StringUtils::ToLower(StringUtils::Trim(name));
}

void MaterialFactory::ValidateMassFractions(const MaterialDefinition& def)
{
    bool hasMassFraction = false;
    double sum = 0.0;
    for (const MaterialComponent& component : def.components) {
        if (component.mode == MaterialComponentMode::ByMassFraction) {
            hasMassFraction = true;
            sum += component.fraction;
        }
    }
    if (hasMassFraction && std::abs(sum - 1.0) > 1.0e-6) {
        throw std::runtime_error(
            "Material '" + def.name + "' mass fractions must sum to 1.0; got "
            + std::to_string(sum)
        );
    }
}
