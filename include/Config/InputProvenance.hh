#pragma once
#include <string>
#include <string_view>
namespace input_provenance {
struct InputFile {
    std::string path;
    std::string bytes;
    std::string sha256;
};
// Hash exact bytes, including BOM/newlines/NUL; no text normalization.
std::string Sha256(std::string_view bytes);
// One binary read. Callers must parse bytes from this returned object.
InputFile ReadFile(const std::string& path);
}
