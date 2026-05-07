#pragma once

#include "Materials/MaterialDefinition.hh"

#include <map>
#include <string>

class G4Element;
class G4Isotope;
class G4Material;

class MaterialFactory {
public:
    MaterialFactory() = default;

    G4Isotope* BuildIsotope(const IsotopeDefinition& def);

    G4Element* BuildElement(
        const ElementDefinition& def,
        const std::map<std::string, G4Isotope*>& isotopes
    );

    G4Element* BuildSimpleElement(const ElementDefinition& def);

    G4Element* BuildIsotopicElement(
        const ElementDefinition& def,
        const std::map<std::string, G4Isotope*>& isotopes
    );

    G4Material* BuildNistMaterial(const std::string& nistName);

    G4Material* BuildCustomMaterial(
        const MaterialDefinition& def,
        const std::map<std::string, G4Element*>& elements,
        const std::map<std::string, G4Material*>& materials
    );

    G4Material* BuildMaterial(
        const MaterialDefinition& def,
        const std::map<std::string, G4Element*>& elements,
        const std::map<std::string, G4Material*>& materials
    );

private:
    static std::string Normalize(const std::string& name);
    static void ValidateMassFractions(const MaterialDefinition& def);
};
