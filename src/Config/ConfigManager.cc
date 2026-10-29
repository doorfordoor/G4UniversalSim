#include "Config/ConfigManager.hh"

#include "Config/ConfigSchemaTable.hh"
#include "Utils/StringUtils.hh"

#include <stdexcept>
#include <algorithm>
#include <limits>

namespace {

std::string LowerTrim(const std::string& value)
{
    return StringUtils::ToLower(StringUtils::Trim(value));
}

bool StartsWith(const std::string& value, const std::string& prefix)
{
    return value.size() >= prefix.size() && value.compare(0, prefix.size(), prefix) == 0;
}

// Keys of the sections not yet migrated to schema/config_schema.json (roadmap E2); the
// migrated static sections come from the generated table below.
std::map<std::string, std::vector<std::string>> BuildKnownKeys()
{
    std::map<std::string, std::vector<std::string>> keys = {
        {"field", {"magnetic", "electric", "magnetic_map", "electric_map", "min_step", "delta_chord", "delta_one_step",
                   "delta_intersection"}},
        {"biasing", {"enabled"}},
        {"biasing.xs", {"particles", "processes", "volumes", "factor", "only_primary", "apply_to_secondaries", "min_weight", "max_interactions"}},
    };
    for (const char* section : ConfigSchema::kMainIniSections) {
        if (keys.count(section)) throw std::logic_error(std::string("section [") + section + "] is in the schema and the hand list");
        keys[section];
    }
    for (const auto& spec : ConfigSchema::kMainIniKeys) {
        auto& names = keys[spec.section];
        names.push_back(spec.key);
        for (const std::string& alias : StringUtils::Split(spec.aliases, ',', true)) {
            if (!StringUtils::Trim(alias).empty()) names.push_back(StringUtils::Trim(alias));
        }
    }
    return keys;
}

const std::map<std::string, std::vector<std::string>>& KnownKeys()
{
    static const std::map<std::string, std::vector<std::string>> keys = BuildKnownKeys();
    return keys;
}

bool IsKnownDynamicSection(const std::string& section)
{
    if (section == "physics.cuts") return true;
    if (section == "scoring.displacement") return true;  // keys are particle names
    if (StartsWith(section, "physics.region.")) {
        const std::string suffix = section.substr(std::string("physics.region.").size());
        return !suffix.empty() && suffix.find('.') == std::string::npos;
    }
    if (StartsWith(section, "scoring.mesh.")) {
        // [scoring.mesh.<mesh>] and [scoring.mesh.<mesh>.<quantity>]
        const std::string suffix = section.substr(std::string("scoring.mesh.").size());
        const auto separator = suffix.find('.');
        if (suffix.empty() || separator == 0) return false;
        return separator == std::string::npos ||
               (separator + 1 < suffix.size() && suffix.find('.', separator + 1) == std::string::npos);
    }
    if (StartsWith(section, "source.")) {
        const std::string suffix = section.substr(std::string("source.").size());
        return !suffix.empty() && suffix.find('.') == std::string::npos;
    }
    if (StartsWith(section, "field.")) {
        const std::string suffix = section.substr(std::string("field.").size());
        return !suffix.empty() && suffix.find('.') == std::string::npos;
    }
    if (StartsWith(section, "biasing.xs.")) {
        const std::string suffix = section.substr(std::string("biasing.xs.").size());
        const auto separator = suffix.find('.');
        return separator != std::string::npos && separator > 0 &&
               separator + 1 < suffix.size() && suffix.find('.', separator + 1) == std::string::npos;
    }
    return false;
}

std::vector<std::string> DynamicKeys(const std::string& section)
{
    if (StartsWith(section, "physics.cuts")) return ConfigSchema::Keys("main_ini", "physics.cuts", true);
    if (StartsWith(section, "physics.region.")) {
        return ConfigSchema::Keys("main_ini", "physics.region.<name>");
    }
    if (StartsWith(section, "scoring.mesh.")) {
        const std::string suffix = section.substr(std::string("scoring.mesh.").size());
        if (suffix.find('.') == std::string::npos) return ConfigSchema::Keys("main_ini", "scoring.mesh.<name>");
        return ConfigSchema::Keys("main_ini", "scoring.mesh.<name>.<quantity>");
    }
    if (StartsWith(section, "field.")) {
        return {"magnetic", "electric", "magnetic_map", "electric_map", "volumes", "min_step", "delta_chord",
                "delta_one_step", "delta_intersection"};
    }
    if (StartsWith(section, "source.")) {
        return ConfigSchema::Keys("main_ini", "source.<name>", true);
    }
    if (StartsWith(section, "biasing.xs.")) return {"particle", "process", "name", "enabled", "factor", "only_primary", "apply_to_secondaries", "min_weight", "max_interactions", "volumes"};
    return {};
}

}  // namespace

void ConfigManager::LoadMainConfig(const std::string& filename)
{
    mainConfig_.Load(filename);
}

void ConfigManager::LoadMainConfigBytes(const std::string& filename, const std::string& bytes)
{
    mainConfig_.LoadBytes(filename, bytes);
}

