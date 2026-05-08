#include "Materials/MaterialCommandParser.hh"

#include "Utils/CommandParser.hh"
#include "Utils/StringUtils.hh"

#include "G4SystemOfUnits.hh"

#include <cstdlib>
#include <stdexcept>

namespace {

double ParseStrictNumber(const std::string& text, const std::string& original)
{
    const std::string trimmed = StringUtils::Trim(text);
    char* end = nullptr;
    const double value = std::strtod(trimmed.c_str(), &end);
    if (end == trimmed.c_str() || !StringUtils::Trim(std::string(end)).empty()) {
        throw std::runtime_error("Cannot parse number '" + text + "' in '" + original + "'");
    }
    return value;
}

std::pair<double, std::string> ParseNumberUnit(const std::string& text)
{
    const std::string trimmed = StringUtils::Trim(text);
    char* end = nullptr;
    const double value = std::strtod(trimmed.c_str(), &end);
    if (end == trimmed.c_str()) {
        throw std::runtime_error("Cannot parse number and unit from '" + text + "'");
    }
    std::string unit = StringUtils::Trim(std::string(end));
    if (!unit.empty() && unit.front() == '*') {
        unit = StringUtils::Trim(unit.substr(1));
    }
    return {value, StringUtils::ToLower(unit)};
}

}  // namespace

std::map<std::string, std::string> MaterialCommandParser::ParseKeyValueLine(
    const std::string& line
)
{
    return CommandParser::ParseKeyValueLine(
        line,
        "name=SiO2 density=2.2 g/cm3 components=\"Si:1,O:2\"; name=Al density=2.7*g/cm3"
    );
}

std::string MaterialCommandParser::Require(
    const std::map<std::string, std::string>& values,
    const std::string& key,
    const std::string& original
)
{
    const auto it = values.find(StringUtils::ToLower(key));
    if (it == values.end() || StringUtils::Trim(it->second).empty()) {
        throw std::runtime_error("Missing required key '" + key + "' in '" + original + "'");
    }
    return it->second;
}

double MaterialCommandParser::ParseDensity(const std::string& text)
{
    const auto parsed = ParseNumberUnit(text);
    const double value = parsed.first;
    const std::string unit = parsed.second;
    if (unit == "g/cm3" || unit == "g/cm^3") return value * g / cm3;
    if (unit == "kg/m3" || unit == "kg/m^3") return value * kg / m3;
    if (unit == "mg/cm3" || unit == "mg/cm^3") return value * mg / cm3;
    throw std::runtime_error("Unsupported density unit in '" + text + "'");
}

double MaterialCommandParser::ParseMolarMass(const std::string& text)
{
    const auto parsed = ParseNumberUnit(text);
    const double value = parsed.first;
    const std::string unit = parsed.second;
    if (unit == "g/mole" || unit == "g/mol") return value * g / mole;
    if (unit == "kg/mole" || unit == "kg/mol") return value * kg / mole;
    throw std::runtime_error("Unsupported molar mass unit in '" + text + "'");
}

double MaterialCommandParser::ParseFraction(const std::string& text)
{
    std::string valueText = StringUtils::Trim(text);
    bool percent = false;
    if (!valueText.empty() && valueText.back() == '%') {
        percent = true;
        valueText.pop_back();
    }
    double value = ParseStrictNumber(valueText, text);
    if (percent) value /= 100.0;
    if (value < 0.0) throw std::runtime_error("Negative fraction is invalid: '" + text + "'");
    return value;
}

MaterialComponentMode MaterialCommandParser::ParseMode(const std::string& text)
{
    const std::string mode = StringUtils::ToLower(StringUtils::Trim(text));
    if (mode == "atom" || mode == "atom_count") return MaterialComponentMode::ByAtomCount;
    if (mode == "mass" || mode == "mass_fraction") return MaterialComponentMode::ByMassFraction;
    if (mode == "volume" || mode == "volume_fraction") return MaterialComponentMode::ByVolumeFraction;
    throw std::runtime_error("Unsupported material component mode: '" + text + "'");
}

std::vector<MaterialComponent> MaterialCommandParser::ParseMaterialComponents(
    const std::string& text,
    MaterialComponentMode mode
)
{
    std::vector<MaterialComponent> result;
    for (const std::string& token : StringUtils::Split(text, ',', true)) {
        const auto parts = StringUtils::Split(token, ':', false);
        if (parts.size() != 2 || StringUtils::Trim(parts[0]).empty()) {
            throw std::runtime_error("Invalid material component '" + token + "' in '" + text + "'");
        }
        MaterialComponent c;
        c.name = StringUtils::Trim(parts[0]);
        c.mode = mode;
        if (mode == MaterialComponentMode::ByAtomCount) {
            const double atoms = ParseStrictNumber(parts[1], token);
            if (atoms <= 0.0 || atoms != static_cast<int>(atoms)) {
                throw std::runtime_error("Atom count must be a positive integer in '" + token + "'");
            }
            c.atomCount = static_cast<int>(atoms);
        } else {
            c.fraction = ParseFraction(parts[1]);
        }
        result.push_back(c);
    }
    return result;
}

std::vector<IsotopeComponent> MaterialCommandParser::ParseIsotopeComponents(
    const std::string& text
)
{
    std::vector<IsotopeComponent> result;
    for (const std::string& token : StringUtils::Split(text, ',', true)) {
        const auto parts = StringUtils::Split(token, ':', false);
        if (parts.size() != 2 || StringUtils::Trim(parts[0]).empty()) {
            throw std::runtime_error("Invalid isotope component '" + token + "' in '" + text + "'");
        }
        IsotopeComponent c;
        c.isotopeName = StringUtils::Trim(parts[0]);
        c.abundance = ParseFraction(parts[1]);
        result.push_back(c);
    }
    return result;
}
