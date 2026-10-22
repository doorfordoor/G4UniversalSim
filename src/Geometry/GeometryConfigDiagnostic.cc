#include "Geometry/GeometryConfigDiagnostic.hh"

#include "Config/IniReader.hh"
#include "Utils/StringUtils.hh"

#include <algorithm>
#include <fstream>
#include <sstream>
#include <set>
#include <stdexcept>

std::string GeometryConfigDiagnostic::FormatWarning() const
{
    std::ostringstream text;
    text << "[GeometryConfigWarning] " << filename << ":" << line << " [" << section << "]";
    if (!key.empty()) text << "/" << key << " = " << value;
    text << ": " << message;
    if (!suggestion.empty()) text << "; " << suggestion;
    return text.str();
}

void SortAndDeduplicateGeometryDiagnostics(std::vector<GeometryConfigDiagnostic>& diagnostics)
{
    const auto less = [](const GeometryConfigDiagnostic& left, const GeometryConfigDiagnostic& right) {
        if (left.filename != right.filename) return left.filename < right.filename;
        if (left.line != right.line) return left.line < right.line;
        if (left.section != right.section) return left.section < right.section;
        if (left.key != right.key) return left.key < right.key;
        if (left.value != right.value) return left.value < right.value;
        if (left.code != right.code) return left.code < right.code;
        return left.message < right.message;
    };
    std::sort(diagnostics.begin(), diagnostics.end(), less);
    diagnostics.erase(std::unique(diagnostics.begin(), diagnostics.end(), [](const auto& left, const auto& right) {
        return left.code == right.code && left.category == right.category && left.filename == right.filename
            && left.line == right.line && left.section == right.section && left.key == right.key
            && left.value == right.value && left.message == right.message && left.suggestion == right.suggestion;
    }), diagnostics.end());
}

