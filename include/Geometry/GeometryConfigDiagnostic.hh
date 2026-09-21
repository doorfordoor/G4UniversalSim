#pragma once

#include <cstddef>
#include <string>
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

void SortAndDeduplicateGeometryDiagnostics(std::vector<GeometryConfigDiagnostic>& diagnostics);

void CollectGeometryConfigDiagnostics(
    const std::string& filename,
    const std::vector<IniFieldInfo>& fields,
    const std::vector<IniSectionInfo>& sections,
    const std::string& templateName,
    std::vector<GeometryConfigDiagnostic>& diagnostics
);
