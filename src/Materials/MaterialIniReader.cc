#include "Materials/MaterialIniReader.hh"

#include "Materials/MaterialCommandParser.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <algorithm>
#include <limits>

namespace {

int ParseRequiredInt(
    const MaterialIniReader::Section& sectionData,
    const std::string& filename,
    const std::string& section,
    const std::string& key
)
{
    const std::string value = MaterialIniReader::Require(sectionData, filename, section, key);
    char* end = nullptr;
    const long parsed = std::strtol(value.c_str(), &end, 10);
    if (end == value.c_str() || !StringUtils::Trim(std::string(end)).empty()) {
        throw MaterialIniReader::Error(filename, section, key, "expected integer, got '" + value + "'");
    }
    return static_cast<int>(parsed);
}

double ParseRequiredDouble(
    const MaterialIniReader::Section& sectionData,
    const std::string& filename,
    const std::string& section,
    const std::string& key
)
{
    const std::string value = MaterialIniReader::Require(sectionData, filename, section, key);
    char* end = nullptr;
    const double parsed = std::strtod(value.c_str(), &end);
    if (end == value.c_str() || !StringUtils::Trim(std::string(end)).empty()) {
        throw MaterialIniReader::Error(filename, section, key, "expected number, got '" + value + "'");
    }
    return parsed;
}

double SumAbundance(const std::vector<IsotopeComponent>& isotopes)
{
    double sum = 0.0;
    for (const auto& isotope : isotopes) sum += isotope.abundance;
    return sum;
}

std::string Suggestion(const std::string& value, const std::vector<std::string>& candidates)
{
    const std::string target = StringUtils::ToLower(StringUtils::Trim(value));
    std::size_t best = std::numeric_limits<std::size_t>::max();
    std::string match;
    for (const auto& candidate : candidates) {
        const std::string normalized = StringUtils::ToLower(candidate);
        std::vector<std::size_t> previous(normalized.size() + 1);
        std::vector<std::size_t> current(normalized.size() + 1);
        for (std::size_t j = 0; j <= normalized.size(); ++j) previous[j] = j;
        for (std::size_t i = 1; i <= target.size(); ++i) {
            current[0] = i;
            for (std::size_t j = 1; j <= normalized.size(); ++j) {
                current[j] = std::min({previous[j] + 1, current[j - 1] + 1,
                                       previous[j - 1] + (target[i - 1] == normalized[j - 1] ? 0 : 1)});
            }
            previous.swap(current);
        }
        if (previous.back() < best) { best = previous.back(); match = candidate; }
    }
    return best <= 3 && !match.empty() ? match : "";
}

std::string SchemaMessage(const std::string& key, const std::vector<std::string>& allowed)
{
    const std::string suggestion = Suggestion(key, allowed);
    return suggestion.empty()
        ? "unknown material configuration key"
        : "unknown material configuration key; did you mean '" + suggestion + "'?";
}

}  // namespace

void MaterialIniReader::Load(const std::string& filename)
{
    Clear();
    if (!FileUtils::IsFile(filename)) {
        throw std::runtime_error("Material ini file does not exist: '" + filename + "'");
    }

    std::ifstream input(filename);
    if (!input) {
        throw std::runtime_error("Failed to open material ini file: '" + filename + "'");
    }

    std::map<std::string, Section> sections;
    SourceMap sources;
    std::map<std::string, std::size_t> sectionLines;
    std::string currentSection = "global";
    sections[currentSection];
    sectionLines[currentSection] = 0;

    std::string line;
    std::size_t lineNumber = 0;
    while (std::getline(input, line)) {
        ++lineNumber;
        const std::string clean = StringUtils::Trim(StringUtils::RemoveComment(line));
        if (clean.empty()) continue;

        if (clean.front() == '[') {
            if (clean.back() != ']') {
                throw std::runtime_error(
                    "Material ini parse error in '" + filename + "' line "
                    + std::to_string(lineNumber) + ": missing closing ']'"
                );
            }
            currentSection = StringUtils::Trim(clean.substr(1, clean.size() - 2));
            if (currentSection.empty()) {
                throw std::runtime_error(
                    "Material ini parse error in '" + filename + "' line "
                    + std::to_string(lineNumber) + ": empty section"
                );
            }
            sections[currentSection];
            sectionLines[currentSection] = lineNumber;
            continue;
        }

        const auto pos = clean.find('=');
        if (pos == std::string::npos) {
            throw std::runtime_error(
                "Material ini parse error in '" + filename + "' line "
                + std::to_string(lineNumber) + ": expected key=value"
            );
        }
        const std::string key = StringUtils::ToLower(StringUtils::Trim(clean.substr(0, pos)));
        const std::string value = StringUtils::Trim(clean.substr(pos + 1));
        if (key.empty()) {
            throw std::runtime_error(
                "Material ini parse error in '" + filename + "' line "
                + std::to_string(lineNumber) + ": empty key"
            );
        }
        sections[currentSection][key] = value;
        sources[currentSection][key] = {currentSection, StringUtils::Trim(clean.substr(0, pos)), value, lineNumber};
    }

    ParseSections(filename, sections, sources, sectionLines);
}

