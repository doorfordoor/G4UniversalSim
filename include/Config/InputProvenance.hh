#pragma once
#include <cstddef>
#include <string>
#include <string_view>
#include <cstdint>
#include <optional>
#include <memory>
#include <vector>
namespace input_provenance {
struct InputFile {
    std::string path;
    std::string bytes;
    std::string sha256;
};
struct FileDigest {
    std::string sha256;
    std::uint64_t size_bytes = 0;
};
struct InputObservation {
    std::uint64_t sequence = 0;
    std::string path, kind, role, capture_method, status;
    std::optional<std::string> sha256;
    std::optional<std::uint64_t> size_bytes;
    std::string reason;
};
// Incrementally hash the exact bytes consumed by a streaming parser.
class StreamDigest {
public:
    StreamDigest();
    ~StreamDigest();
    void Update(std::string_view bytes);
    FileDigest Finish();
private:
    struct State;
    std::unique_ptr<State> state_;
};
// Metadata only; repeated reads remain separate. A read is not semantic acceptance.
void RecordRead(const std::string& path, const FileDigest& digest,
                const std::string& kind, const std::string& role,
                const std::string& capture_method);
void MarkUnobserved(const std::string& path, const std::string& reason,
                    const std::string& kind = "native_command",
                    const std::string& role = "runtime_input",
                    const std::string& capture_method = "unobserved");
std::vector<InputObservation> Snapshot();
// Hash exact bytes, including BOM/newlines/NUL; no text normalization.
std::string Sha256(std::string_view bytes);
// One binary read. Callers must parse bytes from this returned object.
InputFile ReadFile(const std::string& path, const std::string& kind = "project_file",
                   const std::string& role = "parser_input",
                   std::optional<std::size_t> maxBytes = std::nullopt);
// Stream bounded blocks; never adds an input observation.
FileDigest HashFile(const std::string& path);
}
