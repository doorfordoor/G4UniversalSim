#include "Geometry/GeometryConfigDiagnostic.hh"

#include "Config/IniReader.hh"
#include "Utils/StringUtils.hh"

#include <algorithm>
#include <sstream>
#include <set>

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
                    || StringUtils::StartsWith(key, "vis.") || IsCanonicalMetadata(key);
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
        if (mode == "hierarchical" || mode == "hierarchical_boolean" || mode == "boolean_hierarchical" || mode == "boolean") {
            if (IsBooleanSection(section)) return key == "name" || key == "operation" || key == "shape" || key == "size" || key == "parameters" || key == "position" || key == "rotation";
            if (IsOrdinaryHierarchicalSection(section)) {
                return key == "name" || key == "parent" || key == "shape" || key == "size" || key == "parameters" || key == "material"
                    || key == "position" || key == "rotation" || key == "sensitive" || key == "bias" || key == "region"
                    || key == "placement" || key == "copyno" || key == "copyNo" || StringUtils::StartsWith(key, "vis.")
                    || IsCut(key) || IsCanonicalMetadata(key);
            }
        }
        return false;
    };

    const auto validSection = [&](const std::string& section) {
        if (mode == "simple_box") return section == "global" || section == "world" || section == "target" || section == "visual.world" || section == "visual.target";
        if (mode == "layered_device") return section == "global" || section == "world" || section == "layers" || (StringUtils::StartsWith(section, "layer.") && layerNames.count(section.substr(6)));
        if (mode == "array") return section == "global" || section == "world" || section == "array";
        if (mode == "shielding") return section == "global" || section == "world" || section == "shielding" || section == "detector" || (StringUtils::StartsWith(section, "shield.") && shieldNames.count(section.substr(7)));
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
            AddDiagnostic(filename, &field, "unconsumed_key", "implicit global fields are not consumed by geometry templates", "Move the field into a supported geometry section.", diagnostics);
            continue;
        }
        if (!validSection(section)) continue;
        if (known(section, key)) continue;
        if ((mode == "hierarchical" || mode == "hierarchical_boolean" || mode == "boolean_hierarchical" || mode == "boolean")
            && IsBooleanSection(section) && (key == "material" || key == "sensitive" || key == "bias" || key == "region" || key == "parent" || key == "placement" || key == "copyno" || IsCut(key) || StringUtils::StartsWith(key, "vis."))) {
            AddDiagnostic(filename, &field, "ignored_boolean_key", "boolean tool ignores volume-only field", "Remove the field from the boolean section.", diagnostics);
        } else if ((mode == "layered_device" || mode == "hierarchical" || mode == "hierarchical_boolean" || mode == "boolean_hierarchical" || mode == "boolean")
            && !IsCanonicalMetadata(key)) {
            AddDiagnostic(filename, &field, "legacy_metadata", "legacy unprefixed metadata is preserved but not interpreted", "Rename it to metadata." + OriginalKey(field) + " in a future migration.", diagnostics);
        } else {
            AddDiagnostic(filename, &field, "unconsumed_key", "key is not consumed by the selected geometry template", "Remove the key or use a supported field.", diagnostics);
        }
    }
    SortAndDeduplicateGeometryDiagnostics(diagnostics);
}
