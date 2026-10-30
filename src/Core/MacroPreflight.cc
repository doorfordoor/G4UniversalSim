#include "Core/MacroPreflight.hh"
#include "Config/InputProvenance.hh"
#include <sstream>
#include "Core/RandomCommandGuard.hh"

#include "Geometry/GdmlIO.hh"

#include "Utils/StringUtils.hh"

#include <fstream>
#include <set>
#include <stdexcept>
#include <utility>
#include <vector>

namespace {

constexpr std::size_t kMaxMacroDepth = 64;

struct MacroLine {
    std::string command;
    std::string arguments;
    std::string text;
};

std::string Trim(const std::string& value)
{
    return StringUtils::Trim(value);
}

std::string Lower(const std::string& value)
{
    return StringUtils::ToLower(value);
}

std::string StripTrailingComment(const std::string& value)
{
    char quote = '\0';
    for (std::size_t i = 0; i < value.size(); ++i) {
        const char current = value[i];
        if (quote != '\0') {
            if (current == quote) quote = '\0';
            continue;
        }
        if (current == '\'' || current == '"') {
            quote = current;
            continue;
        }
        if (current == '#') {
            return value.substr(0, i);
        }
    }
    return value;
}

std::string MacroLocation(const std::filesystem::path& filename, std::size_t line)
{
    return filename.string() + ":" + std::to_string(line);
}

[[noreturn]] void ThrowMacroError(
    const std::filesystem::path& filename,
    std::size_t line,
    const std::string& message,
    const std::string& command = {}
)
{
    throw MacroPreflightError(filename, line, command, message);
}

std::filesystem::path NormalizeExistingFile(
    const std::filesystem::path& candidate,
    const std::filesystem::path& includingDirectory,
    const std::filesystem::path& includingFile,
    std::size_t line,
    const std::string& command
)
{
    std::vector<std::filesystem::path> candidates;
    if (candidate.is_absolute()) {
        candidates.push_back(candidate);
    } else {
        candidates.push_back(includingDirectory / candidate);
    }

    for (const auto& path : candidates) {
        std::error_code error;
        if (std::filesystem::is_regular_file(path, error)) {
            const auto absolute = std::filesystem::absolute(path, error);
            if (error) {
                ThrowMacroError(includingFile, line, "cannot resolve macro path '" + candidate.string() + "'", command);
            }
            return absolute.lexically_normal();
        }
    }

    ThrowMacroError(
        includingFile,
        line,
        "nested macro file does not exist: '" + candidate.string() + "'",
        command
    );
}

MacroLine ParseMacroLine(
    const std::string& rawLine,
    const std::filesystem::path& filename,
    std::size_t line
)
{
    std::string value = rawLine;
    if (line == 1 && value.size() >= 3 &&
        static_cast<unsigned char>(value[0]) == 0xEF &&
        static_cast<unsigned char>(value[1]) == 0xBB &&
        static_cast<unsigned char>(value[2]) == 0xBF) {
        value.erase(0, 3);
    }
    value = Trim(StripTrailingComment(value));
    value = StringUtils::NormalizeCommandSlashes(value);
    if (value.empty() || value[0] == '#') return {};

    const std::size_t separator = value.find_first_of(" \t\r\n");
    const std::string command = Lower(value.substr(0, separator));
    if (command.empty()) return {};
    if (command[0] != '/') {
        ThrowMacroError(
            filename,
            line,
            "unsupported dynamic or alias macro line; commands must use an absolute Geant4 command path"
        );
    }

    const std::string arguments = separator == std::string::npos
        ? ""
        : Trim(value.substr(separator + 1));
    return {command, arguments, value};
}

std::string ParseSingleMacroPath(
    const MacroLine& line,
    const std::filesystem::path& filename,
    std::size_t lineNumber
)
{
    if (line.arguments.empty()) {
        ThrowMacroError(filename, lineNumber, "missing nested macro path for /control/execute", line.text);
    }

    const char quote = line.arguments.front();
    std::string path;
    if (quote == '\'' || quote == '"') {
        const std::size_t closing = line.arguments.find(quote, 1);
        if (closing == std::string::npos || !Trim(line.arguments.substr(closing + 1)).empty()) {
            ThrowMacroError(filename, lineNumber, "invalid quoted path for /control/execute", line.text);
        }
        path = line.arguments.substr(1, closing - 1);
    } else {
        path = line.arguments;
    }

    if (path.find('{') != std::string::npos ||
        path.find('}') != std::string::npos ||
        path.find('$') != std::string::npos) {
        ThrowMacroError(
            filename,
            lineNumber,
            "dynamic alias value in /control/execute is not supported by macro preflight",
            line.text
        );
    }
    return path;
}

class MacroScanner {
public:
    explicit MacroScanner(const MacroPreflightLocks& locks)
        : locks_(locks)
    {
    }