void ConfigManager::LoadConfigFile(const std::string& name, const std::string& filename)
{
    const std::string normalizedName = NormalizeConfigName(name);
    if (normalizedName.empty()) {
        throw std::runtime_error("ConfigManager cannot load config with empty name");
    }

    IniReader reader;
    reader.Load(filename);
    namedConfigs_[normalizedName] = reader;
}

bool ConfigManager::HasConfigFile(const std::string& name) const
{
    return namedConfigs_.find(NormalizeConfigName(name)) != namedConfigs_.end();
}

bool ConfigManager::HasSection(const std::string& section) const
{
    EnsureMainConfigLoaded();
    return mainConfig_.HasSection(section);
}

bool ConfigManager::HasKey(const std::string& section, const std::string& key) const
{
    EnsureMainConfigLoaded();
    return mainConfig_.HasKey(section, key);
}

std::string ConfigManager::GetString(
    const std::string& section,
    const std::string& key
) const
{
    return GetValue(section, key).AsString();
}

std::string ConfigManager::GetString(
    const std::string& section,
    const std::string& key,
    const std::string& defaultValue
) const
{
    return GetValue(section, key, defaultValue).AsString();
}

int ConfigManager::GetInt(const std::string& section, const std::string& key) const
{
    return GetValue(section, key).AsInt();
}

int ConfigManager::GetInt(
    const std::string& section,
    const std::string& key,
    int defaultValue
) const
{
    if (!HasKey(section, key)) {
        return defaultValue;
    }
    return GetInt(section, key);
}

double ConfigManager::GetDouble(const std::string& section, const std::string& key) const
{
    return GetValue(section, key).AsDouble();
}

double ConfigManager::GetDouble(
    const std::string& section,
    const std::string& key,
    double defaultValue
) const
{
    if (!HasKey(section, key)) {
        return defaultValue;
    }
    return GetDouble(section, key);
}

bool ConfigManager::GetBool(const std::string& section, const std::string& key) const
{
    return GetValue(section, key).AsBool();
}

bool ConfigManager::GetBool(
    const std::string& section,
    const std::string& key,
    bool defaultValue
) const
{
    if (!HasKey(section, key)) {
        return defaultValue;
    }
    return GetBool(section, key);
}

std::vector<std::string> ConfigManager::GetVector(
    const std::string& section,
    const std::string& key,
    char delimiter
) const
{
    return GetValue(section, key).AsStringVector(delimiter);
}

std::vector<std::string> ConfigManager::GetVector(
    const std::string& section,
    const std::string& key,
    const std::vector<std::string>& defaultValue,
    char delimiter
) const
{
    if (!HasKey(section, key)) {
        return defaultValue;
    }
    return GetVector(section, key, delimiter);
}

ConfigValue ConfigManager::GetValue(
    const std::string& section,
    const std::string& key
) const
{
    EnsureMainConfigLoaded();
    if (!mainConfig_.HasKey(section, key)) {
        throw std::runtime_error(
            "Missing config value for section/key '" + section + "/" + key + "'"
        );
    }
    return ConfigValue(mainConfig_.GetString(section, key));
}

ConfigValue ConfigManager::GetValue(
    const std::string& section,
    const std::string& key,
    const std::string& defaultValue
) const
{
    EnsureMainConfigLoaded();
    if (!mainConfig_.HasKey(section, key)) {
        return ConfigValue(defaultValue);
    }
    return ConfigValue(mainConfig_.GetString(section, key));
}

std::string ConfigManager::GetStringFrom(
    const std::string& configName,
    const std::string& section,
    const std::string& key,
    const std::string& defaultValue
) const
{
    const IniReader& reader = RequireConfigFile(configName);
    if (!reader.HasKey(section, key)) {
        return defaultValue;
    }
    return reader.GetString(section, key);
}

ConfigValue ConfigManager::GetValueFrom(
    const std::string& configName,
    const std::string& section,
    const std::string& key
) const
{
    const IniReader& reader = RequireConfigFile(configName);
    if (!reader.HasKey(section, key)) {
        throw std::runtime_error(
            "Missing config value for named config '" + configName
            + "' section/key '" + section + "/" + key + "'"
        );
    }
    return ConfigValue(reader.GetString(section, key));
}

std::vector<std::string> ConfigManager::GetSections() const
{
    EnsureMainConfigLoaded();
    return mainConfig_.GetSections();
}

std::vector<std::string> ConfigManager::GetKeys(const std::string& section) const
{
    EnsureMainConfigLoaded();
    return mainConfig_.GetKeys(section);
}

std::vector<IniFieldInfo> ConfigManager::GetFields() const
{
    EnsureMainConfigLoaded();
    return mainConfig_.GetFields();
}

std::vector<IniSectionInfo> ConfigManager::GetSectionInfo() const
{
    EnsureMainConfigLoaded();
    return mainConfig_.GetSectionInfo();
}

