#pragma once

#include "Config/IniReader.hh"

#include <set>
#include <string>

class ConfigManager;

namespace GeometrySafety {

std::string Normalize(const std::string& value);

void ValidateProductionCuts(
    const ConfigManager& config,
    const std::set<std::string>& allowedSections
);

void ValidateFixedBoxShape(
    const ConfigManager& config,
    const std::string& section,
    const std::string& owner
);

[[noreturn]] void ThrowFieldError(
    const ConfigManager& config,
    const IniFieldInfo& field,
    const std::string& message,
    const std::string& suggestion = ""
);

}  // namespace GeometrySafety
