#include "Utils/UnitParser.hh"

#include "Utils/StringUtils.hh"

#include "G4SystemOfUnits.hh"
#include "G4UnitsTable.hh"

#include <cstdlib>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>

namespace {

struct ParsedQuantity {
    double value = 0.0;
    std::string unit;
    bool hasUnit = false;
};

double ParseStrictDouble(const std::string& text, const std::string& original)
{
    const std::string trimmed = StringUtils::Trim(text);
    if (trimmed.empty()) {
        throw std::runtime_error("Cannot parse empty numeric value from: '" + original + "'");
    }

    char* end = nullptr;
    const double value = std::strtod(trimmed.c_str(), &end);
    if (end == trimmed.c_str()) {
        throw std::runtime_error("Cannot parse numeric value from: '" + original + "'");
    }

    const std::string tail = StringUtils::Trim(std::string(end));
    if (!tail.empty()) {
        throw std::runtime_error("Unexpected text after numeric value in: '" + original + "'");
    }

    return value;
}

ParsedQuantity ParseQuantity(const std::string& text)
{
    const std::string trimmed = StringUtils::Trim(text);
    if (trimmed.empty()) {
        throw std::runtime_error("Cannot parse empty quantity from: '" + text + "'");
    }

    char* end = nullptr;
    const double value = std::strtod(trimmed.c_str(), &end);
    if (end == trimmed.c_str()) {
        throw std::runtime_error("Cannot parse numeric value from quantity: '" + text + "'");
    }

    std::string unit = StringUtils::Trim(std::string(end));
    if (!unit.empty() && unit.front() == '*') {
        unit = StringUtils::Trim(unit.substr(1));
    }
    if (unit.find_first_of(" \t\r\n") != std::string::npos) {
        throw std::runtime_error("Invalid unit text in quantity: '" + text + "'");
    }

    return ParsedQuantity{value, unit, !unit.empty()};
}

const std::map<std::string, double>& LengthUnits()
{
    static const std::map<std::string, double> units = {
        {"nm", nm},
        {"um", micrometer},
        {"mm", mm},
        {"cm", cm},
        {"m", m},
    };
    return units;
}

const std::map<std::string, double>& EnergyUnits()
{
    static const std::map<std::string, double> units = {
        {"eV", eV},
        {"keV", keV},
        {"MeV", MeV},
        {"GeV", GeV},
    };
    return units;
}

const std::map<std::string, double>& TimeUnits()
{
    static const std::map<std::string, double> units = {
        {"ns", ns},
        {"us", microsecond},
        {"ms", millisecond},
        {"s", second},
    };
    return units;
}

const std::map<std::string, double>& AngleUnits()
{
    static const std::map<std::string, double> units = {
        {"deg", deg},
        {"rad", rad},
    };
    return units;
}

double ParseTypedQuantity(
    const std::string& text,
    const std::map<std::string, double>& allowedUnits,
    const std::string& quantityType
)
{
    const ParsedQuantity parsed = ParseQuantity(text);
    if (!parsed.hasUnit) {
        return parsed.value;
    }

    const auto it = allowedUnits.find(parsed.unit);
    if (it == allowedUnits.end()) {
        throw std::runtime_error(
            "Unsupported " + quantityType + " unit '" + parsed.unit
            + "' in quantity: '" + text + "'"
        );
    }

    return parsed.value * it->second;
}

}  // namespace

namespace UnitParser {

double ParseDouble(const std::string& text)
{
    return ParseStrictDouble(text, text);
}

double ParseDoubleWithUnit(const std::string& text)
{
    const ParsedQuantity parsed = ParseQuantity(text);
    if (!parsed.hasUnit) {
        return parsed.value;
    }

    const double unitValue = G4UnitDefinition::GetValueOf(parsed.unit);
    if (unitValue <= 0.0) {
        throw std::runtime_error(
            "Unsupported or unknown unit '" + parsed.unit + "' in quantity: '" + text + "'"
        );
    }

    return parsed.value * unitValue;
}

double ParseLength(const std::string& text)
{
    return ParseTypedQuantity(text, LengthUnits(), "length");
}

double ParseEnergy(const std::string& text)
{
    return ParseTypedQuantity(text, EnergyUnits(), "energy");
}

double ParseTime(const std::string& text)
{
    return ParseTypedQuantity(text, TimeUnits(), "time");
}

double ParseAngle(const std::string& text)
{
    return ParseTypedQuantity(text, AngleUnits(), "angle");
}

std::vector<double> ParseVectorDouble(
    const std::string& text,
    char delimiter
)
{
    std::vector<double> values;
    for (const std::string& item : StringUtils::Split(text, delimiter, true)) {
        values.push_back(ParseDouble(item));
    }
    return values;
}

std::vector<double> ParseVectorWithUnit(
    const std::string& text,
    char delimiter
)
{
    std::vector<double> values;
    for (const std::string& item : StringUtils::Split(text, delimiter, true)) {
        values.push_back(ParseDoubleWithUnit(item));
    }
    return values;
}

}  // namespace UnitParser
