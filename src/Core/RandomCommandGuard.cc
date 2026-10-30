#include "Core/RandomCommandGuard.hh"
#include "Config/InputProvenance.hh"

#include "G4ApplicationState.hh"
#include "G4RunManager.hh"
#include "G4StateManager.hh"
#include "Randomize.hh"
#include "CLHEP/Random/DoubConv.h"
#include "CLHEP/Random/JamesRandom.h"
#include "CLHEP/Random/MixMaxRng.h"

#include <charconv>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <limits>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <vector>

namespace {
constexpr std::size_t kMaximumStatusBytes = 1024 * 1024;
constexpr std::uint64_t kMask32 = 0xffffffffULL;
constexpr std::uint64_t kMixMaxModulus = (std::uint64_t{1} << 61) - 1;

[[noreturn]] void Refuse(const std::string& reason)
{
    throw std::runtime_error("Random command rejected: " + reason);
}

std::string Trim(const std::string& value)
{
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    return value.substr(first, value.find_last_not_of(" \t\r\n") - first + 1);
}

struct Command {
    std::string name;
    std::string arguments;
};

Command Split(const std::string& line)
{
    const std::string text = Trim(line);
    const auto space = text.find_first_of(" \t");
    if (space == std::string::npos) return {text, {}};
    return {text.substr(0, space), Trim(text.substr(space + 1))};
}

std::string RestoreArgument(const std::string& arguments)
{
    if (arguments.empty()) return "currentRun.rndm";
    std::string path = arguments;
    if (path.front() == '\'' || path.front() == '"') {
        if (path.size() < 2 || path.back() != path.front()) Refuse("restore path has unmatched quotes");
        path = path.substr(1, path.size() - 2);
    }
    if (path.empty()) Refuse("restore path must not be empty");
    for (unsigned char c : path) {
        if (c < 32 || c == 127 || c == '\'' || c == '"') Refuse("restore path has a control character or invalid quote");
    }
    return path;
}

void ValidateSeeds(const std::string& arguments)
{
    std::istringstream stream(arguments);
    std::string token;
    std::size_t count = 0;
    while (stream >> token) {
        if (++count > 99) Refuse("/random/setSeeds accepts at most 99 nonzero long integers (native seeds[100] reserves a terminator)");
        const char* first = token.data();
        const char* last = first + token.size();
        if (first != last && *first == '+') ++first;
        if (first == last || (token.front() == '+' && (*first == '+' || *first == '-'))) Refuse("setSeeds needs complete long integers");
        long value = 0;
        const auto parsed = std::from_chars(first, last, value, 10);
        if (parsed.ec != std::errc{} || parsed.ptr != last) Refuse("setSeeds value is not a complete integer in signed long range");
        if (value == 0) Refuse("setSeeds does not accept explicit 0; Geant4 appends its own terminating 0");
        if (value == std::numeric_limits<long>::min()) Refuse("setSeeds LONG_MIN is unsafe for CLHEP engines that negate negative seeds");
    }
    if (count < 2) Refuse("/random/setSeeds needs at least two nonzero long integers");
}

void ValidatePerEvent(const std::string& arguments)
{
    std::string value = arguments;
    for (char& c : value) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    if (value.empty() || value == "false" || value == "0" || value == "f" || value == "no" || value == "n" || value == "off") return;
    Refuse("/random/resetEngineFromEachEvent enable is unsupported: worker per-event restore has no safe validation hook; use /random/setSeeds or a validated single /random/resetEngineFrom");
}

class StatusReader {
public:
    explicit StatusReader(const std::string& text) : text_(text) {}
    void Expect(const std::string& token)
    {
        Space();
        if (text_.compare(position_, token.size(), token) != 0) Refuse("restore state has invalid or wrong-engine format near " + token);
        position_ += token.size();
    }
    std::string Word()
    {
        Space();
        const auto begin = position_;
        while (position_ < text_.size() && !std::isspace(static_cast<unsigned char>(text_[position_]))) ++position_;
        return text_.substr(begin, position_ - begin);
    }
    std::uint64_t Unsigned()
    {
        Space();
        const auto begin = position_;
        while (position_ < text_.size() && text_[position_] >= '0' && text_[position_] <= '9') ++position_;
        if (position_ == begin) Refuse("restore state requires an unsigned integer");
        std::uint64_t value = 0;
        const auto parsed = std::from_chars(text_.data() + begin, text_.data() + position_, value, 10);
        if (parsed.ec != std::errc{}) Refuse("restore state integer is out of range");
        return value;
    }
    void End()
    {
        Space();
        if (position_ != text_.size()) Refuse("restore state has extra or malformed trailing data");
    }
private:
    void Space()
    {
        while (position_ < text_.size() && std::isspace(static_cast<unsigned char>(text_[position_]))) ++position_;
    }
    const std::string& text_;
    std::size_t position_ = 0;
};

std::string ReadSnapshot(const std::string& argument, std::string& resolvedPath)
{
    std::string path = argument;
    // Match G4RunManager::RestoreRandomNumberStatus exactly, including its
    // slash-based directory rule rather than inventing a different resolver.
    if (path.find('/') == std::string::npos) {
        auto* runManager = G4RunManager::GetRunManager();
        path = (runManager ? std::string(runManager->GetRandomNumberStoreDir()) : "./") + path;
    }
    resolvedPath = path;
    const auto file = std::filesystem::u8path(path);
    std::error_code error;
    if (!std::filesystem::is_regular_file(file, error)) Refuse("restore file is missing or is not a regular file: '" + path + "'");
    std::ifstream input(file, std::ios::binary | std::ios::ate);
    if (!input) Refuse("cannot open restore file '" + path + "'");
    const auto length = input.tellg();
    if (length <= 0 || length > static_cast<std::streamoff>(kMaximumStatusBytes)) Refuse("restore file is empty or exceeds supported native-state size (1 MiB)");
    std::string bytes(static_cast<std::size_t>(length), '\0');
    input.seekg(0);
    input.read(bytes.data(), static_cast<std::streamsize>(bytes.size()));
    if (!input || input.gcount() != static_cast<std::streamsize>(bytes.size())) Refuse("restore file could not be read completely");
    char extra = 0;
    if (input.get(extra)) Refuse("restore file grew while its state snapshot was read");
    if (input.bad()) Refuse("restore file encountered an I/O failure after its snapshot");
    input.clear();
    input.close();
    if (input.fail()) Refuse("restore file could not be closed after its snapshot");
    return bytes;
}

std::vector<unsigned long> ParseMixMax(const std::string& bytes, const std::vector<unsigned long>& current)
{
    if (current.size() < 6 || (current.size() - 4) % 2 != 0) Refuse("unsupported current MixMax state layout");
    const std::size_t dimension = (current.size() - 4) / 2;
    StatusReader reader(bytes);
    reader.Expect("mixmax state, file version 1.0");
    reader.Expect("N"); reader.Expect("=");
    if (reader.Unsigned() != dimension) Refuse("restore MixMax dimension differs from current engine");
    reader.Expect(";"); reader.Expect("V[N]"); reader.Expect("="); reader.Expect("{");
    std::vector<unsigned long> result = current;
    bool nonzero = false;
    for (std::size_t i = 0; i < dimension; ++i) {
        if (i) reader.Expect(",");
        const auto value = reader.Unsigned();
        if (value > kMixMaxModulus) Refuse("restore MixMax state component is out of range");
        nonzero = nonzero || value != 0;
        result[2 * i + 1] = static_cast<unsigned long>(value & kMask32);
        result[2 * i + 2] = static_cast<unsigned long>(value >> 32);
    }
    if (!nonzero) Refuse("restore MixMax state is a degenerate zero vector");
    reader.Expect("}"); reader.Expect(";"); reader.Expect("counter"); reader.Expect("=");
    const auto counter = reader.Unsigned();
    if (counter > dimension) Refuse("restore MixMax counter is out of range");
    result[2 * dimension + 1] = static_cast<unsigned long>(counter);
    reader.Expect(";"); reader.Expect("sumtot"); reader.Expect("=");
    const auto checksum = reader.Unsigned();
    if (checksum > kMixMaxModulus) Refuse("restore MixMax checksum is out of range");
    result[2 * dimension + 2] = static_cast<unsigned long>(checksum & kMask32);
    result[2 * dimension + 3] = static_cast<unsigned long>(checksum >> 32);
    reader.Expect(";"); reader.End();
    return result;
}

std::vector<unsigned long> ParseJames(const std::string& bytes, const std::vector<unsigned long>& current)
{
    if (current.size() != 202) Refuse("unsupported current James state layout");
    StatusReader reader(bytes);
    if (reader.Word() != "Uvec") Refuse("restore James file must use its native Uvec saveStatus format (wrong engine or unsupported legacy format)");
    std::vector<unsigned long> result;
    for (std::size_t i = 0; i < current.size(); ++i) {
        // Word boundaries matter: unlike MixMax grammar there is no delimiter.
        const std::string word = reader.Word();
        std::uint64_t value = 0;
        const auto parsed = std::from_chars(word.data(), word.data() + word.size(), value, 10);
        if (word.empty() || parsed.ec != std::errc{} || parsed.ptr != word.data() + word.size() || value > kMask32)
            Refuse("restore James file has truncated or out-of-range state words");
        result.push_back(static_cast<unsigned long>(value));
    }
    reader.End();
    if (result[0] != current[0]) Refuse("restore file engine ID differs from the current James engine");
    if (result[201] > 96) Refuse("restore James state index is out of range");
    const auto unpack = [&](std::size_t offset) {
        const std::vector<unsigned long> pair{result[offset], result[offset + 1]};
        return CLHEP::DoubConv::longs2double(pair);
    };
    constexpr double kJamesGrid = 16777216.0;
    const auto onGrid = [=](double value) { return std::floor(value * kJamesGrid) == value * kJamesGrid; };
    for (std::size_t i = 0; i < 97; ++i) {
        const double value = unpack(2 * i + 1);
        if (!std::isfinite(value) || value < 0.0 || value >= 1.0 || !onGrid(value)) Refuse("restore James state contains a nonfinite or invalid random fraction");
    }
    const double c = unpack(195), cd = unpack(197), cm = unpack(199);
    constexpr double kJamesCd = 7654321.0 / kJamesGrid;
    constexpr double kJamesCm = 16777213.0 / kJamesGrid;
    if (!std::isfinite(c) || !std::isfinite(cd) || !std::isfinite(cm) || c < 0.0 || c >= cm || !onGrid(c) || cd != kJamesCd || cm != kJamesCm)
        Refuse("restore James carry/constants are nonfinite or out of range");
    return result;
}
}  // namespace

