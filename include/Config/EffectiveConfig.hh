#pragma once

#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <variant>
#include <utility>
#include <vector>

namespace effective_config {

// JSON values retain integers, booleans and null; no string coercion is performed.
struct Value {
    using Array = std::vector<Value>;
    using Object = std::map<std::string, Value>;
    using Storage = std::variant<std::nullptr_t, bool, std::int64_t, double,
                                 std::string, Array, Object>;
    Storage data = nullptr;
    Value() = default;
    Value(std::nullptr_t) : data(nullptr) {}
    Value(bool value) : data(value) {}
    Value(int value) : data(static_cast<std::int64_t>(value)) {}
    Value(std::int64_t value) : data(value) {}
    Value(double value) : data(value) {}
    Value(const char* value) : data(std::string(value)) {}
    Value(std::string value) : data(std::move(value)) {}
    Value(Array value) : data(std::move(value)) {}
    Value(Object value) : data(std::move(value)) {}
    std::string ToJson() const;
};

enum class ApplicationStatus { NotApplied, Applied, Unknown, Failed };
enum class EvidenceLevel { None, ManagerAccepted, KernelConstructed, ThreadApplied, RunValidated };

struct Origin {
    std::string kind; // default, preset, main_ini, cli, macro, runtime_unattributed
    std::string file;
    std::uint64_t line = 0;
    std::string section;
    std::string key;
    std::string raw;
    std::string alias;
    std::string input_sha256;
    std::string disposition = "accepted"; // accepted, shadowed, derived
};

struct Field {
    std::string path;
    Value requested;
    bool requested_known = true; // false omits requested; explicit null remains a valid value
    Value resolved;
    bool resolved_known = true;
    std::string unit;
    std::vector<Origin> origins; // complete successful override chain, oldest first
    ApplicationStatus application_status = ApplicationStatus::NotApplied;
    EvidenceLevel evidence_level = EvidenceLevel::None;
    std::string reason;
    std::string evidence_source;
    std::optional<std::uint64_t> applied_revision;
    std::uint64_t revision = 0; // assigned by Registry::Commit
    std::uint64_t configuration_generation = 0; // consumer transaction identity, scoped by module
};

std::string EscapePointerToken(const std::string& token);
std::string FieldPath(const std::string& module, const std::string& field);
std::string ObjectFieldPath(const std::string& module, const std::string& object,
                          const std::string& field);

class Snapshot {
public:
    std::uint64_t Revision() const { return revision_; }
    const std::map<std::string, Field>& Fields() const { return fields_; }
    const Value::Object& Metadata() const { return metadata_; }
    std::string ToJson() const;
    // Annotation changes a snapshot view, never the configuration registry/revision.
    Snapshot WithMetadata(Value::Object metadata) const;
    Snapshot WithApplicationEvidence(const std::vector<Field>& evidence) const;
private:
    friend class Registry;
    std::uint64_t revision_ = 0;
    std::string stage_;
    std::optional<std::int64_t> run_id_;
    std::map<std::string, Field> fields_;
    Value::Object metadata_;
};

// Caller serializes access (normally the configuration/master thread). A commit
// observes already successful Manager operations; it must never execute setters.
class Registry {
public:
    // Atomic upserts + removals. Every incoming field carries its complete origin
    // chain. Empty/identical transactions return the current revision. Unchanged
    // fields retain their revision; callers cannot assign Field::revision.
    // Throws before publication on invalid values/paths/evidence/duplicates.
    std::uint64_t Commit(std::vector<Field> fields,
                         const std::vector<std::string>& erasedPaths = {});
    // Complete module replacement, including removal of fields absent in fields.
    // Empty replacement clears the module. Module is an unescaped identity token.
    std::uint64_t ReplaceModule(const std::string& module, std::vector<Field> fields);
    std::uint64_t Revision() const { return revision_; }
    Snapshot Capture(const std::string& stage,
                     std::optional<std::int64_t> run_id = std::nullopt) const;
private:
    std::uint64_t revision_ = 0;
    std::map<std::string, Field> fields_;
};

} // namespace effective_config