bool MaterialIniReader::HasIsotope(const std::string& name) const
{
    return isotopes_.find(Normalize(name)) != isotopes_.end();
}

bool MaterialIniReader::HasElement(const std::string& name) const
{
    return elements_.find(Normalize(name)) != elements_.end();
}

bool MaterialIniReader::HasMaterial(const std::string& name) const
{
    return materials_.find(Normalize(name)) != materials_.end();
}

const IsotopeDefinition& MaterialIniReader::GetIsotopeDefinition(const std::string& name) const
{
    const auto it = isotopes_.find(Normalize(name));
    if (it == isotopes_.end()) throw std::runtime_error("Unknown isotope definition: '" + name + "'");
    return it->second;
}

const ElementDefinition& MaterialIniReader::GetElementDefinition(const std::string& name) const
{
    const auto it = elements_.find(Normalize(name));
    if (it == elements_.end()) throw std::runtime_error("Unknown element definition: '" + name + "'");
    return it->second;
}

const MaterialDefinition& MaterialIniReader::GetMaterialDefinition(const std::string& name) const
{
    const auto it = materials_.find(Normalize(name));
    if (it == materials_.end()) throw std::runtime_error("Unknown material definition: '" + name + "'");
    return it->second;
}

std::vector<std::string> MaterialIniReader::GetIsotopeNames() const
{
    std::vector<std::string> names;
    for (const auto& item : isotopes_) names.push_back(item.second.name);
    return names;
}

std::vector<std::string> MaterialIniReader::GetElementNames() const
{
    std::vector<std::string> names;
    for (const auto& item : elements_) names.push_back(item.second.name);
    return names;
}

std::vector<std::string> MaterialIniReader::GetMaterialNames() const
{
    std::vector<std::string> names;
    for (const auto& item : materials_) names.push_back(item.second.name);
    return names;
}

std::vector<std::string> MaterialIniReader::GetNistMaterialNames() const
{
    return nistMaterials_;
}

void MaterialIniReader::Clear()
{
    nistMaterials_.clear();
    isotopes_.clear();
    elements_.clear();
    materials_.clear();
}

std::string MaterialIniReader::Normalize(const std::string& name)
{
    return StringUtils::ToLower(StringUtils::Trim(name));
}

std::runtime_error MaterialIniReader::Error(
    const std::string& filename,
    const std::string& section,
    const std::string& key,
    const std::string& message
)
{
    return std::runtime_error(
        "Material ini error in file '" + filename + "', section '" + section
        + "', key '" + key + "': " + message
    );
}

std::runtime_error MaterialIniReader::SchemaError(
    const std::string& filename,
    std::size_t lineNumber,
    const std::string& section,
    const std::string& key,
    const std::string& value,
    const std::string& message
)
{
    return std::runtime_error(
        "Material schema error: file '" + filename + "', line " + std::to_string(lineNumber)
        + ", section '" + section + "', key '" + key + "', value '" + value + "': " + message
    );
}

std::string MaterialIniReader::Require(
    const Section& sectionData,
    const std::string& filename,
    const std::string& section,
    const std::string& key
)
{
    const auto it = sectionData.find(StringUtils::ToLower(key));
    if (it == sectionData.end() || StringUtils::Trim(it->second).empty()) {
        throw Error(filename, section, key, "missing required key");
    }
    return it->second;
}