namespace {

std::string Normalize(const std::string& value)
{
    return StringUtils::ToLower(StringUtils::Trim(value));
}

std::string OriginalSection(const IniSectionInfo& section)
{
    return section.originalSection.empty() ? section.section : section.originalSection;
}

std::string NormalizedSection(const IniSectionInfo& section)
{
    return section.normalizedSection.empty() ? section.section : section.normalizedSection;
}

std::string OriginalSection(const IniFieldInfo& field)
{
    return field.originalSection.empty() ? field.section : field.originalSection;
}

std::string NormalizedSection(const IniFieldInfo& field)
{
    return field.normalizedSection.empty() ? field.section : field.normalizedSection;
}

std::string OriginalKey(const IniFieldInfo& field)
{
    return field.originalKey.empty() ? field.key : field.originalKey;
}

std::string NormalizedKey(const IniFieldInfo& field)
{
    return field.normalizedKey.empty() ? Normalize(field.key) : field.normalizedKey;
}

std::set<std::string> SplitNames(const std::vector<IniFieldInfo>& fields, const std::string& section, const std::string& key)
{
    std::set<std::string> result;
    for (const auto& field : fields) {
        if (NormalizedSection(field) != section || NormalizedKey(field) != key) continue;
        for (const auto& item : StringUtils::Split(field.value, ',', true)) {
            const auto name = Normalize(item);
            if (!name.empty()) result.insert(name);
        }
    }
    return result;
}

bool IsCut(const std::string& key)
{
    return StringUtils::StartsWith(key, "cut.");
}

bool IsKnownVisual(const std::string& key)
{
    return key == "vis.color" || key == "vis.alpha" || key == "vis.visible" || key == "vis.wireframe";
}

void RejectDuplicateGeometryVersion(const std::string& filename)
{
    // IniReader intentionally keeps only the last value of a repeated key.
    // Inspect the geometry source so a repeated strict-mode declaration cannot disappear.
    std::ifstream input(filename);
    if (!input) throw std::runtime_error("Cannot inspect geometry schema version in file '" + filename + "'");
    std::string section = "global";
    std::string line;
    std::size_t lineNumber = 0;
    bool seen = false;
    while (std::getline(input, line)) {
        ++lineNumber;
        const std::string clean = StringUtils::Trim(StringUtils::RemoveComment(line));
        if (clean.empty()) continue;
        if (clean.front() == '[' && clean.back() == ']') {
            section = Normalize(clean.substr(1, clean.size() - 2));
            continue;
        }
        const auto equal = clean.find('=');
        if (section != "global" || equal == std::string::npos
            || Normalize(clean.substr(0, equal)) != "version") continue;
        if (seen) {
            throw std::runtime_error("Geometry config schema error in file '" + filename + "', line "
                + std::to_string(lineNumber) + ", section '[global]', key '"
                + StringUtils::Trim(clean.substr(0, equal)) + "', value '"
                + StringUtils::Trim(clean.substr(equal + 1))
                + "': duplicate geometry version declaration");
        }
        seen = true;
    }
}

void RejectStrictDuplicateGeometryDeclarations(const std::string& filename)
{
    // IniReader stores the last occurrence of each normalized section/key.
    // Version 2 must reject that ambiguity before a geometry object is created.
    std::ifstream input(filename);
    if (!input) throw std::runtime_error("Cannot inspect geometry declarations in file '" + filename + "'");
    std::set<std::string> sections;
    std::set<std::pair<std::string, std::string>> keys;
    std::string section = "global";
    std::string originalSection = "global";
    std::string line;
    std::size_t lineNumber = 0;
    while (std::getline(input, line)) {
        ++lineNumber;
        const std::string clean = StringUtils::Trim(StringUtils::RemoveComment(line));
        if (clean.empty()) continue;
        if (clean.front() == '[' && clean.back() == ']') {
            originalSection = StringUtils::Trim(clean.substr(1, clean.size() - 2));
            section = Normalize(originalSection);
            if (!sections.insert(section).second) {
                throw std::runtime_error("Geometry version=2 schema rejected duplicate_section in file '"
                    + filename + "', line " + std::to_string(lineNumber) + ", section '["
                    + originalSection + "]': repeated section would overwrite earlier declarations");
            }
            continue;
        }
        const auto equal = clean.find('=');
        if (equal == std::string::npos) continue; // IniReader reports malformed lines first.
        const std::string originalKey = StringUtils::Trim(clean.substr(0, equal));
        const std::string key = Normalize(originalKey);
        if (!keys.insert({section, key}).second) {
            throw std::runtime_error("Geometry version=2 schema rejected duplicate_key in file '"
                + filename + "', line " + std::to_string(lineNumber) + ", section '["
                + originalSection + "]', key '" + originalKey + "', value '"
                + StringUtils::Trim(clean.substr(equal + 1))
                + "': repeated key would overwrite an earlier value");
        }
    }
    if (input.bad()) {
        throw std::runtime_error("Failed while inspecting geometry declarations in file '" + filename + "'");
    }
}

bool IsCanonicalMetadata(const std::string& key)
{
    return StringUtils::StartsWith(key, "metadata.") && key.size() > std::string("metadata.").size();
}

bool IsEmptyMetadata(const std::string& key)
{
    return key == "metadata.";
}

bool IsBooleanSection(const std::string& section)
{
    const auto marker = section.find(".boolean.");
    if (!StringUtils::StartsWith(section, "volume.") || marker == std::string::npos) return false;
    const auto target = section.substr(std::string("volume.").size(), marker - std::string("volume.").size());
    const auto index = section.substr(marker + std::string(".boolean.").size());
    return !target.empty() && !index.empty() && index.find_first_not_of("0123456789") == std::string::npos;
}

bool IsOrdinaryHierarchicalSection(const std::string& section)
{
    return section == "world"
        || (StringUtils::StartsWith(section, "volume.")
            && section.size() > std::string("volume.").size()
            && section.find(".boolean.") == std::string::npos);
}

void AddDiagnostic(
    const std::string& filename,
    const IniFieldInfo* field,
    const std::string& code,
    const std::string& message,
    const std::string& suggestion,
    std::vector<GeometryConfigDiagnostic>& diagnostics,
    const std::string& sectionOverride = {},
    std::size_t lineOverride = 0
)
{
    GeometryConfigDiagnostic diagnostic;
    diagnostic.code = code;
    diagnostic.category = code;
    diagnostic.filename = filename;
    diagnostic.line = field ? field->lineNumber : lineOverride;
    diagnostic.section = field ? OriginalSection(*field) : sectionOverride;
    diagnostic.key = field ? OriginalKey(*field) : "";
    diagnostic.value = field ? field->value : "";
    diagnostic.message = message;
    diagnostic.suggestion = suggestion;
    diagnostics.push_back(std::move(diagnostic));
}

}  // namespace

