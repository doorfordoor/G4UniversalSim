#pragma once

#include <filesystem>
#include <cstddef>
#include <string>
#include <vector>

struct MacroPreflightLocks {
    bool outputDir = false;
    bool numThreads = false;
    bool seed = false;
    bool checkOverlaps = false;
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
