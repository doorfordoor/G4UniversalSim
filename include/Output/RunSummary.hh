#pragma once

#include "Config/EffectiveConfig.hh"

#include <map>
#include <optional>
#include <cstdint>
#include <string>
#include <stdexcept>
#include <vector>

class RunSummary {
public:
    // Preserve the exact serializer I/O boundary without message parsing.
    struct MetadataWriteError : std::runtime_error {
        std::string stage;
        MetadataWriteError(const std::string& where, const std::string& message)
            : std::runtime_error(message), stage(where) {}
    };
    struct RunRecord {
        int runId = 0;
        std::int64_t plannedEvents = 0;
        std::int64_t completedEvents = 0;
    };

    enum class ArtifactScope { Process, Run, Thread };
    struct ArtifactEvidence {
        std::string path, execution_id;
        ArtifactScope scope = ArtifactScope::Process;
        std::optional<int> run_id, thread_id;
        std::optional<std::string> sha256;
        std::optional<std::uint64_t> size_bytes;
        std::string integrity_status = "unavailable", reason;
    };

    RunSummary() = default;

    void Set(const std::string& key, const std::string& value);
    void Set(const std::string& key, int value);
    void Set(const std::string& key, std::int64_t value);
    void Set(const std::string& key, double value);
    void SetPath(const std::string& key, const std::string& nativePath);
    void SetBool(const std::string& key, bool value);

    bool Has(const std::string& key) const;

    std::string Get(const std::string& key, const std::string& defaultValue = "") const;

    void AddMessage(const std::string& message);
    void AddWarning(const std::string& warning);
    void AddRun(int runId, std::int64_t plannedEvents, std::int64_t completedEvents);
    void SetGeneratedFiles(const std::vector<std::string>& files);
    void SetProvenance(effective_config::Value provenance);
    void SetArtifactEvidence(const std::vector<ArtifactEvidence>& evidence);
    const std::vector<RunRecord>& GetRuns() const;

    void WriteText(const std::string& filename) const;
    void WriteCSV(const std::string& filename) const;
    // Machine-readable run metadata (run_metadata.json, schema run_metadata_json_v1).
    void WriteJson(const std::string& filename) const;

    void Clear();

private:
    std::map<std::string, std::string> values_;
    std::vector<std::string> messages_;
    std::vector<std::string> warnings_;
    std::vector<RunRecord> runs_;
    std::vector<std::string> generatedFiles_;
    std::optional<effective_config::Value> provenance_;
    std::vector<ArtifactEvidence> artifactEvidence_;
};
