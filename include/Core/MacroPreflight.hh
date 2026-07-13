#pragma once

#include <filesystem>
#include <cstddef>
#include <stdexcept>
#include <string>
#include <vector>

struct MacroPreflightLocks {
    bool outputDir = false;
    bool numThreads = false;
    bool seed = false;
    bool checkOverlaps = false;
};

class MacroPreflightError : public std::runtime_error {
public:
    MacroPreflightError(std::filesystem::path file,
                        std::size_t line,
                        std::string command,
                        std::string message);

    const std::filesystem::path& File() const noexcept { return file_; }
    std::size_t Line() const noexcept { return line_; }
    const std::string& Command() const noexcept { return command_; }

private:
    std::filesystem::path file_;
    std::size_t line_ = 0;
    std::string command_;
};

struct MacroCommand {
    std::filesystem::path sourceFile;
    std::size_t lineNumber = 0;
    std::string text;
};

struct MacroPreflightResult {
    std::filesystem::path macroPath;
    std::vector<MacroCommand> commands;
};

MacroPreflightResult PreflightMacro(
    const std::string& filename,
    const MacroPreflightLocks& locks
);
