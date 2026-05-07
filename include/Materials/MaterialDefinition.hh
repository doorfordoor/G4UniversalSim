#pragma once

#include <string>
#include <vector>

enum class MaterialComponentMode {
    ByMassFraction,
    ByAtomCount,
    ByVolumeFraction
};

enum class MaterialSourceType {
    Nist,
    Custom
};

struct IsotopeDefinition {
    std::string name;
    std::string symbol;
    int z = 0;
    int n = 0;
    double a = 0.0;
    std::string aText;
};

struct IsotopeComponent {
    std::string isotopeName;
    double abundance = 0.0;
};

struct ElementDefinition {
    std::string name;
    std::string symbol;
    double z = 0.0;
    double a = 0.0;
    std::string aText;
    bool useIsotopes = false;
    std::vector<IsotopeComponent> isotopes;
};

struct MaterialComponent {
    std::string name;
    double fraction = 0.0;
    int atomCount = 0;
    MaterialComponentMode mode = MaterialComponentMode::ByMassFraction;
};

struct MaterialDefinition {
    std::string name;
    MaterialSourceType source = MaterialSourceType::Custom;
    std::string nistName;
    double density = 0.0;
    std::string densityText;
    std::string state;
    double temperature = 0.0;
    std::string temperatureText;
    double pressure = 0.0;
    std::string pressureText;
    std::vector<MaterialComponent> components;
    bool isElement = false;
    ElementDefinition element;
};
