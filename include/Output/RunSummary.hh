#pragma once

#include <map>
#include <cstdint>
#include <string>
#include <vector>

class RunSummary {
public:
    struct RunRecord {
        int runId = 0;
        std::int64_t plannedEvents = 0;
        std::int64_t completedEvents = 0;
    };

    RunSummary() = default;

    void Set(const std::string& key, const std::string& value);
    void Set(const std::string& key, int value);
    void Set(const std::string& key, std::int64_t value);
    void Set(const std::string& key, double value);
    void SetBool(const std::string& key, bool value);

    bool Has(const std::string& key) const;

    std::string Get(const std::string& key, const std::string& defaultValue = "") const;

    void AddMessage(const std::string& message);
    void AddWarning(const std::string& warning);
    void AddRun(int runId, std::int64_t plannedEvents, std::int64_t completedEvents);
    void SetGeneratedFiles(const std::vector<std::string>& files);
    const std::vector<RunRecord>& GetRuns() const;

    void WriteText(const std::string& filename) const;
    void WriteCSV(const std::string& filename) const;

    void Clear();

private:
    std::map<std::string, std::string> values_;
    std::vector<std::string> messages_;
    std::vector<std::string> warnings_;
    std::vector<RunRecord> runs_;
    std::vector<std::string> generatedFiles_;
};
