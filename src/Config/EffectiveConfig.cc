#include "Config/EffectiveConfig.hh"

#include <cmath>
#include <iomanip>
#include <limits>
#include <locale>
#include <set>
#include <sstream>
#include <stdexcept>
#include <type_traits>

namespace effective_config {
namespace {
std::string Quote(const std::string& text)
{
    std::ostringstream out;
    out << '"';
    for (unsigned char ch : text) {
        switch (ch) {
        case '"': out << "\\\""; break;
        case '\\': out << "\\\\"; break;
        case '\b': out << "\\b"; break;
        case '\f': out << "\\f"; break;
        case '\n': out << "\\n"; break;
        case '\r': out << "\\r"; break;
        case '\t': out << "\\t"; break;
        default:
            if (ch < 0x20) out << "\\u00" << std::hex << std::setw(2)
                               << std::setfill('0') << static_cast<int>(ch) << std::dec;
            else out << static_cast<char>(ch);
        }
    }
    out << '"';
    return out.str();
}
const char* Name(ApplicationStatus status)
{
    switch (status) {
    case ApplicationStatus::NotApplied: return "not_applied";
    case ApplicationStatus::Applied: return "applied";
    case ApplicationStatus::Unknown: return "unknown";
    case ApplicationStatus::Failed: return "failed";
    }
    throw std::invalid_argument("Invalid application status");
}
const char* Name(EvidenceLevel level)
{
    switch (level) {
    case EvidenceLevel::None: return "none";
    case EvidenceLevel::ManagerAccepted: return "manager_accepted";
    case EvidenceLevel::KernelConstructed: return "kernel_constructed";
    case EvidenceLevel::ThreadApplied: return "thread_applied";
    case EvidenceLevel::RunValidated: return "run_validated";
    }
    throw std::invalid_argument("Invalid evidence level");
}
Value Number(std::uint64_t number)
{
    if (number > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))
        throw std::overflow_error("EffectiveConfig counter exceeds signed JSON integer range");
    return Value(static_cast<std::int64_t>(number));
}
void ValidatePath(const std::string& path)
{
    if (path.empty() || path.front() != '/' || path.back() == '/' || path.find("//") != std::string::npos)
        throw std::invalid_argument("EffectiveConfig path must have nonempty JSON Pointer tokens");
    for (std::size_t i = 0; i < path.size(); ++i) {
        if (static_cast<unsigned char>(path[i]) < 0x20)
            throw std::invalid_argument("EffectiveConfig path contains control character");
        if (path[i] == '~') {
            if (++i == path.size() || (path[i] != '0' && path[i] != '1'))
                throw std::invalid_argument("Invalid JSON Pointer escape");
        }
    }
    const auto second = path.find('/', 1);
    if (second == std::string::npos)
        throw std::invalid_argument("EffectiveConfig path requires module and field");
    if (path.substr(second + 1, 8) == "objects/") {
        const auto objectEnd = path.find('/', second + 9);
        if (objectEnd == std::string::npos || path.find('/', objectEnd + 1) != std::string::npos)
            throw std::invalid_argument("Object path requires one object and one field token");
    } else if (path.find('/', second + 1) != std::string::npos) {
        throw std::invalid_argument("Field path requires module/field or module/objects/name/field");
    }
}
Value FieldValue(const Field& field)
{
    Value::Array origins;
    for (const auto& origin : field.origins) {
        origins.emplace_back(Value::Object{{"kind", origin.kind}, {"file", origin.file},
            {"line", Number(origin.line)}, {"section", origin.section}, {"key", origin.key},
            {"raw", origin.raw}, {"alias", origin.alias}, {"input_sha256", origin.input_sha256}, {"disposition", origin.disposition}});
    }
    Value::Object result{{"path", field.path},
        {"unit", field.unit}, {"origins", origins},
        {"application_status", Name(field.application_status)},
        {"evidence_level", Name(field.evidence_level)}, {"reason", field.reason},
        {"evidence_source", field.evidence_source}, {"revision", Number(field.revision)},
        {"configuration_generation", Number(field.configuration_generation)},
        {"applied_revision", field.applied_revision ? Number(*field.applied_revision) : Value()}};
    if (field.requested_known) result["requested"] = field.requested;
    if (field.resolved_known) result["resolved"] = field.resolved;
    return result;
}
} // namespace

