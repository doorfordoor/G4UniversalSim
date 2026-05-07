#include "Utils/FileUtils.hh"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <system_error>

namespace fs = std::filesystem;

namespace {

std::runtime_error MakeFileError(const std::string& action, const std::string& path)
{
    return std::runtime_error("FileUtils failed to " + action + ": '" + path + "'");
}

}  // namespace

namespace FileUtils {

bool Exists(const std::string& path)
{
    std::error_code ec;
    return fs::exists(fs::path(path), ec);
}

bool IsFile(const std::string& path)
{
    std::error_code ec;
    return fs::is_regular_file(fs::path(path), ec);
}

bool IsDirectory(const std::string& path)
{
    std::error_code ec;
    return fs::is_directory(fs::path(path), ec);
}

void CreateDirectories(const std::string& path)
{
    std::error_code ec;
    fs::create_directories(fs::path(path), ec);

    if (ec || !IsDirectory(path)) {
        throw std::runtime_error(
            "FileUtils failed to create directories: '" + path + "'"
            + (ec ? " (" + ec.message() + ")" : "")
        );
    }
}

std::string CanonicalPath(const std::string& path)
{
    std::error_code ec;
    const fs::path result = fs::weakly_canonical(fs::path(path), ec);
    if (ec) {
        throw std::runtime_error(
            "FileUtils failed to canonicalize path: '" + path + "' (" + ec.message() + ")"
        );
    }
    return result.string();
}

std::string AbsolutePath(const std::string& path)
{
    std::error_code ec;
    const fs::path result = fs::absolute(fs::path(path), ec);
    if (ec) {
        throw std::runtime_error(
            "FileUtils failed to make absolute path: '" + path + "' (" + ec.message() + ")"
        );
    }
    return result.string();
}

std::string JoinPath(const std::string& a, const std::string& b)
{
    return (fs::path(a) / fs::path(b)).string();
}

std::string ParentPath(const std::string& path)
{
    return fs::path(path).parent_path().string();
}

std::string Filename(const std::string& path)
{
    return fs::path(path).filename().string();
}

std::string Extension(const std::string& path)
{
    return fs::path(path).extension().string();
}

std::string ReadTextFile(const std::string& path)
{
    if (!IsFile(path)) {
        throw MakeFileError("read missing file", path);
    }

    std::ifstream input(path);
    if (!input) {
        throw MakeFileError("open file for reading", path);
    }

    std::ostringstream buffer;
    buffer << input.rdbuf();

    if (input.bad()) {
        throw MakeFileError("read file", path);
    }

    return buffer.str();
}

void WriteTextFile(const std::string& path, const std::string& content)
{
    const fs::path filePath(path);
    const fs::path parent = filePath.parent_path();
    if (!parent.empty()) {
        CreateDirectories(parent.string());
    }

    std::ofstream output(path);
    if (!output) {
        throw MakeFileError("open file for writing", path);
    }

    output << content;
    if (!output) {
        throw MakeFileError("write file", path);
    }
}

}  // namespace FileUtils
