#pragma once

#include "Config/ConfigValue.hh"
#include "Config/IniReader.hh"

#include <map>
#include <string>
#include <vector>

struct ConfigWarning {
    std::string filename;
    std::string section;
    std::string key;
    std::string value;
    std::size_t lineNumber = 0;
    std::string suggestion;
};

class ConfigManager {
public:
    ConfigManager() = default;

    void LoadMainConfig(const std::string& filename);
    void LoadMainConfigBytes(const std::string& filename, const std::string& bytes);

    // Geometry templates reuse this key/value facade, but their format version
    // is [global]/version and is validated by GeometryConfigDiagnostic.
    void LoadGeometryConfigBytes(const std::string& filename, const std::string& bytes);

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

    std::vector<IniFieldInfo> GetFields() const;

    std::vector<IniSectionInfo> GetSectionInfo() const;

    std::vector<ConfigWarning> GetUnconsumedWarnings() const;

    // Repeated [section] headers and repeated keys in the main INI. The parser keeps the
    // historical last-value-wins behavior (geometry version=2 has its own strict rejection),
    // so these are reported as warnings: the earlier declaration is silently dropped for
    // every consumer, which must not stay invisible.
    std::vector<ConfigWarning> GetDuplicateWarnings() const;

    // Mark a known compatibility alias consumed after a higher-priority alias wins.
    void MarkKeyConsumed(const std::string& section, const std::string& key) const;

    std::string GetMainConfigPath() const;

    // Read-only provenance: never marks keys consumed or reparses the input.
    const IniReader& GetMainReader() const { return mainConfig_; }

    void Clear();

    // Closest candidate (edit distance <= 5) for a "did you mean" message; shared by
    // the unconsumed-key warnings and by modules that validate a name against an
    // external table at configuration time (for example [scoring.displacement]).
    static std::string Suggestion(const std::string& value,
                                  const std::vector<std::string>& candidates);

private:
    static std::string NormalizeConfigName(const std::string& name);

    const IniReader& RequireConfigFile(const std::string& name) const;
    void EnsureMainConfigLoaded() const;

    IniReader mainConfig_;
    std::map<std::string, IniReader> namedConfigs_;
};
