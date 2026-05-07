#include "Materials/MaterialCommandParser.hh"

#include "Utils/StringUtils.hh"

#include "G4SystemOfUnits.hh"

#include <cstdlib>
#include <stdexcept>

namespace {

double ParseNumber(const std::string& text, const std::string& original)
{
    const std::string trimmed = StringUtils::Trim(text);
    char* end = nullptr;
    const double value = std::strtod(trimmed.c_str(), &end);
    if (end == trimmed.c_str() || !StringUtils::Trim(std::string(end)).empty()) {
        throw std::runtime_error("Cannot parse number '" + text + "' in: " + original);
    }
    return value;
}

std::pair<double, std::string> ParseNumberAndUnit(const std::string& text)
{
    const std::string trimmed = StringUtils::Trim(text);
    char* end = nullptr;
    const double value = std::strtod(trimmed.c_str(), &end);
    if (end == trimmed.c_str()) {
        throw std::runtime_error("Cannot parse numeric value with unit: '" + text + "'");
    }
    return {value, StringUtils::ToLower(StringUtils::Trim(std::string(end)))};
}

}  // namespace

std::map<std::string, std::string> MaterialCommandParser::ParseKeyValueLine(
    const std::string& line
)
{
    std::map<std::string, std::string> result;
    std::size_t i = 0;

    while (i < line.size()) {
        while (i < line.size() && std::isspace(static_cast<unsigned char>(line[i]))) {
            ++i;
        }
        if (i >= line.size()) {
            break;
        }

        const std::size_t keyStart = i;
        while (i < line.size() && line[i] != '=' && !std::isspace(static_cast<unsigned char>(line[i]))) {
            ++i;
        }
        std::string key = StringUtils::ToLower(StringUtils::Trim(line.substr(keyStart, i - keyStart)));

        while (i < line.size() && std::isspace(static_cast<unsigned char>(line[i]))) {
            ++i;
        }
        if (i >= line.size() || line[i] != '=') {
            throw std::runtime_error("Expected key=value in material command: '" + line + "'");
        }
        ++i;
        while (i < line.size() && std::isspace(static_cast<unsigned char>(line[i]))) {
            ++i;
        }

        std::string value;
        if (i < line.size() && line[i] == '"') {
            ++i;
            bool closed = false;
            while (i < line.size()) {
                if (line[i] == '"') {
                    closed = true;
                    ++i;
                    break;
                }
                value.push_back(line[i++]);
            }
            if (!closed) {
                throw std::runtime_error("Unclosed quote in material command: '" + line + "'");
            }
        } else {
            const std::size_t valueStart = i;
            while (i < line.size() && !std::isspace(static_cast<unsigned char>(line[i]))) {
                ++i;
            }
            value = line.substr(valueStart, i - valueStart);
        }

        if (key.empty()) {
            throw std::runtime_error("Empty key in material command: '" + line + "'");
        }
        result[key] = value;
    }

    return result;
}

std::string MaterialCommandParser::Require(
    const std::map<std::string, std::string>& values,
    const std::string& key,
    const std::string& original
)
{
    const auto it = values.find(StringUtils::ToLower(key));
    if (it == values.end() || StringUtils::Trim(it->second).empty()) {
        throw std::runtime_error("Missing required key '" + key + "' in: " + original);
    }
    return it->second;
}

double MaterialCommandParser::ParseDensity(const std::string& text)
{
    const auto parsed = ParseNumberAndUnit(text);
    const double value = parsed.first;
    const std::string& unit = parsed.second;

    if (unit == "g/cm3" || unit == "g/cm^3") {
        return value * g / cm3;
    }
    if (unit == "kg/m3" || unit == "kg/m^3") {
        return value * kg / m3;
    }
    if (unit == "mg/cm3" || unit == "mg/cm^3") {
        return value * mg / cm3;
    }

    throw std::runtime_error("Unsupported density unit in '" + text + "'");
}

double MaterialCommandParser::ParseMolarMass(const std::string& text)
{
    const auto parsed = ParseNumberAndUnit(text);
    const double value = parsed.first;
    const std::string& unit = parsed.second;

    if (unit == "g/mole" || unit == "g/mol") {
        return value * g / mole;
    }
    if (unit == "kg/mole" || unit == "kg/mol") {
        return value * kg / mole;
    }

    throw std::runtime_error("Unsupported molar mass unit in '" + text + "'");
}

double MaterialCommandParser::ParseFraction(const std::string& text)
{
    std::string trimmed = StringUtils::Trim(text);
    bool percent = false;
    if (!trimmed.empty() && trimmed.back() == '%') {
        percent = true;
        trimmed.pop_back();
    }

    double value = ParseNumber(trimmed, text);
    if (percent) {
        value /= 100.0;
    }
    if (value < 0.0) {
        throw std::runtime_error("Negative fraction is invalid: '" + text + "'");
    }
    return value;
}

MaterialComponentMode MaterialCommandParser::ParseMode(const std::string& text)
{
    const std::string mode = StringUtils::ToLower(StringUtils::Trim(text));
    if (mode == "atom" || mode == "atom_count") {
        return MaterialComponentMode::ByAtomCount;
    }
    if (mode == "mass" || mode == "mass_fraction") {
        return MaterialComponentMode::ByMassFraction;
    }
    if (mode == "volume" || mode == "volume_fraction") {
        return MaterialComponentMode::ByVolumeFraction;
    }
    throw std::runtime_error("Unsupported material component mode: '" + text + "'");
}

std::vector<MaterialComponent> MaterialCommandParser::ParseMaterialComponents(
    const std::string& text,
    MaterialComponentMode mode
)
{
    std::vector<MaterialComponent> components;
    for (const std::string& token : StringUtils::Split(text, ',', true)) {
        const auto parts = StringUtils::Split(token, ':', false);
        if (parts.size() != 2 || StringUtils::Trim(parts[0]).empty()) {
            throw std::runtime_error("Invalid material component token '" + token + "' in '" + text + "'");
        }

        MaterialComponent component;
        component.name = StringUtils::Trim(parts[0]);
        component.mode = mode;
        if (mode == MaterialComponentMode::ByAtomCount) {
            const double atoms = ParseNumber(parts[1], token);
            if (atoms <= 0.0 || atoms != static_cast<int>(atoms)) {
                throw std::runtime_error("Atom count must be a positive integer in component '" + token + "'");
            }
            component.atomCount = static_cast<int>(atoms);
        } else {
            component.fraction = ParseFraction(parts[1]);
        }
        components.push_back(component);
    }
    return components;
}

std::vector<IsotopeComponent> MaterialCommandParser::ParseIsotopeComponents(
    const std::string& text
)
{
    std::vector<IsotopeComponent> components;
    for (const std::string& token : StringUtils::Split(text, ',', true)) {
        const auto parts = StringUtils::Split(token, ':', false);
        if (parts.size() != 2 || StringUtils::Trim(parts[0]).empty()) {
            throw std::runtime_error("Invalid isotope component token '" + token + "' in '" + text + "'");
        }

        IsotopeComponent component;
        component.isotopeName = StringUtils::Trim(parts[0]);
        component.abundance = ParseFraction(parts[1]);
        components.push_back(component);
    }
    return components;
}
