#include "Utils/G4NameUtils.hh"

#include <cctype>
#include <sstream>

namespace {

bool IsAllowedNameChar(unsigned char c)
{
    return std::isalnum(c) != 0 || c == '_';
}

std::string WithSuffix(const std::string& base, const std::string& suffix)
{
    return G4NameUtils::SanitizeName(base) + suffix;
}

}  // namespace

namespace G4NameUtils {

std::string SanitizeName(const std::string& raw)
{
    std::string result;
    result.reserve(raw.size());

    for (unsigned char c : raw) {
        result.push_back(IsAllowedNameChar(c) ? static_cast<char>(c) : '_');
    }

    return result.empty() ? "unnamed" : result;
}

std::string MakeUniqueName(const std::string& base, int index)
{
    std::ostringstream oss;
    oss << SanitizeName(base) << "_" << index;
    return oss.str();
}

std::string LogicalName(const std::string& base)
{
    return WithSuffix(base, "_LV");
}

std::string PhysicalName(const std::string& base)
{
    return WithSuffix(base, "_PV");
}

std::string SolidName(const std::string& base)
{
    return WithSuffix(base, "_Solid");
}

std::string RegionName(const std::string& base)
{
    return WithSuffix(base, "_Region");
}

}  // namespace G4NameUtils