namespace RandomCommandGuard {
void Validate(const std::string& command)
{
    const auto parsed = Split(command);
    if (parsed.name == "/random/setSeeds") ValidateSeeds(parsed.arguments);
    else if (parsed.name == "/random/resetEngineFrom") (void)RestoreArgument(parsed.arguments);
    else if (parsed.name == "/random/resetEngineFromEachEvent") ValidatePerEvent(parsed.arguments);
}

bool ExecuteRestoreIfRequested(const std::string& command)
{
    const auto parsed = Split(command);
    if (parsed.name != "/random/resetEngineFrom") return false;
    const std::string path = RestoreArgument(parsed.arguments);
    const auto state = G4StateManager::GetStateManager()->GetCurrentState();
    if (state != G4State_PreInit && state != G4State_Idle && state != G4State_GeomClosed)
        Refuse("restore is available only in PreInit, Idle or GeomClosed state");
    auto* current = G4Random::getTheEngine();
    if (!current) Refuse("there is no current random engine");
    auto* mixmax = dynamic_cast<CLHEP::MixMaxRng*>(current);
    auto* james = dynamic_cast<CLHEP::HepJamesRandom*>(current);
    if (!mixmax && !james) Refuse("restore for current engine '" + current->name() + "' is unsupported; use /random/setSeeds instead");
    const auto before = current->put();
    std::unique_ptr<CLHEP::HepRandomEngine> candidate;
    std::string resolvedPath;
    const std::string bytes = ReadSnapshot(path, resolvedPath);
    // Observe the complete bounded bytes before parsing or mutating the engine.
    // A rejected native state is still a read; ledger failures leave the engine unchanged.
    input_provenance::RecordRead(resolvedPath,
        {input_provenance::Sha256(bytes), static_cast<std::uint64_t>(bytes.size())},
        "random_restore", "engine_restore_validation", "bounded_binary_snapshot");
    std::vector<unsigned long> restored;
    if (mixmax) {
        candidate = std::make_unique<CLHEP::MixMaxRng>(*mixmax);
        restored = ParseMixMax(bytes, before);
    } else {
        candidate = std::make_unique<CLHEP::HepJamesRandom>(*james);
        restored = ParseJames(bytes, before);
    }
    if (!candidate->get(restored) || candidate->put() != restored) Refuse("restore engine state failed validation (including checksum); current engine is unchanged");
    try {
        if (!current->get(restored) || current->put() != restored) Refuse("restore commit did not reproduce the validated state");
    } catch (...) {
        bool rolledBack = false;
        try { rolledBack = current->get(before) && current->put() == before; } catch (...) {}
        Refuse(rolledBack ? "restore commit failed; previous engine state was restored" : "restore commit and rollback failed; stop this process");
    }
    return true;
}
}  // namespace RandomCommandGuard
