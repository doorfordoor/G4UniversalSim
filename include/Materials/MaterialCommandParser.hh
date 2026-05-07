#pragma once

#include "Materials/MaterialDefinition.hh"

#include <map>
#include <string>
#include <vector>

class MaterialCommandParser {
public:
    static std::map<std::string, std::string> ParseKeyValueLine(const std::string& line);
    static std::string Require(
        const std::map<std::string, std::string>& values,
        const std::string& key,
        const std::string& original
    );

    static double ParseDensity(const std::string& text);
    static double ParseMolarMass(const std::string& text);
    static double ParseFraction(const std::string& text);
    static MaterialComponentMode ParseMode(const std::string& text);
    static std::vector<MaterialComponent> ParseMaterialComponents(
        const std::string& text,
        MaterialComponentMode mode
    );
    static std::vector<IsotopeComponent> ParseIsotopeComponents(const std::string& text);
};
