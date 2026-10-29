#pragma once

#include <cstddef>
#include <algorithm>
#include <string>
#include <tuple>
#include <vector>

struct IniFieldInfo;
struct IniSectionInfo;
class ConfigManager;

struct GeometryConfigDiagnostic {
    std::string code;
    std::string category;
    std::string filename;
    std::size_t line = 0;
    std::string section;
    std::string key;
    std::string value;
    std::string message;
    std::string suggestion;

    std::string FormatWarning() const;
};

inline void SortAndDeduplicateGeometryDiagnostics(std::vector<GeometryConfigDiagnostic>& diagnostics)
{
    const auto identity = [](const GeometryConfigDiagnostic& item) {
        return std::tie(item.filename, item.line, item.section, item.key, item.value,
                        item.code, item.message, item.category, item.suggestion);
    };
    std::sort(diagnostics.begin(), diagnostics.end(), [&](const auto& left, const auto& right) {
        return identity(left) < identity(right);
    });
    diagnostics.erase(std::unique(diagnostics.begin(), diagnostics.end(), [&](const auto& left, const auto& right) {
        return identity(left) == identity(right);
    }), diagnostics.end());
}

void CollectGeometryConfigDiagnostics(
    const std::string& filename,
    const std::vector<IniFieldInfo>& fields,
    const std::vector<IniSectionInfo>& sections,
    const std::string& templateName,
    std::vector<GeometryConfigDiagnostic>& diagnostics,
    const std::string* acceptedBytes = nullptr
);
