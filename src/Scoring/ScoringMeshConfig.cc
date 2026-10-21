#include "Scoring/ScoringMeshConfig.hh"

#include "Config/ConfigManager.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4SystemOfUnits.hh"

#include <cctype>
#include <cmath>
#include <map>
#include <sstream>
#include <stdexcept>

namespace {

const std::string kPrefix = "scoring.mesh.";

struct QuantitySection {
    std::string name;      // original spelling
    std::string section;   // normalized section name
};

struct MeshSection {
    std::string name;      // original spelling
    std::string section;   // normalized section name
    std::vector<QuantitySection> quantities;
};

[[noreturn]] void Fail(const std::string& section, const std::string& message)
{
    throw std::runtime_error("Invalid [" + section + "]: " + message);
}

bool ValidName(const std::string& name)
{
    if (name.empty()) return false;
    for (const char c : name) {
        if (!(std::isalnum(static_cast<unsigned char>(c)) || c == '_' || c == '-')) return false;
    }
    return true;
}

std::string Number(double value)
{
    std::ostringstream out;
    out.precision(12);
    out << value;
    return out.str();
}

std::vector<double> Lengths(const ConfigManager& config, const std::string& section, const char* key,
                            std::size_t count)
{
    const std::string text = config.GetString(section, key);
    std::vector<double> values;
    for (const std::string& part : StringUtils::Split(text, ',')) {
        const std::string item = StringUtils::Trim(part);
        try {
            values.push_back(UnitParser::ParseLength(item));
        } catch (const std::exception& error) {
            Fail(section, std::string(key) + " = '" + text + "': " + error.what());
        }
    }
    if (values.size() != count) {
        Fail(section, std::string(key) + " needs " + std::to_string(count) + " comma-separated lengths");
    }
    for (const double value : values) {
        if (!std::isfinite(value)) Fail(section, std::string(key) + " must be finite");
    }
    return values;
}

std::vector<int> Bins(const ConfigManager& config, const std::string& section)
{
    const std::string text = config.GetString(section, "bins");
    std::vector<int> values;
    for (const std::string& part : StringUtils::Split(text, ',')) {
        const std::string item = StringUtils::Trim(part);
        std::size_t used = 0;
        int value = 0;
        try {
            value = std::stoi(item, &used);
        } catch (const std::exception&) {
            used = 0;
        }
        if (used != item.size() || value < 1) Fail(section, "bins = '" + text + "': expected three integers >= 1");
        values.push_back(value);
    }
    if (values.size() != 3) Fail(section, "bins needs three comma-separated integers");
    return values;
}

std::vector<MeshSection> FindSections(const ConfigManager& config)
{
    std::map<std::string, MeshSection> meshes;   // keyed by normalized mesh name
    std::vector<std::string> order;
    std::vector<std::pair<std::string, QuantitySection>> pending;
    for (const auto& info : config.GetSectionInfo()) {
        if (info.section.rfind(kPrefix, 0) != 0) continue;
        const std::string normalizedRest = info.section.substr(kPrefix.size());
        const std::string original = info.originalSection.size() >= kPrefix.size()
            ? info.originalSection.substr(kPrefix.size()) : normalizedRest;
        const auto dot = original.find('.');
        if (dot == std::string::npos) {
            if (!ValidName(original)) Fail(info.section, "mesh name must use letters, digits, '_' or '-'");
            if (meshes.count(normalizedRest)) Fail(info.section, "duplicate mesh section");
            meshes[normalizedRest] = {original, info.section, {}};
            order.push_back(normalizedRest);
        } else {
            const std::string meshName = original.substr(0, dot);
            const std::string quantityName = original.substr(dot + 1);
            if (!ValidName(meshName) || !ValidName(quantityName)) {
                Fail(info.section, "expected [scoring.mesh.<mesh>.<quantity>] with names of letters, digits, '_' or '-'");
            }
            pending.push_back({StringUtils::ToLower(meshName), {quantityName, info.section}});
        }
    }
    for (const auto& item : pending) {
        auto it = meshes.find(item.first);
        if (it == meshes.end()) {
            Fail(item.second.section, "no matching [scoring.mesh." + item.first + "] section");
        }
        it->second.quantities.push_back(item.second);
    }
    std::vector<MeshSection> result;
    for (const auto& name : order) result.push_back(meshes[name]);
    return result;
}

}  // namespace

