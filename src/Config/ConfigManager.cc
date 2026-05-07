#include "Config/ConfigManager.hh"

#include "Utils/StringUtils.hh"

#include <stdexcept>

void ConfigManager::LoadMainConfig(const std::string& filename)
{
    mainConfig_.Load(filename);
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