std::string Value::ToJson() const
{
    return std::visit([](const auto& value) -> std::string {
        using T = std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<T, std::nullptr_t>) return "null";
        else if constexpr (std::is_same_v<T, bool>) return value ? "true" : "false";
        else if constexpr (std::is_same_v<T, std::int64_t>) return std::to_string(value);
        else if constexpr (std::is_same_v<T, double>) {
            if (!std::isfinite(value)) throw std::invalid_argument("EffectiveConfig requires finite numbers");
            std::ostringstream out;
            out.imbue(std::locale::classic());
            out << std::setprecision(std::numeric_limits<double>::max_digits10) << value;
            std::string result = out.str();
            if (result.find_first_of(".eE") == std::string::npos) result += ".0";
            return result;
        } else if constexpr (std::is_same_v<T, std::string>) return Quote(value);
        else {
            constexpr bool object = std::is_same_v<T, Object>;
            std::string result = object ? "{" : "[";
            bool first = true;
            for (const auto& item : value) {
                if (!first) result += ',';
                first = false;
                if constexpr (object) result += Quote(item.first) + ':' + item.second.ToJson();
                else result += item.ToJson();
            }
            return result + (object ? "}" : "]");
        }
    }, data);
}

std::string EscapePointerToken(const std::string& token)
{
    if (token.empty()) throw std::invalid_argument("Empty EffectiveConfig identity token");
    std::string result;
    for (char ch : token) {
        if (ch == '~') result += "~0";
        else if (ch == '/') result += "~1";
        else result += ch;
    }
    return result;
}
std::string FieldPath(const std::string& module, const std::string& field)
{
    return '/' + EscapePointerToken(module) + '/' + EscapePointerToken(field);
}
std::string ObjectFieldPath(const std::string& module, const std::string& object,
                          const std::string& field)
{
    return '/' + EscapePointerToken(module) + "/objects/" + EscapePointerToken(object)
         + '/' + EscapePointerToken(field);
}
std::uint64_t Registry::Commit(std::vector<Field> fields,
                               const std::vector<std::string>& erasedPaths)
{
    if (revision_ >= static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))
        throw std::overflow_error("EffectiveConfig revision exhausted");
    const auto next = revision_ + 1;
    auto candidate = fields_; // publication only after all validation and allocation
    std::set<std::string> seen;
    for (const auto& path : erasedPaths) {
        ValidatePath(path);
        if (!seen.insert(path).second) throw std::invalid_argument("Duplicate removal in transaction");
        candidate.erase(path);
    }
    for (auto& field : fields) {
        ValidatePath(field.path);
        if (!seen.insert(field.path).second) throw std::invalid_argument("Duplicate field in transaction");
        Name(field.application_status);
        Name(field.evidence_level);
        if (field.applied_revision && (*field.applied_revision == 0 || *field.applied_revision > next))
            throw std::invalid_argument("Applied revision is outside committed revision history");
        const auto previous = fields_.find(field.path);
        if (field.application_status == ApplicationStatus::Applied) {
            if (field.evidence_level == EvidenceLevel::None || field.evidence_level == EvidenceLevel::ManagerAccepted
                || field.evidence_source.empty())
                throw std::invalid_argument("Applied requires runtime evidence, not Manager acceptance");
            if (!field.applied_revision) {
                // Re-submitting identical runtime evidence must not create a
                // new application event merely because the caller omitted it.
                Field comparable = field;
                if (previous != fields_.end()) {
                    comparable.revision = previous->second.revision;
                    comparable.applied_revision = previous->second.applied_revision;
                }
                if (previous != fields_.end() && FieldValue(comparable).ToJson() == FieldValue(previous->second).ToJson())
                    field.applied_revision = previous->second.applied_revision;
                else field.applied_revision = next;
            }
        } else if (field.applied_revision) {
            throw std::invalid_argument("Non-applied status cannot claim an applied revision");
        }
        field.revision = previous == fields_.end() ? 0 : previous->second.revision;
        const auto serialized = FieldValue(field).ToJson(); // validate before publication
        if (previous == fields_.end() || serialized != FieldValue(previous->second).ToJson()) {
            field.revision = next;
            candidate[field.path] = std::move(field);
        }
    }
    bool changed = candidate.size() != fields_.size();
    if (!changed) {
        for (const auto& item : candidate) {
            const auto old = fields_.find(item.first);
            if (old == fields_.end() || FieldValue(item.second).ToJson() != FieldValue(old->second).ToJson()) {
                changed = true; break;
            }
        }
    }
    if (!changed) return revision_;
    fields_.swap(candidate);
    revision_ = next;
    return revision_;
}
std::uint64_t Registry::ReplaceModule(const std::string& module, std::vector<Field> fields)
{
    const auto prefix = '/' + EscapePointerToken(module) + '/';
    std::set<std::string> incoming;
    for (const auto& field : fields) {
        ValidatePath(field.path);
        if (field.path.compare(0, prefix.size(), prefix) != 0)
            throw std::invalid_argument("Replacement field belongs to another module");
        if (!incoming.insert(field.path).second)
            throw std::invalid_argument("Duplicate field in module replacement");
    }
    std::vector<std::string> removed;
    for (const auto& item : fields_)
        if (item.first.compare(0, prefix.size(), prefix) == 0 && !incoming.count(item.first))
            removed.push_back(item.first);
    return Commit(std::move(fields), removed);
}
Snapshot Registry::Capture(const std::string& stage, std::optional<std::int64_t> run_id) const
{
    if (stage != "configure" && stage != "run_begin" && stage != "finalization")
        throw std::invalid_argument("Unknown EffectiveConfig snapshot stage");
    if ((stage == "run_begin" && !run_id) || (run_id && *run_id < 0))
        throw std::invalid_argument("run_begin requires a nonnegative run ID");
    Snapshot result;
    result.revision_ = revision_;
    result.fields_ = fields_;
    result.stage_ = stage;
    result.run_id_ = run_id;
    return result;
}
Snapshot Snapshot::WithMetadata(Value::Object metadata) const
{
    for (const auto& item : metadata) {
        if (item.first == "schema" || item.first == "stage" || item.first == "revision" ||
            item.first == "run_id" || item.first == "fields")
            throw std::invalid_argument("EffectiveConfig metadata cannot replace reserved snapshot fields");
    }
    Value(metadata).ToJson();
    Snapshot result = *this;
    result.metadata_ = std::move(metadata);
    return result;
}

