#include "Materials/MaterialIniReader.hh"

#include "Materials/MaterialCommandParser.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <stdexcept>

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
    std::string currentSection = "global";
    sections[currentSection];

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
    }

    ParseSections(filename, sections);
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
    const std::map<std::string, Section>& sections
)
{
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
            def.densityText = Require(data, filename, section, "density");
            def.density = MaterialCommandParser::ParseDensity(def.densityText);
            const std::string modeText = data.count("mode") ? data.at("mode") : "mass_fraction";
            const auto mode = MaterialCommandParser::ParseMode(modeText);
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
