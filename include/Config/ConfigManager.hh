#pragma once

#include "Config/ConfigValue.hh"
#include "Config/IniReader.hh"

#include <map>
#include <string>
#include <vector>

class ConfigManager {
public:
    ConfigManager() = default;

    void LoadMainConfig(const std::string& filename);

    void LoadConfigFile(const std::string& name, const std::string& filename);

    bool HasConfigFile(const std::string& name) const;

    bool HasSection(const std::string& section) const;

    bool HasKey(const std::string& section, const std::string& key) const;

    std::string GetString(const std::string& section, const std::string& key) const;

    std::string GetString(
        const std::string& section,
        const std::string& key,
        const std::string& defaultValue
    ) const;

    int GetInt(const std::string& section, const std::string& key) const;

    int GetInt(const std::string& section, const std::string& key, int defaultValue) const;

    double GetDouble(const std::string& section, const std::string& key) const;

    double GetDouble(
        const std::string& section,
        const std::string& key,
        double defaultValue
    ) const;

    bool GetBool(const std::string& section, const std::string& key) const;

    bool GetBool(const std::string& section, const std::string& key, bool defaultValue) const;

    std::vector<std::string> GetVector(
        const std::string& section,
        const std::string& key,
        char delimiter = ','
    ) const;

    std::vector<std::string> GetVector(
        const std::string& section,
        const std::string& key,
        const std::vector<std::string>& defaultValue,
        char delimiter = ','
    ) const;

    ConfigValue GetValue(const std::string& section, const std::string& key) const;

    ConfigValue GetValue(
        const std::string& section,
        const std::string& key,
        const std::string& defaultValue
    ) const;

    std::string GetStringFrom(
        const std::string& configName,
        const std::string& section,
        const std::string& key,
        const std::string& defaultValue = ""
    ) const;

    ConfigValue GetValueFrom(
        const std::string& configName,
        const std::string& section,
        const std::string& key
    ) const;

    std::vector<std::string> GetSections() const;

    std::vector<std::string> GetKeys(const std::string& section) const;

    std::string GetMainConfigPath() const;

    void Clear();

private:
    static std::string NormalizeConfigName(const std::string& name);

    const IniReader& RequireConfigFile(const std::string& name) const;
    void EnsureMainConfigLoaded() const;

    IniReader mainConfig_;
    std::map<std::string, IniReader> namedConfigs_;
};