std::vector<ConfigWarning> ConfigManager::GetUnconsumedWarnings() const
{
    EnsureMainConfigLoaded();
    std::vector<ConfigWarning> warnings;
    const auto& known = KnownKeys();
    std::vector<std::string> globalCandidates;
    for (const auto& item : known) {
        globalCandidates.insert(globalCandidates.end(), item.second.begin(), item.second.end());
    }

    for (const auto& sectionInfo : mainConfig_.GetSectionInfo()) {
        if (!sectionInfo.explicitSection && sectionInfo.section == "global") continue;
        const auto knownIt = known.find(sectionInfo.section);
        const bool dynamic = IsKnownDynamicSection(sectionInfo.section);
        if (knownIt == known.end() && !dynamic) {
            warnings.push_back({mainConfig_.GetFilename(), sectionInfo.section, "", "",
                                sectionInfo.lineNumber, Suggestion(sectionInfo.section, [&]() {
                                    std::vector<std::string> sections;
                                    for (const auto& item : known) sections.push_back(item.first);
                                    return sections;
                                }())});
        }
    }

    for (const auto& field : mainConfig_.GetFields()) {
        const auto knownIt = known.find(field.section);
        const auto candidates = field.section == "global"
            ? globalCandidates
            : (knownIt != known.end() ? knownIt->second : DynamicKeys(field.section));
        if (!field.consumed && (field.section == "global" || !candidates.empty() || knownIt != known.end())) {
            warnings.push_back({mainConfig_.GetFilename(), field.section, field.key, field.value,
                                field.lineNumber, Suggestion(field.key, candidates)});
        }
    }

    std::sort(warnings.begin(), warnings.end(), [](const ConfigWarning& left, const ConfigWarning& right) {
        if (left.filename != right.filename) return left.filename < right.filename;
        if (left.lineNumber != right.lineNumber) return left.lineNumber < right.lineNumber;
        if (left.section != right.section) return left.section < right.section;
        return left.key < right.key;
    });
    warnings.erase(std::unique(warnings.begin(), warnings.end(), [](const ConfigWarning& left, const ConfigWarning& right) {
        return left.filename == right.filename && left.lineNumber == right.lineNumber &&
               left.section == right.section && left.key == right.key;
    }), warnings.end());
    return warnings;
}

std::vector<ConfigWarning> ConfigManager::GetDuplicateWarnings() const
{
    EnsureMainConfigLoaded();
    std::vector<ConfigWarning> warnings;
    const std::string& filename = mainConfig_.GetFilename();
    for (const auto& duplicate : mainConfig_.GetDuplicates()) {
        ConfigWarning warning;
        warning.filename = filename;
        warning.section = duplicate.section;
        warning.key = duplicate.key;
        warning.lineNumber = duplicate.lineNumber;
        warning.suggestion =
            "earlier declaration at line " + std::to_string(duplicate.firstLine) +
            " is overridden by this one; remove one of the declarations";
        if (duplicate.key.empty()) {
            warning.value = "";
        } else {
            // The repeated key's value in the map is the later one; report it so the
            // warning states which value actually wins.
            warning.value = mainConfig_.GetString(duplicate.section, duplicate.key);
        }
        warnings.push_back(std::move(warning));
    }
    std::sort(warnings.begin(), warnings.end(), [](const ConfigWarning& left, const ConfigWarning& right) {
        if (left.filename != right.filename) return left.filename < right.filename;
        if (left.lineNumber != right.lineNumber) return left.lineNumber < right.lineNumber;
        if (left.section != right.section) return left.section < right.section;
        return left.key < right.key;
    });
    return warnings;
}

void ConfigManager::MarkKeyConsumed(const std::string& section, const std::string& key) const
{
    EnsureMainConfigLoaded();
    if (mainConfig_.HasKey(section, key)) {
        (void)mainConfig_.GetString(section, key);
    }
}

std::string ConfigManager::GetMainConfigPath() const
{
    return mainConfig_.GetFilename();
}

void ConfigManager::Clear()
{
    mainConfig_.Clear();
    namedConfigs_.clear();
}

std::string ConfigManager::NormalizeConfigName(const std::string& name)
{
    return StringUtils::ToLower(StringUtils::Trim(name));
}

std::string ConfigManager::Suggestion(const std::string& value,
                                      const std::vector<std::string>& candidates)
{
    const std::string target = LowerTrim(value);
    std::size_t best = std::numeric_limits<std::size_t>::max();
    std::string match;
    for (const auto& candidate : candidates) {
        const std::string normalized = LowerTrim(candidate);
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
    return best <= 5 && !match.empty() ? match : "";
}

const IniReader& ConfigManager::RequireConfigFile(const std::string& name) const
{
    const auto it = namedConfigs_.find(NormalizeConfigName(name));
    if (it == namedConfigs_.end()) {
        throw std::runtime_error("Named config file has not been loaded: '" + name + "'");
    }
    return it->second;
}

void ConfigManager::EnsureMainConfigLoaded() const
{
    if (mainConfig_.GetFilename().empty()) {
        throw std::runtime_error("Main config file has not been loaded");
    }
}