void MaterialIniReader::ParseSections(
    const std::string& filename,
    const std::map<std::string, Section>& sections,
    const SourceMap& sources,
    const std::map<std::string, std::size_t>& sectionLines
)
{
    const std::vector<std::string> nistKeys = {"materials"};
    const std::vector<std::string> isotopeKeys = {"symbol", "z", "n", "a"};
    const std::vector<std::string> elementKeys = {"symbol", "isotopes", "z", "a"};
    const std::vector<std::string> materialKeys = {"type", "mode", "density", "components", "state", "temperature", "pressure"};
    const std::vector<std::string> aliasKeys = {"material"};

    for (const auto& sectionPair : sections) {
        const std::string& section = sectionPair.first;
        const std::string sectionLower = StringUtils::ToLower(section);
        const auto sourceIt = sources.find(section);
        const auto& sectionSource = sourceIt == sources.end()
            ? SourceMap::mapped_type{}
            : sourceIt->second;
        std::vector<std::string> allowed;
        bool known = false;
        bool legacy = false;
        if (sectionLower == "global") {
            known = true;
            allowed = {};
        } else if (sectionLower == "nist") {
            known = true;
            allowed = nistKeys;
        } else if (StringUtils::StartsWith(sectionLower, "isotope.")) {
            known = true;
            allowed = isotopeKeys;
            if (section.substr(std::string("isotope.").size()).empty()) {
                throw SchemaError(filename, sectionLines.at(section), section, "<section>", "", "section suffix must not be empty");
            }
        } else if (StringUtils::StartsWith(sectionLower, "element.")) {
            known = true;
            allowed = elementKeys;
            if (section.substr(std::string("element.").size()).empty()) {
                throw SchemaError(filename, sectionLines.at(section), section, "<section>", "", "section suffix must not be empty");
            }
        } else if (StringUtils::StartsWith(sectionLower, "material.")) {
            known = true;
            allowed = materialKeys;
            if (section.substr(std::string("material.").size()).empty()) {
                throw SchemaError(filename, sectionLines.at(section), section, "<section>", "", "section suffix must not be empty");
            }
        } else if (sectionPair.second.find("material") != sectionPair.second.end()) {
            known = true;
            legacy = true;
            allowed = aliasKeys;
        }

        if (!known) {
            if (!sectionPair.second.empty()) {
                const auto& field = *sectionPair.second.begin();
                const auto fieldSourceIt = sectionSource.find(field.first);
                const SourceInfo source = fieldSourceIt == sectionSource.end()
                    ? SourceInfo{section, field.first, field.second, sectionLines.at(section)}
                    : fieldSourceIt->second;
                throw SchemaError(filename, source.lineNumber, source.section, source.key, source.value,
                                  "unknown material configuration section");
            }
            throw SchemaError(filename, sectionLines.at(section), section, "<section>", "", "unknown material configuration section");
        }
        for (const auto& field : sectionPair.second) {
            const auto fieldSourceIt = sectionSource.find(field.first);
            const SourceInfo source = fieldSourceIt == sectionSource.end()
                ? SourceInfo{section, field.first, field.second, sectionLines.at(section)}
                : fieldSourceIt->second;
            if (std::find(allowed.begin(), allowed.end(), field.first) == allowed.end()) {
                throw SchemaError(filename, source.lineNumber, source.section, source.key, source.value,
                                  SchemaMessage(source.key, allowed));
            }
            if (!legacy && !StringUtils::StartsWith(sectionLower, "material.")) {
                continue;
            }
            if (!legacy && (field.first == "temperature" || field.first == "pressure")) {
                throw SchemaError(filename, source.lineNumber, source.section, source.key, source.value,
                                  "unsupported temperature/pressure field; remove it and use density, state, and composition only");
            }
            if (!legacy && field.first == "type"
                && StringUtils::ToLower(StringUtils::Trim(field.second)) != "material") {
                throw SchemaError(filename, source.lineNumber, source.section, source.key, source.value,
                                  "deprecated compatibility field 'type' only accepts 'material'");
            }
        }
    }

    for (const auto& sectionPair : sections) {
        const std::string& section = sectionPair.first;
        const Section& data = sectionPair.second;
        const std::string sectionLower = StringUtils::ToLower(section);

        if (sectionLower == "nist") {
            const auto it = data.find("materials");
            if (it != data.end()) {
                for (const std::string& name : StringUtils::Split(it->second, ',', true)) {
                    const std::string trimmed = StringUtils::Trim(name);
                    if (!trimmed.empty()) nistMaterials_.push_back(trimmed);
                }
            }
            continue;
        }

        if (StringUtils::StartsWith(sectionLower, "isotope.")) {
            const std::string name = section.substr(std::string("isotope.").size());
            IsotopeDefinition def;
            def.name = name;
            def.symbol = Require(data, filename, section, "symbol");
            def.z = ParseRequiredInt(data, filename, section, "z");
            def.n = ParseRequiredInt(data, filename, section, "n");
            def.aText = Require(data, filename, section, "a");
            if (def.z <= 0 || def.n <= 0) throw Error(filename, section, "z/n", "z and n must be positive");
            def.a = MaterialCommandParser::ParseMolarMass(def.aText);
            isotopes_[Normalize(def.name)] = def;
            continue;
        }

        if (StringUtils::StartsWith(sectionLower, "element.")) {
            const std::string name = section.substr(std::string("element.").size());
            ElementDefinition def;
            def.name = name;
            def.symbol = Require(data, filename, section, "symbol");
            const bool hasIsotopes = data.find("isotopes") != data.end();
            const bool hasZA = data.find("z") != data.end() || data.find("a") != data.end();
            if (hasIsotopes && hasZA) {
                throw Error(filename, section, "isotopes", "do not mix isotope element and z/a element definitions");
            }
            if (hasIsotopes) {
                def.useIsotopes = true;
                def.isotopes = MaterialCommandParser::ParseIsotopeComponents(data.at("isotopes"));
                if (def.isotopes.empty()) throw Error(filename, section, "isotopes", "isotope list is empty");
                const double sum = SumAbundance(def.isotopes);
                if (std::abs(sum - 1.0) > 1.0e-6) {
                    throw Error(filename, section, "isotopes", "abundance sum must be 1.0; got " + std::to_string(sum));
                }
            } else {
                def.z = ParseRequiredDouble(data, filename, section, "z");
                def.aText = Require(data, filename, section, "a");
                def.a = MaterialCommandParser::ParseMolarMass(def.aText);
            }
            elements_[Normalize(def.name)] = def;
            continue;
        }

        if (StringUtils::StartsWith(sectionLower, "material.")) {
            const std::string name = section.substr(std::string("material.").size());
            MaterialDefinition def;
            def.name = name;
            const std::string modeText = data.count("mode") ? data.at("mode") : "mass_fraction";
            const auto mode = MaterialCommandParser::ParseMode(modeText);
            const auto densityIt = data.find("density");
            if (densityIt != data.end()) {
                def.densityText = densityIt->second;
                if (MaterialCommandParser::IsAutoDensity(def.densityText)) {
                    if (mode != MaterialComponentMode::ByVolumeFraction) {
                        throw Error(filename, section, "density", "density=auto is only supported for mode=volume_fraction");
                    }
                    def.densityAuto = true;
                } else {
                    def.density = MaterialCommandParser::ParseDensity(def.densityText);
                    def.densitySpecified = true;
                }
            } else if (mode == MaterialComponentMode::ByVolumeFraction) {
                def.densityText = "auto";
                def.densityAuto = true;
            } else {
                throw Error(filename, section, "density", "missing required key");
            }
            def.components = MaterialCommandParser::ParseMaterialComponents(
                Require(data, filename, section, "components"),
                mode
            );
            if (def.components.empty()) throw Error(filename, section, "components", "component list is empty");
            if (data.count("state")) def.state = data.at("state");
            if (data.count("temperature")) def.temperatureText = data.at("temperature");
            if (data.count("pressure")) def.pressureText = data.at("pressure");
            materials_[Normalize(def.name)] = def;
            continue;
        }

        // Legacy convenience format: [Alias] material = G4_AIR
        const auto materialIt = data.find("material");
        if (materialIt != data.end()) {
            MaterialDefinition def;
            def.name = section;
            def.source = MaterialSourceType::Nist;
            def.nistName = materialIt->second;
            materials_[Normalize(def.name)] = def;
            nistMaterials_.push_back(materialIt->second);
        }
    }
}
