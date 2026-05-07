#include "Config/ConfigValue.hh"

#include "Utils/StringUtils.hh"

#include <cstdlib>
#include <stdexcept>

namespace {

double ParseStrictDouble(const std::string& value, const std::string& typeName)
{
    const std::string trimmed = StringUtils::Trim(value);
    if (trimmed.empty()) {
        throw std::runtime_error("Cannot parse empty config value as " + typeName);
    }

    char* end = nullptr;
    const double parsed = std::strtod(trimmed.c_str(), &end);
    if (end == trimmed.c_str() || !StringUtils::Trim(std::string(end)).empty()) {
        throw std::runtime_error(
            "Cannot parse config value '" + value + "' as " + typeName
        );
    }

    return parsed;
}

int ParseStrictInt(const std::string& value)
{
    const std::string trimmed = StringUtils::Trim(value);
    if (trimmed.empty()) {
        throw std::runtime_error("Cannot parse empty config value as int");
    }

    char* end = nullptr;
    const long parsed = std::strtol(trimmed.c_str(), &end, 10);
    if (end == trimmed.c_str() || !StringUtils::Trim(std::string(end)).empty()) {
        throw std::runtime_error("Cannot parse config value '" + value + "' as int");
    }

    return static_cast<int>(parsed);
}

}  // namespace

ConfigValue::ConfigValue(const std::string& value)
    : value_(value)
{
}

const std::string& ConfigValue::AsString() const
{
    return value_;
}

int ConfigValue::AsInt() const
{
    return ParseStrictInt(value_);
}

double ConfigValue::AsDouble() const
{
    return ParseStrictDouble(value_, "double");
}

bool ConfigValue::AsBool() const
{
    return StringUtils::ToBool(value_);
}

std::vector<std::string> ConfigValue::AsStringVector(char delimiter) const
{
    std::vector<std::string> result;
    for (const std::string& item : StringUtils::Split(value_, delimiter, true)) {
        const std::string trimmed = StringUtils::Trim(item);
        if (!trimmed.empty()) {
            result.push_back(trimmed);
        }
    }
    return result;
}

std::vector<int> ConfigValue::AsIntVector(char delimiter) const
{
    std::vector<int> result;
    for (const std::string& item : AsStringVector(delimiter)) {
        result.push_back(ParseStrictInt(item));
    }
    return result;
}

std::vector<double> ConfigValue::AsDoubleVector(char delimiter) const
{
    std::vector<double> result;
    for (const std::string& item : AsStringVector(delimiter)) {
        result.push_back(ParseStrictDouble(item, "double"));
    }
    return result;
}

bool ConfigValue::Empty() const
{
    return value_.empty();
}