namespace ScoringMeshConfig {

const std::vector<std::string>& MeshKeys()
{
    static const std::vector<std::string> keys = {"shape", "size", "bins", "center"};
    return keys;
}

const std::vector<std::string>& QuantityKeys()
{
    static const std::vector<std::string> keys = {"type", "unit", "particles", "energy_min", "energy_max"};
    return keys;
}

std::vector<std::string> BuildCommands(const ConfigManager& config)
{
    std::vector<std::string> commands;
    for (const MeshSection& mesh : FindSections(config)) {
        const std::string& s = mesh.section;
        for (const auto& key : MeshKeys()) config.MarkKeyConsumed(s, key);
        if (!config.HasKey(s, "shape") || !config.HasKey(s, "size") || !config.HasKey(s, "bins")) {
            Fail(s, "shape, size and bins are required");
        }
        const std::string shape = StringUtils::ToLower(StringUtils::Trim(config.GetString(s, "shape")));
        const std::vector<int> bins = Bins(config, s);
        if (shape == "box") {
            const auto size = Lengths(config, s, "size", 3);
            for (const double v : size) if (v <= 0.0) Fail(s, "size half-lengths must be > 0");
            commands.push_back("/score/create/boxMesh " + mesh.name);
            commands.push_back("/score/mesh/boxSize " + Number(size[0] / mm) + " " + Number(size[1] / mm) + " " +
                               Number(size[2] / mm) + " mm");
        } else if (shape == "cylinder") {
            const auto size = Lengths(config, s, "size", 2);
            for (const double v : size) if (v <= 0.0) Fail(s, "cylinder radius and half-length must be > 0");
            commands.push_back("/score/create/cylinderMesh " + mesh.name);
            commands.push_back("/score/mesh/cylinderSize " + Number(size[0] / mm) + " " + Number(size[1] / mm) + " mm");
        } else {
            Fail(s, "shape = '" + shape + "': expected box or cylinder");
        }
        commands.push_back("/score/mesh/nBin " + std::to_string(bins[0]) + " " + std::to_string(bins[1]) + " " +
                           std::to_string(bins[2]));
        if (config.HasKey(s, "center")) {
            const auto center = Lengths(config, s, "center", 3);
            commands.push_back("/score/mesh/translate/xyz " + Number(center[0] / mm) + " " + Number(center[1] / mm) +
                               " " + Number(center[2] / mm) + " mm");
        }
        if (mesh.quantities.empty()) Fail(s, "define at least one [" + s + ".<quantity>] section");

        for (const QuantitySection& quantity : mesh.quantities) {
            const std::string& q = quantity.section;
            for (const auto& key : QuantityKeys()) config.MarkKeyConsumed(q, key);
            if (!config.HasKey(q, "type")) Fail(q, "type is required (a Geant4 primitive scorer, e.g. energyDeposit)");
            const std::string type = StringUtils::Trim(config.GetString(q, "type"));
            if (!ValidName(type)) Fail(q, "type = '" + type + "' is not a scorer command name");
            std::string command = "/score/quantity/" + type + " " + quantity.name;
            if (config.HasKey(q, "unit")) command += " " + StringUtils::Trim(config.GetString(q, "unit"));
            commands.push_back(command);

            const bool hasParticles = config.HasKey(q, "particles");
            const bool hasEnergy = config.HasKey(q, "energy_min") || config.HasKey(q, "energy_max");
            std::string particles;
            if (hasParticles) {
                for (const std::string& part : StringUtils::Split(config.GetString(q, "particles"), ',')) {
                    const std::string name = StringUtils::Trim(part);
                    if (!name.empty()) particles += " " + name;
                }
                if (particles.empty()) Fail(q, "particles is empty");
            }
            std::string energies;
            if (hasEnergy) {
                double low = 0.0;
                double high = 1.0e30;
                try {
                    if (config.HasKey(q, "energy_min")) low = UnitParser::ParseEnergy(config.GetString(q, "energy_min"));
                    if (config.HasKey(q, "energy_max")) high = UnitParser::ParseEnergy(config.GetString(q, "energy_max"));
                } catch (const std::exception& error) {
                    Fail(q, std::string("energy_min/energy_max: ") + error.what());
                }
                if (!(low >= 0.0) || !(high > low)) Fail(q, "need 0 <= energy_min < energy_max");
                energies = " " + Number(low / MeV) + " " + Number(high / MeV) + " MeV";
            }
            const std::string filterName = quantity.name + "_filter";
            if (hasParticles && hasEnergy) {
                commands.push_back("/score/filter/particleWithKineticEnergy " + filterName + energies + particles);
            } else if (hasParticles) {
                commands.push_back("/score/filter/particle " + filterName + particles);
            } else if (hasEnergy) {
                commands.push_back("/score/filter/kineticEnergy " + filterName + energies);
            }
        }
        commands.push_back("/score/close");
    }
    return commands;
}

}  // namespace ScoringMeshConfig
