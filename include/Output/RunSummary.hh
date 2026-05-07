#pragma once

#include <map>
#include <string>
#include <vector>

class RunSummary {
public:
    RunSummary() = default;

    void Set(const std::string& key, const std::string& value);
    void Set(const std::string& key, int value);
    void Set(const std::string& key, double value);
    void SetBool(const std::string& key, bool value);

    bool Has(const std::string& key) const;

    std::string Get(const std::string& key, const std::string& defaultValue = "") const;

    void AddMessage(const std::string& message);
    void AddWarning(const std::string& warning);

    void WriteText(const std::string& filename) const;
    void WriteCSV(const std::string& filename) const;

    void Clear();

private:
    std::map<std::string, std::string> values_;
    std::vector<std::string> messages_;
    std::vector<std::string> warnings_;
};