    std::vector<MacroCommand> Scan(const std::filesystem::path& filename)
    {
        ScanFile(filename, 0);
        return commands_;
    }
    const std::vector<std::pair<std::string, std::string>>& Inputs() const { return inputs_; }

private:
    void CheckCommand(
        const MacroLine& line,
        const std::filesystem::path& filename,
        std::size_t lineNumber
    ) const
    {
        // Macro preflight follows Configure(); a late main-config switch
        // would desynchronize already-configured managers from the summary.
        if (line.command == "/aihl/app/setmainconfig") {
            ThrowMacroError(
                filename, lineNumber,
                "/AIHL/app/setMainConfig cannot change the main config after Configure(); use --config <file> at process startup instead",
                line.text
            );
        }
        std::string conflict;
        if (locks_.outputDir &&
            (line.command == "/aihl/app/setoutputdir" || line.command == "/aihl/output/setdir")) {
            conflict = "output directory";
        } else if (locks_.numThreads &&
                   (line.command == "/aihl/app/setnumthreads" ||
                    line.command == "/run/numberofthreads" ||
                    line.command == "/run/setnumberofthreads")) {
            conflict = "thread count";
        } else if (locks_.seed &&
                   (line.command == "/aihl/app/setseed" ||
                    line.command.rfind("/random/", 0) == 0)) {
            conflict = "random seed/state";
        } else if (locks_.checkOverlaps &&
                   (line.command == "/aihl/app/setcheckoverlaps" ||
                    line.command == "/aihl/geometry/checkoverlaps")) {
            conflict = "geometry overlap checking";
        }

        if (!conflict.empty()) {
            ThrowMacroError(
                filename,
                lineNumber,
                "command '" + line.command + "' conflicts with an explicit CLI lock for " + conflict,
                line.text
            );
        }

        // Native random commands can return success after ignoring malformed
        // arguments. Validate semantics before any command from this macro runs.
        try {
            RandomCommandGuard::Validate(line.text);
        } catch (const std::exception& error) {
            ThrowMacroError(filename, lineNumber, error.what(), line.text);
        }

        const std::string arguments = Lower(Trim(line.arguments));
        const bool enableValue = arguments == "true" || arguments == "1"
            || arguments == "on" || arguments == "yes";
        std::string unsupported;
        if ((line.command == "/aihl/scoring/let"
             || line.command == "/aihl/scoring/dose"
             || line.command == "/aihl/scoring/fluence") && enableValue) {
            unsupported = "LET/Dose/Fluence scoring cannot be enabled from a macro; set let/dose/fluence = true "
                          "in the main INI [scoring] section instead (they need default scorers created before initialization)";
        } else if (line.command == "/aihl/geometry/settemplate" && arguments == "gdml" && !GdmlIO::Available()) {
            unsupported = "GDML geometry is not supported; use a supported geometry template and regular volume definitions instead";
        } else if (line.command == "/aihl/material/add"
                   && (arguments.find("temperature=") != std::string::npos
                       || arguments.find("pressure=") != std::string::npos)) {
            unsupported = "material temperature/pressure is not supported; use density, state, and composition only";
        }
        if (!unsupported.empty()) {
            ThrowMacroError(
                filename,
                lineNumber,
                unsupported,
                line.text
            );
        }

        if (line.command == "/control/alias" ||
            line.command == "/control/loop" ||
            line.command == "/control/foreach" ||
            line.command == "/control/if" || line.command == "/control/doif" ||
            line.command == "/control/strif" || line.command == "/control/strdoif") {
            ThrowMacroError(
                filename,
                lineNumber,
                "dynamic macro command '" + line.command + "' is not supported by preflight",
                line.text
            );
        }
    }

    void ScanFile(const std::filesystem::path& filename, std::size_t depth)
    {
        if (depth > kMaxMacroDepth) {
            ThrowMacroError(filename, 0, "nested macro depth exceeds the preflight limit");
        }
        if (active_.find(filename) != active_.end()) {
            ThrowMacroError(filename, 0, "recursive /control/execute cycle detected");
        }
        input_provenance::InputFile accepted;
        try { accepted = input_provenance::ReadFile(filename.u8string(), "macro", "recursive_preflight"); }
        catch (const std::exception&) { ThrowMacroError(filename, 0, "cannot open macro file"); }
        std::istringstream input(accepted.bytes);
        inputs_.emplace_back(accepted.path, accepted.sha256);

        active_.insert(filename);
        std::string rawLine;
        std::size_t lineNumber = 0;
        while (std::getline(input, rawLine)) {
            ++lineNumber;
            const MacroLine line = ParseMacroLine(rawLine, filename, lineNumber);
            if (line.command.empty()) continue;

            CheckCommand(line, filename, lineNumber);
            if (line.command != "/control/execute") {
                commands_.push_back({filename, lineNumber, line.text, accepted.sha256, rawLine});
                continue;
            }

            const std::string nestedName = ParseSingleMacroPath(line, filename, lineNumber);
            const auto nestedPath = NormalizeExistingFile(
                std::filesystem::u8path(nestedName),
                filename.parent_path(),
                filename,
                lineNumber,
                line.text
            );
            ScanFile(nestedPath, depth + 1);
            continue;
        }

        active_.erase(filename);
    }

    MacroPreflightLocks locks_;
    std::set<std::filesystem::path> active_;
    std::vector<MacroCommand> commands_;
    std::vector<std::pair<std::string, std::string>> inputs_;
};

}  // namespace

MacroPreflightError::MacroPreflightError(std::filesystem::path file,
                                         std::size_t line,
                                         std::string command,
                                         std::string message)
    : std::runtime_error(file.string() + ":" + std::to_string(line) + ": " + message),
      file_(std::move(file)),
      line_(line),
      command_(std::move(command))
{
}

MacroPreflightResult PreflightMacro(
    const std::string& filename,
    const MacroPreflightLocks& locks
)
{
    const std::filesystem::path requested(filename);
    const auto topLevel = NormalizeExistingFile(
        requested,
        std::filesystem::current_path(),
        requested,
        0,
        {}
    );

    MacroScanner scanner(locks);
    const auto commands = scanner.Scan(topLevel);
    return {topLevel, commands, scanner.Inputs()};
}