Snapshot Snapshot::WithApplicationEvidence(const std::vector<Field>& evidence) const
{
    Snapshot result = *this;
    std::set<std::string> seen;
    for (const auto& receipt : evidence) {
        const auto found = result.fields_.find(receipt.path);
        if (found == result.fields_.end() || !seen.insert(receipt.path).second)
            throw std::invalid_argument("Application evidence needs a unique existing configuration field");
        auto& field = found->second;
        if (receipt.revision != field.revision)
            throw std::invalid_argument("Application evidence belongs to a different configuration revision");
        Name(receipt.application_status);
        Name(receipt.evidence_level);
        if (receipt.application_status == ApplicationStatus::Applied) {
            if (receipt.applied_revision && *receipt.applied_revision != field.revision)
                throw std::invalid_argument("Application evidence applied revision is stale");
            if (receipt.evidence_level == EvidenceLevel::None || receipt.evidence_level == EvidenceLevel::ManagerAccepted ||
                receipt.evidence_source.empty() || !receipt.resolved_known || !field.resolved_known ||
                receipt.resolved.ToJson() != field.resolved.ToJson())
                throw std::invalid_argument("Applied evidence must observe this field's resolved value");
            field.applied_revision = field.revision;
        } else {
            if (receipt.applied_revision) throw std::invalid_argument("Non-applied evidence claims an applied revision");
            field.applied_revision.reset();
        }
        field.application_status = receipt.application_status;
        field.evidence_level = receipt.evidence_level;
        field.evidence_source = receipt.evidence_source;
        field.reason = receipt.reason;
    }
    return result;
}

std::string Snapshot::ToJson() const
{
    Value::Array fields;
    for (const auto& item : fields_) fields.push_back(FieldValue(item.second));
    auto value = metadata_;
    value["schema"] = "g4usim_effective_config_v1";
    value["stage"] = stage_;
    value["revision"] = Number(revision_);
    value["run_id"] = run_id_ ? Value(*run_id_) : Value();
    value["fields"] = std::move(fields);
    return Value(value).ToJson();
}
} // namespace effective_config