void CollectGeometryConfigDiagnostics(
    const std::string& filename,
    const std::vector<IniFieldInfo>& fields,
    const std::vector<IniSectionInfo>& sections,
    const std::string& templateName,
    std::vector<GeometryConfigDiagnostic>& diagnostics
)
{
    RejectDuplicateGeometryVersion(filename);
    const std::string mode = Normalize(templateName);
    const auto layerNames = SplitNames(fields, "layers", "names");
    const auto shieldNames = SplitNames(fields, "shielding", "layers");
    const auto known = [&](const std::string& section, const std::string& key) {
        if (mode == "simple_box") {
            if (section == "world") return std::set<std::string>{"size", "material"}.count(key) > 0;
            if (section == "target") return key == "name" || key == "shape" || key == "size" || key == "material"
                || key == "position" || key == "rotation" || key == "sensitive" || key == "bias" || key == "region" || IsCut(key);
            if (section == "visual.world" || section == "visual.target") return key == "color" || key == "alpha" || key == "visible" || key == "wireframe";
            return false;
        }
        if (mode == "layered_device") {
            if (section == "world") return key == "size" || key == "material" || key == "shape";
            if (section == "layers") return key == "count" || key == "names" || key == "auto_stack" || key == "axis" || key == "gap" || key == "z_start";
            if (StringUtils::StartsWith(section, "layer.") && layerNames.count(section.substr(6))) {
                return key == "thickness" || key == "xy" || key == "material" || key == "position" || key == "rotation"
                    || key == "sensitive" || key == "bias" || key == "region" || key == "copyno" || IsCut(key)
                    || IsKnownVisual(key) || IsCanonicalMetadata(key);
            }
            return false;
        }
        if (mode == "array") {
            if (section == "world") return key == "size" || key == "material" || key == "shape";
            if (section == "array") return key == "name" || key == "shape" || key == "material" || key == "element_size"
                || key == "counts" || key == "pitch" || key == "center" || key == "sensitive" || key == "bias" || key == "region";
            return false;
        }
        if (mode == "shielding") {
            if (section == "world") return key == "size" || key == "material" || key == "shape";
            if (section == "shielding") return key == "axis" || key == "area" || key == "start" || key == "gap" || key == "layers";
            if (StringUtils::StartsWith(section, "shield.") && shieldNames.count(section.substr(7))) {
                return key == "thickness" || key == "material" || key == "bias" || key == "sensitive" || key == "region";
            }
            if (section == "detector") return key == "size" || key == "material" || key == "position" || key == "sensitive" || key == "region";
            return false;
        }
        if (mode == "gdml") {
            return section == "gdml" && (key == "file" || key == "validate" || key == "sensitive_volumes"
                                         || key == "bias_volumes" || key == "world_name");
        }
        if (mode == "hierarchical" || mode == "hierarchical_boolean" || mode == "boolean_hierarchical" || mode == "boolean") {
            if (IsBooleanSection(section)) return key == "name" || key == "operation" || key == "shape" || key == "size" || key == "parameters" || key == "position" || key == "rotation";
            if (IsOrdinaryHierarchicalSection(section)) {
                return key == "name" || key == "parent" || key == "shape" || key == "size" || key == "parameters" || key == "material"
                    || key == "position" || key == "rotation" || key == "sensitive" || key == "bias" || key == "region"
                    || key == "placement" || key == "copyno" || key == "copyNo" || IsKnownVisual(key)
                    || IsCut(key) || IsCanonicalMetadata(key)
                    // roadmap A5 shape and placement fields
                    || key == "z_planes" || key == "r_inner" || key == "r_outer" || key == "file" || key == "file_unit"
                    || key == "replica_axis" || key == "replica_count" || key == "replica_width" || key == "replica_offset"
                    || key == "copies_file" || key == "copies" || key == "copy_step";
            }
        }
        return false;
    };

    const auto validSection = [&](const std::string& section) {
        if (mode == "simple_box") return section == "global" || section == "world" || section == "target" || section == "visual.world" || section == "visual.target";
        if (mode == "layered_device") return section == "global" || section == "world" || section == "layers" || (StringUtils::StartsWith(section, "layer.") && layerNames.count(section.substr(6)));
        if (mode == "array") return section == "global" || section == "world" || section == "array";
        if (mode == "shielding") return section == "global" || section == "world" || section == "shielding" || section == "detector" || (StringUtils::StartsWith(section, "shield.") && shieldNames.count(section.substr(7)));
        if (mode == "gdml") return section == "global" || section == "gdml";
        if (mode == "hierarchical" || mode == "hierarchical_boolean" || mode == "boolean_hierarchical" || mode == "boolean") return section == "global" || IsOrdinaryHierarchicalSection(section) || IsBooleanSection(section);
        return false;
    };

    for (const auto& section : sections) {
        const std::string normalized = NormalizedSection(section);
        if (normalized == "global") continue;
        if (!validSection(normalized)) {
            GeometryConfigDiagnostic diagnostic;
            diagnostic.code = "unknown_section";
            diagnostic.category = "schema";
            diagnostic.filename = filename;
            diagnostic.line = section.lineNumber;
            diagnostic.section = OriginalSection(section);
            diagnostic.message = "section is not recognized by the selected geometry template";
            diagnostic.suggestion = "Use a supported section for the selected template.";
            diagnostics.push_back(std::move(diagnostic));
        }
    }

    for (const auto& field : fields) {
        const std::string section = NormalizedSection(field);
        const std::string key = NormalizedKey(field);
        if (IsEmptyMetadata(key)) {
            throw std::runtime_error(
                "Geometry config error in file '" + filename + "', line " + std::to_string(field.lineNumber)
                + ", section '[" + OriginalSection(field) + "]', key '" + OriginalKey(field)
                + "', value '" + field.value + "': metadata namespace requires a non-empty name"
            );
        }
        if (section == "global") {
            if (key == "version") continue;
            AddDiagnostic(filename, &field, "unconsumed_key", "implicit global fields are not consumed by geometry templates", "Move the field into a supported geometry section.", diagnostics);
            continue;
        }
        if (!validSection(section)) continue;
        if (known(section, key)) continue;
        if ((mode == "hierarchical" || mode == "hierarchical_boolean" || mode == "boolean_hierarchical" || mode == "boolean")
            && IsBooleanSection(section) && (key == "material" || key == "sensitive" || key == "bias" || key == "region" || key == "parent" || key == "placement" || key == "copyno" || IsCut(key) || StringUtils::StartsWith(key, "vis."))) {
            AddDiagnostic(filename, &field, "ignored_boolean_key", "boolean tool ignores volume-only field", "Remove the field from the boolean section.", diagnostics);
        } else if (IsCut(key) || StringUtils::StartsWith(key, "vis.")) {
            AddDiagnostic(filename, &field, "unconsumed_key", "runtime field is not supported by the selected geometry template", "Use a supported cut.* or vis.* field for this section.", diagnostics);
        } else if ((mode == "layered_device" || mode == "hierarchical" || mode == "hierarchical_boolean" || mode == "boolean_hierarchical" || mode == "boolean")
            && !IsCanonicalMetadata(key)) {
            AddDiagnostic(filename, &field, "legacy_metadata", "legacy unprefixed metadata is preserved but not interpreted", "Rename it to metadata." + OriginalKey(field) + " in a future migration.", diagnostics);
        } else {
            AddDiagnostic(filename, &field, "unconsumed_key", "key is not consumed by the selected geometry template", "Remove the key or use a supported field.", diagnostics);
        }
    }
    SortAndDeduplicateGeometryDiagnostics(diagnostics);

    const IniFieldInfo* versionField = nullptr;
    for (const auto& field : fields) {
        if (NormalizedSection(field) != "global" || NormalizedKey(field) != "version") continue;
        if (versionField) {
            throw std::runtime_error("Geometry config schema error in file '" + filename + "', line "
                + std::to_string(field.lineNumber) + ", section '[" + OriginalSection(field)
                + "]', key '" + OriginalKey(field) + "', value '" + field.value
                + "': duplicate geometry version declaration");
        }
        versionField = &field;
    }
    if (!versionField) return;
    if (Normalize(versionField->value) == "1") return;
    if (Normalize(versionField->value) != "2") {
        throw std::runtime_error("Geometry config schema error in file '" + filename + "', line "
            + std::to_string(versionField->lineNumber) + ", section '[" + OriginalSection(*versionField)
            + "]', key '" + OriginalKey(*versionField) + "', value '" + versionField->value
            + "': supported geometry versions are 1 (legacy) and 2 (strict)");
    }
    RejectStrictDuplicateGeometryDeclarations(filename);
    if (!diagnostics.empty()) {
        const auto& first = diagnostics.front();
        throw std::runtime_error("Geometry version=2 schema rejected " + first.code + " in file '"
            + first.filename + "', line " + std::to_string(first.line) + ", section '["
            + first.section + "]', key '" + first.key + "', value '" + first.value
            + "': " + first.message + "; " + first.suggestion);
    }
}
