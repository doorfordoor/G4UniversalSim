// Versioned controlled-session server (F2, protocol g4usim-session-v1).
//
// Threading model: the process main thread owns every Geant4 call. A reader
// thread only parses stdin frames, records a cancel intent and wakes the main
// loop; it never touches Geant4 or the session state without the state mutex.

#include "Core/SessionServer.hh"

#include "Config/InputProvenance.hh"
#include "Core/SessionJson.hh"
#include "Core/SimulationManager.hh"
#include "Geometry/GeometryManager.hh"
#include "Output/OutputManager.hh"
#include "Source/SourceManager.hh"
#include "Utils/UnitParser.hh"

#include "BuildInfo.hh"
#include "G4RunManager.hh"
#include "G4ParticleTable.hh"
#include "G4UImanager.hh"
#include "G4Version.hh"
#include "CLHEP/Random/Random.h"
#include "Core/Geant4DataLocator.hh"

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#else
#include <poll.h>
#include <unistd.h>
#endif

namespace {

constexpr const char* kProtocol = "g4usim-session-v1";
constexpr std::size_t kMaxFrameBytes = SessionJson::kMaxDocumentBytes;
constexpr long long kMaxSessionEvents = 100000000LL;
constexpr std::size_t kDedupCapacity = 256;
constexpr std::size_t kExpiredCapacity = 512;
constexpr auto kReadPoll = std::chrono::milliseconds(50);

std::atomic<int> g_cancelRunId{-1};
std::atomic<SessionServer*> g_activeServer{nullptr};

std::string NowIso8601()
{
    const auto now = std::chrono::system_clock::now();
    const std::time_t seconds = std::chrono::system_clock::to_time_t(now);
    std::tm utc{};
#ifdef _WIN32
    gmtime_s(&utc, &seconds);
#else
    gmtime_r(&seconds, &utc);
#endif
    std::ostringstream out;
    out << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ");
    return out.str();
}

bool IsHexId(const std::string& value)
{
    if (value.empty() || value.size() > 64) return false;
    return std::all_of(value.begin(), value.end(), [](unsigned char c) {
        return std::isxdigit(c) != 0;
    });
}

std::string NewSessionId()
{
    std::ostringstream out;
    const auto seed = static_cast<unsigned long long>(std::chrono::steady_clock::now().time_since_epoch().count());
    std::uint64_t state = seed ^ 0x9e3779b97f4a7c15ULL;
    for (int byte = 0; byte < 16; ++byte) {
        state ^= state >> 12; state ^= state << 25; state ^= state >> 27;
        const unsigned value = static_cast<unsigned>((state * 0x2545F4914F6CDD1DULL) >> 56) & 0xFF;
        out << std::hex << std::setw(2) << std::setfill('0') << value;
    }
    return out.str();
}

std::string ScopeName(OutputManager::ArtifactScope scope)
{
    switch (scope) {
        case OutputManager::ArtifactScope::Process: return "process";
        case OutputManager::ArtifactScope::Run: return "run";
        case OutputManager::ArtifactScope::Thread: return "thread";
    }
    return "unknown";
}

SessionJson::Json OptionalString(const std::optional<std::string>& value)
{
    return value.has_value() ? SessionJson::Json(*value) : SessionJson::Json();
}

SessionJson::Json OptionalInt(const std::optional<int>& value)
{
    return value.has_value() ? SessionJson::Json(*value) : SessionJson::Json();
}

SessionJson::Json OptionalUInt(const std::optional<std::uint64_t>& value)
{
    return value.has_value() ? SessionJson::Json(*value) : SessionJson::Json();
}

bool ParseLengthVector(const std::string& text, std::array<double, 3>& out)
{
    std::string normalized = text;
    std::replace(normalized.begin(), normalized.end(), ',', ' ');
    std::istringstream stream(normalized);
    std::vector<std::string> tokens;
    for (std::string token; stream >> token;) tokens.push_back(token);
    if (tokens.size() != 4) return false;
    try {
        const double factor = UnitParser::ParseLength("1 " + tokens[3]);
        for (int axis = 0; axis < 3; ++axis) out[axis] = UnitParser::ParseDouble(tokens[axis]) * factor;
    } catch (const std::exception&) {
        return false;
    }
    return std::all_of(out.begin(), out.end(), [](double value) { return std::isfinite(value); });
}

bool ParseNumberTriple(const std::string& text, std::array<double, 3>& out)
{
    std::string normalized = text;
    std::replace(normalized.begin(), normalized.end(), ',', ' ');
    std::istringstream stream(normalized);
    std::vector<double> values;
    for (std::string token; stream >> token;) {
        try {
            values.push_back(UnitParser::ParseDouble(token));
        } catch (const std::exception&) {
            return false;
        }
    }
    if (values.size() != 3) return false;
    std::copy(values.begin(), values.end(), out.begin());
    return std::all_of(out.begin(), out.end(), [](double value) { return std::isfinite(value); });
}

bool ParseDirectionTriple(const std::string& text, std::array<double, 3>& out)
{
    std::string normalized = text;
    std::transform(normalized.begin(), normalized.end(), normalized.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    while (!normalized.empty() && std::isspace(static_cast<unsigned char>(normalized.front()))) normalized.erase(normalized.begin());
    while (!normalized.empty() && std::isspace(static_cast<unsigned char>(normalized.back()))) normalized.pop_back();
    if (normalized == "+x") { out = {1.0, 0.0, 0.0}; return true; }
    if (normalized == "-x") { out = {-1.0, 0.0, 0.0}; return true; }
    if (normalized == "+y") { out = {0.0, 1.0, 0.0}; return true; }
    if (normalized == "-y") { out = {0.0, -1.0, 0.0}; return true; }
    if (normalized == "+z") { out = {0.0, 0.0, 1.0}; return true; }
    if (normalized == "-z") { out = {0.0, 0.0, -1.0}; return true; }
    if (!ParseNumberTriple(text, out)) return false;
    const double norm = std::sqrt(out[0] * out[0] + out[1] * out[1] + out[2] * out[2]);
    return std::isfinite(norm) && norm > 0.0;
}

std::string PadRun(int runId)
{
    std::ostringstream out;
    out << std::setw(4) << std::setfill('0') << runId;
    return out.str();
}

// ---------------------------------------------------------------- replay files
// Replay snapshots live next to the session record. They are written with an
// explicit schema and are validated again when a replay starts; a snapshot that
// cannot be written aborts the session instead of silently losing the state.

std::string ReplayNormalizePath(const std::string& text)
{
    std::error_code error;
    const std::filesystem::path path(text);
    const std::filesystem::path absolute = std::filesystem::absolute(path, error);
    if (error) return path.lexically_normal().generic_string();
    const std::filesystem::path canonical = std::filesystem::weakly_canonical(absolute, error);
    return (error ? absolute.lexically_normal() : canonical).generic_string();
}

bool ReplayReadText(const std::filesystem::path& path, std::string& out)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) return false;
    std::ostringstream buffer;
    buffer << input.rdbuf();
    if (input.bad()) return false;
    out = buffer.str();
    return true;
}

bool ReplayWriteText(const std::filesystem::path& path, const std::string& text)
{
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) return false;
    output.write(text.data(), static_cast<std::streamsize>(text.size()));
    output.flush();
    return output.good();
}

bool HashFilesParallel(const std::vector<std::string>& files,
                       std::vector<input_provenance::FileDigest>& digests,
                       std::string& errorText)
{
    errorText.clear();
    digests.assign(files.size(), input_provenance::FileDigest{});
    if (files.empty()) return true;
    unsigned workers = std::thread::hardware_concurrency();
    if (workers == 0) workers = 4;
    workers = std::min<unsigned>(workers, 12u);
    workers = std::min<unsigned>(workers, static_cast<unsigned>(files.size()));
    std::atomic<std::size_t> next{0};
    std::atomic<bool> failed{false};
    std::mutex errorMutex;
    std::string firstError;
    auto run = [&]() {
        for (;;) {
            if (failed.load()) return;
            const std::size_t index = next.fetch_add(1);
            if (index >= files.size()) return;
            try {
                digests[index] = input_provenance::HashFile(files[index]);
            } catch (const std::exception& exception) {
                std::lock_guard<std::mutex> lock(errorMutex);
                if (!failed.exchange(true)) {
                    firstError = "could not hash " + files[index] + ": " + exception.what();
                }
                return;
            }
        }
    };
    std::vector<std::thread> threads;
    threads.reserve(workers);
    for (unsigned index = 0; index < workers; ++index) threads.emplace_back(run);
    for (auto& thread : threads) thread.join();
    if (failed.load()) {
        errorText = firstError;
        return false;
    }
    return true;
}


}  // namespace

namespace SessionControl {

bool CancelRequested(int runId) noexcept
{
    if (runId < 0) return false;
    const int target = g_cancelRunId.load(std::memory_order_acquire);
    return target >= 0 && target == runId;
}

void OnRunBegin(int runId, int plannedEvents)
{
    if (SessionServer* server = g_activeServer.load(std::memory_order_acquire)) {
        server->HandleRunBegin(runId, plannedEvents);
    }
}

void OnRunEnd(int runId, int plannedEvents, int completedEvents, long long abortedEvents,
              bool outputFailed, OutputManager* outputManager)
{
    if (SessionServer* server = g_activeServer.load(std::memory_order_acquire)) {
        server->HandleRunEnd(runId, plannedEvents, completedEvents, abortedEvents, outputFailed,
                             outputManager);
    }
}

}  // namespace SessionControl

struct SessionServer::Impl {
    SessionServer* owner = nullptr;
    SimulationManager& simulation;
    std::string recordRoot;
    std::string sessionRoot;
    std::string outputRoot;
    std::string sessionId = NewSessionId();

    // ------------------------------------------------------------- replay (F2)
    std::string replaySource;
    bool replayMode = false;
    bool replayPrepared = false;
    bool replayExecuted = false;
    bool helloSeen = false;
    bool replaySnapshotReady = false;
    bool replayPlanValid = true;
    std::string replayInvalidReason;
    SessionJson::Json replaySnapshot;
    SessionJson::Json replayManifest;
    SessionJson::Json replayPreRunProvenance;
    bool replayDataIdentityReady = false;
    SessionJson::Json replayInfo;
    std::vector<SessionJson::Json> replaySteps;
    int replayCurrentRunStep = -1;
    long long replayRequestCounter = 0;
    std::string lastRunStatus;
    long long lastRunCompletedEvents = -1;
    int lastRunId = -1;
    // The replay executor must judge an operation by the response the
    // backend actually sent, never by the request loop's liveness bool.
    std::string lastResponseStatus;
    std::string lastResponseReason;
    std::string lastResponseMessage;

    OutputManager* output = nullptr;
    SourceManager* source = nullptr;

    std::mutex stateMutex;
    std::mutex writerMutex;
    std::condition_variable wake;
    std::thread reader;
    std::atomic<bool> stopReader{false};
    std::atomic<bool> eofSeen{false};

    enum class Phase { WaitingHello, Idle, Running, ShuttingDown, Stopped };
    Phase phase = Phase::WaitingHello;
    bool kernelInitialized = false;
    long long stateRevision = 0;
    long long draftRevision = 0;
    long long lastClientSeq = 0;
    std::string pendingRunRequest;
    int currentRunId = -1;
    bool cancelPending = false;
    bool cancelRequested = false;
    bool eofShutdown = false;
    std::atomic<int> exitCode{0};
    bool fatal = false;
    // Protocol failures latched by the reader thread. They must survive EOF and
    // ordinary cancellation so the final exit code cannot look like a clean end.
    bool protocolFailed = false;
    std::string protocolError;
    bool protocolErrorSent = false;

    struct Command {
        enum class Kind { Hello, Request, Eof, Fatal } kind = Kind::Request;
        SessionJson::Json frame;
        std::string raw;
        std::string error;
        bool arrivedDuringRun = false;
    };
    std::deque<Command> queue;

    struct Cached {
        long long seq = 0;
        std::string bodySha;
        SessionJson::Json response;
    };
    std::map<std::string, Cached> dedup;
    std::deque<std::string> dedupOrder;
    std::set<std::string> expired;
    std::deque<std::string> expiredOrder;
    std::set<std::string> seenFrameIds;

    std::ofstream record;
    std::mutex recordMutex;
    std::mutex dedupMutex;
    bool recordFailed = false;
    std::string recordError;

    Impl(SimulationManager& manager, std::string root, std::string replay)
        : simulation(manager), recordRoot(std::move(root)), replaySource(std::move(replay))
    {
        replayMode = !replaySource.empty();
        output = manager.GetOutputManager();
        source = manager.GetSourceManager();
        outputRoot = std::filesystem::path(manager.GetContext().GetOutputDir()).lexically_normal().string();
    }

    // ---------------------------------------------------------------- record
    // The reader thread and the main thread both append to the session log.
    // All record writes and their failure latching are serialized here.
    void RecordLine(const SessionJson::Json& line)
    {
        std::lock_guard<std::mutex> guard(recordMutex);
        if (!record.is_open() || recordFailed) return;
        record << line.dump() << '\n';
        record.flush();
        if (!record.good()) {
            recordFailed = true;
            recordError = "session record write failed";
            exitCode = 4;
        }
    }

    void MarkRecordFailure(const std::string& message)
    {
        std::lock_guard<std::mutex> guard(recordMutex);
        if (!recordFailed) {
            recordFailed = true;
            recordError = message;
            exitCode.store(4, std::memory_order_relaxed);
        }
    }

    bool RecordFailedSnapshot()
    {
        std::lock_guard<std::mutex> guard(recordMutex);
        return recordFailed;
    }

    void ConsumeNextSeq(long long seq, const std::string& frameId)
    {
        std::lock_guard<std::mutex> guard(stateMutex);
        if (seq == lastClientSeq + 1 && seenFrameIds.count(frameId) == 0) {
            lastClientSeq = seq;
            seenFrameIds.insert(frameId);
        }
    }

    // ---------------------------------------------------------------- dedup cache
    struct CachedLookup {
        bool found = false;
        std::string bodySha;
        SessionJson::Json response;
    };

    CachedLookup LookupCached(const std::string& requestId)
    {
        std::lock_guard<std::mutex> guard(dedupMutex);
        CachedLookup result;
        const auto cached = dedup.find(requestId);
        if (cached == dedup.end()) return result;
        result.found = true;
        result.bodySha = cached->second.bodySha;
        result.response = cached->second.response;
        return result;
    }

    std::optional<SessionJson::Json> CachedForSeq(const std::string& requestId, long long seq)
    {
        std::lock_guard<std::mutex> guard(dedupMutex);
        const auto cached = dedup.find(requestId);
        if (cached == dedup.end() || cached->second.seq != seq) return std::nullopt;
        return cached->second.response;
    }

    bool ExpiredRequest(const std::string& requestId)
    {
        std::lock_guard<std::mutex> guard(dedupMutex);
        return expired.count(requestId) != 0;
    }

    void RememberResponse(const std::string& requestId, long long seq,
                          const std::string& bodySha, SessionJson::Json response)
    {
        std::lock_guard<std::mutex> guard(dedupMutex);
        Cached entry;
        entry.seq = seq;
        entry.bodySha = bodySha;
        entry.response = std::move(response);
        dedup[requestId] = std::move(entry);
        dedupOrder.push_back(requestId);
        while (dedupOrder.size() > kDedupCapacity) {
            const std::string evicted = dedupOrder.front();
            dedupOrder.pop_front();
            dedup.erase(evicted);
            expired.insert(evicted);
            expiredOrder.push_back(evicted);
            while (expiredOrder.size() > kExpiredCapacity) {
                expired.erase(expiredOrder.front());
                expiredOrder.pop_front();
            }
        }
    }

    void NoteDedupSeq(const std::string& requestId, long long seq)
    {
        std::lock_guard<std::mutex> guard(dedupMutex);
        const auto cached = dedup.find(requestId);
        if (cached != dedup.end()) cached->second.seq = seq;
    }

    void RecordFrame(const char* direction, const std::string& text)
    {
        SessionJson::Json entry;
        entry["schema"] = "g4usim-session-log-v1";
        entry["at"] = NowIso8601();
        entry["direction"] = direction;
        if (direction[0] == 'c') {
            entry["text"] = text;
        } else {
            entry["text"] = text;
        }
        RecordLine(entry);
    }

    // ---------------------------------------------------------------- writer
    void Send(const SessionJson::Json& frame)
    {
        if (frame.value("kind", std::string()) == "response") {
            lastResponseStatus = frame.value("status", std::string());
            lastResponseReason = frame.value("reason", std::string());
            lastResponseMessage = frame.value("message", std::string());
        }
        std::string text = SessionJson::Dump(frame);
        if (text.size() > kMaxFrameBytes) text = "{\"kind\":\"error\",\"code\":\"frame_too_large\"}";
        text.push_back('\n');
        std::lock_guard<std::mutex> guard(writerMutex);
        std::fwrite(text.data(), 1, text.size(), stdout);
        std::fflush(stdout);
        RecordFrame("s2c", text.substr(0, text.size() - 1));
    }

    void SendError(const std::string& code, const std::string& message)
    {
        SessionJson::Json frame;
        frame["kind"] = "error";
        frame["code"] = code;
        frame["message"] = message;
        frame["at"] = NowIso8601();
        Send(frame);
    }

    // ---------------------------------------------------------------- reader
    bool ReadChunk(std::string& buffer, bool& eof)
    {
        eof = false;
        char chunk[4096];
#ifdef _WIN32
        const HANDLE handle = GetStdHandle(STD_INPUT_HANDLE);
        if (handle == INVALID_HANDLE_VALUE || handle == nullptr) {
            eof = true;
            return false;
        }
        DWORD available = 0;
        if (!PeekNamedPipe(handle, nullptr, 0, nullptr, &available, nullptr)) {
            const DWORD error = GetLastError();
            if (error == ERROR_BROKEN_PIPE || error == ERROR_PIPE_NOT_CONNECTED) {
                eof = true;
                return false;
            }
            std::this_thread::sleep_for(kReadPoll);
            return false;
        }
        if (available == 0) {
            const DWORD wait = WaitForSingleObject(handle, static_cast<DWORD>(kReadPoll.count()));
            if (wait == WAIT_OBJECT_0) {
                if (!PeekNamedPipe(handle, nullptr, 0, nullptr, &available, nullptr)) {
                    const DWORD error = GetLastError();
                    if (error == ERROR_BROKEN_PIPE || error == ERROR_PIPE_NOT_CONNECTED) {
                        eof = true;
                    }
                    return false;
                }
            }
            if (available == 0) return false;
        }
        DWORD read = 0;
        const DWORD want = static_cast<DWORD>(std::min<std::size_t>(available, sizeof(chunk)));
        if (!ReadFile(handle, chunk, want, &read, nullptr) || read == 0) {
            eof = true;
            return false;
        }
        buffer.append(chunk, read);
        return true;
#else
        struct pollfd descriptor{};
        descriptor.fd = STDIN_FILENO;
        descriptor.events = POLLIN;
        const int ready = poll(&descriptor, 1, static_cast<int>(kReadPoll.count()));
        if (ready == 0) return false;
        if (ready < 0) {
            eof = true;
            return false;
        }
        const ssize_t read = ::read(STDIN_FILENO, chunk, sizeof(chunk));
        if (read <= 0) {
            eof = true;
            return false;
        }
        buffer.append(chunk, static_cast<std::size_t>(read));
        return true;
#endif
    }

    void ReaderLoop()
    {
        std::string buffer;
        while (!stopReader.load(std::memory_order_acquire)) {
            bool eof = false;
            ReadChunk(buffer, eof);
            if (eof) {
                if (!buffer.empty()) {
                    // A short fragment without a terminating newline is still a
                    // protocol violation: do not let EOF silently discard it.
                    std::string leftover = buffer;
                    buffer.clear();
                    const std::string error = "invalid_json: incomplete frame at end of input";
                    LatchReaderProtocolFailure(error, leftover);
                    {
                        std::lock_guard<std::mutex> guard(stateMutex);
                        Command command;
                        command.kind = Command::Kind::Fatal;
                        command.error = error;
                        command.raw = leftover;
                        queue.push_back(std::move(command));
                        wake.notify_all();
                    }
                    eofSeen.store(true);
                    return;
                }
                {
                    std::lock_guard<std::mutex> guard(stateMutex);
                    if (phase == Phase::Running) {
                        eofShutdown = true;
                        if (currentRunId >= 0) {
                            cancelRequested = true;
                            g_cancelRunId.store(currentRunId, std::memory_order_release);
                        } else {
                            cancelPending = true;
                        }
                    }
                    Command command;
                    command.kind = Command::Kind::Eof;
                    queue.push_back(std::move(command));
                    wake.notify_all();
                }
                eofSeen.store(true);
                return;
            }
            while (true) {
                const auto newline = buffer.find('\n');
                if (newline == std::string::npos) break;
                std::string line = buffer.substr(0, newline);
                buffer.erase(0, newline + 1);
                if (!line.empty() && line.back() == '\r') line.pop_back();
                if (line.empty()) continue;
                Command command;
                command.raw = line;
                try {
                    if (line.size() > kMaxFrameBytes) {
                        command.kind = Command::Kind::Fatal;
                        command.error = "frame_too_large";
                    } else {
                        std::string error;
                        SessionJson::Json frame;
                        if (!SessionJson::ParseStrict(line, frame, error)) {
                            command.kind = Command::Kind::Fatal;
                            command.error = "invalid_json: " + error;
                        } else if (!frame.is_object()) {
                            command.kind = Command::Kind::Fatal;
                            command.error = "non_object_root";
                        } else {
                            command.frame = std::move(frame);
                            const std::string kind = command.frame.value("kind", "");
                            command.kind = kind == "hello" ? Command::Kind::Hello : Command::Kind::Request;
                        }
                    }
                } catch (const std::exception& failure) {
                    command.kind = Command::Kind::Fatal;
                    command.error = std::string("invalid_frame: ") + failure.what();
                }
                if (command.kind == Command::Kind::Fatal) {
                    LatchReaderProtocolFailure(command.error, line);
                }
                if (command.kind == Command::Kind::Request &&
                    TryReaderControl(command)) {
                    if (line.size() > kMaxFrameBytes) return;
                    continue;
                }
                {
                    std::lock_guard<std::mutex> guard(stateMutex);
                    command.arrivedDuringRun = phase == Phase::Running;
                    queue.push_back(std::move(command));
                }
                wake.notify_all();
                if (line.size() > kMaxFrameBytes) return;
            }
            if (buffer.size() > kMaxFrameBytes) {
                LatchReaderProtocolFailure("frame_too_large", buffer);
                {
                    std::lock_guard<std::mutex> guard(stateMutex);
                    Command command;
                    command.kind = Command::Kind::Fatal;
                    command.error = "frame_too_large";
                    queue.push_back(std::move(command));
                    wake.notify_all();
                }
                return;
            }
        }
    }

    // ---------------------------------------------------------------- reader control
    // Frames that arrive while BeamOn runs on the main thread must still receive
    // a bounded answer. The reader never touches Geant4: it rejects busy control
    // requests, answers pings and records cancel intent, then the main thread
    // only reports run state changes through the RunAction callbacks.
    bool ValidateReaderFrame(const SessionJson::Json& frame, long long& seq, std::string& frameId,
                             std::string& requestId, std::string& op) const
    {
        if (!frame.is_object()) return false;
        if (!frame.contains("seq") || !frame["seq"].is_number_integer() ||
            !frame.contains("id") || !frame["id"].is_string() ||
            !frame.contains("request_id") || !frame["request_id"].is_string() ||
            !frame.contains("op") || !frame["op"].is_string()) {
            return false;
        }
        seq = frame["seq"].get<long long>();
        frameId = frame["id"].get<std::string>();
        requestId = frame["request_id"].get<std::string>();
        op = frame["op"].get<std::string>();
        return IsHexId(frameId) && IsHexId(requestId);
    }

    SessionJson::Json ReaderResponse(const SessionJson::Json& frame, const std::string& op,
                                     const std::string& status, long long revision, bool duplicate)
    {
        SessionJson::Json response;
        response["kind"] = "response";
        response["seq"] = frame.value("seq", 0LL);
        response["id"] = frame.value("id", "");
        response["request_id"] = frame.value("request_id", "");
        response["op"] = op;
        response["status"] = status;
        response["state_revision"] = revision;
        response["duplicate"] = duplicate;
        response["at"] = NowIso8601();
        return response;
    }

    bool ReaderReject(const SessionJson::Json& frame, const std::string& op,
                      const std::string& reason, const std::string& message)
    {
        long long revision = 0;
        {
            std::lock_guard<std::mutex> guard(stateMutex);
            revision = stateRevision;
        }
        SessionJson::Json response = ReaderResponse(frame, op, "rejected", revision, false);
        response["reason"] = reason;
        response["message"] = message;
        Send(response);
        return true;
    }

    // Control frames that arrive while BeamOn owns the main thread. They share
    // the identity, sequencing, revision, idempotency and target rules with the
    // main request path; only the effect (cancel intent / ping / prompt busy) is
    // reader-local. The reader never calls Geant4.
    // Reader-thread latch for a protocol failure. The reader never calls Geant4:
    // it records the raw input, latches the error and reuses the existing atomic
    // cancel intent so a running BeamOn stops at its next bounded event boundary.
    void LatchReaderProtocolFailure(const std::string& error, const std::string& raw)
    {
        {
            std::lock_guard<std::mutex> guard(stateMutex);
            if (!protocolFailed || protocolError.empty()) {
                protocolFailed = true;
                protocolError = error;
            }
            if (phase == Phase::Running) {
                if (currentRunId >= 0) {
                    cancelRequested = true;
                    g_cancelRunId.store(currentRunId, std::memory_order_release);
                } else {
                    cancelPending = true;
                }
            }
        }
        if (!raw.empty()) {
            std::string text = raw;
            if (text.size() > kMaxFrameBytes) {
                text.resize(kMaxFrameBytes);
                text += "...(input truncated in the record)";
            }
            RecordFrame("c2s", text);
        }
    }

    bool ReadProtocolFailure(std::string& error)
    {
        std::lock_guard<std::mutex> guard(stateMutex);
        if (!protocolFailed) return false;
        error = protocolError;
        return true;
    }

    void ReportProtocolFailure(const std::string& error)
    {
        {
            std::lock_guard<std::mutex> guard(stateMutex);
            if (protocolErrorSent) return;
            protocolErrorSent = true;
        }
        SendError("protocol_error", error);
    }

    bool TryReaderControl(const Command& command)
    {
        const SessionJson::Json& frame = command.frame;
        if (!frame.is_object()) return false;
        long long seq = 0;
        std::string frameId, requestId, op;
        if (!ValidateReaderFrame(frame, seq, frameId, requestId, op)) return false;
        if (op != "ping" && op != "cancel" && op != "run" && op != "set_source" &&
            op != "initialize" && op != "shutdown") {
            return false;
        }

        const SessionJson::Json params = frame.contains("params") && frame["params"].is_object()
                                             ? frame["params"]
                                             : SessionJson::Json::object();
        // The idempotency fingerprint covers the stable request body (op plus
        // params); seq/id are transport identity and may change on a replayed
        // frame, so they are excluded by contract.
        SessionJson::Json bodyFingerprint = SessionJson::Json::object();
        bodyFingerprint["op"] = op;
        bodyFingerprint["params"] = params;
        const std::string bodySha = input_provenance::Sha256(SessionJson::Dump(bodyFingerprint));

        CachedLookup cached = LookupCached(requestId);
        if (cached.found && cached.bodySha != bodySha) {
            ConsumeNextSeq(seq, frameId);
            return ReaderReject(frame, op, "idempotency_conflict",
                                "request_id was already used with a different body");
        }
        if (!cached.found && ExpiredRequest(requestId)) {
            ConsumeNextSeq(seq, frameId);
            return ReaderReject(frame, op, "expired", "request_id left the idempotency window");
        }

        long long revision = 0;
        Phase currentPhase = Phase::Stopped;
        bool exactlyNext = false;
        bool duplicateFrame = false;
        bool replyDuplicate = false;
        bool cancelAccepted = false;
        bool cancelRejected = false;
        std::string cancelReason;
        std::string cancelMessage;
        int acceptedRunId = -1;
        std::string acceptedRunRequest;
        SessionJson::Json ack = SessionJson::Json::object();
        SessionJson::Json busyReply = SessionJson::Json::object();
        {
            std::lock_guard<std::mutex> guard(stateMutex);
            revision = stateRevision;
            currentPhase = phase;
            exactlyNext = seq == lastClientSeq + 1;
            duplicateFrame = seenFrameIds.count(frameId) != 0;
            if (cached.found && exactlyNext) {
                lastClientSeq = seq;
                seenFrameIds.insert(frameId);
                replyDuplicate = true;
                ack = cached.response;
            } else if (exactlyNext && !duplicateFrame && (op == "ping" || op == "cancel")) {
                if (op == "ping" && currentPhase == Phase::Running) {
                    lastClientSeq = seq;
                    seenFrameIds.insert(frameId);
                    ack = ReaderResponse(frame, op, "ok", revision, false);
                    ack["phase"] = "running";
                } else if (op == "cancel" && currentPhase == Phase::Running) {
                    // The reader fast path must apply the same revision identity rule
                    // as the main request path: a cancel without a matching
                    // state_revision is rejected before any cancel intent is set.
                    const auto revisionIt = frame.find("state_revision");
                    if (revisionIt == frame.end() || !revisionIt->is_number_integer()) {
                        lastClientSeq = seq;
                        seenFrameIds.insert(frameId);
                        cancelRejected = true;
                        cancelReason = "invalid_request";
                        cancelMessage = "cancel requests require an integer state_revision";
                    } else if (revisionIt->get<long long>() != revision) {
                        lastClientSeq = seq;
                        seenFrameIds.insert(frameId);
                        cancelRejected = true;
                        cancelReason = "stale_revision";
                        cancelMessage = "state_revision does not match the server state";
                    } else if (params.contains("run_request_id") && !params["run_request_id"].is_string()) {
                        lastClientSeq = seq;
                        seenFrameIds.insert(frameId);
                        cancelRejected = true;
                        cancelReason = "invalid_request";
                        cancelMessage = "params.run_request_id must be a string";
                    } else if (params.contains("run_id") && !params["run_id"].is_number_integer()) {
                        lastClientSeq = seq;
                        seenFrameIds.insert(frameId);
                        cancelRejected = true;
                        cancelReason = "invalid_request";
                        cancelMessage = "params.run_id must be an integer";
                    } else if (params.contains("run_request_id") &&
                               params["run_request_id"].get<std::string>() != pendingRunRequest) {
                        lastClientSeq = seq;
                        seenFrameIds.insert(frameId);
                        cancelRejected = true;
                        cancelReason = "unknown_run";
                        cancelMessage = "run_request_id does not match the active run";
                    } else if (params.contains("run_id") &&
                               params["run_id"].get<long long>() != currentRunId) {
                        lastClientSeq = seq;
                        seenFrameIds.insert(frameId);
                        cancelRejected = true;
                        cancelReason = "unknown_run";
                        cancelMessage = "run_id does not match the active run";
                    } else {
                        lastClientSeq = seq;
                        seenFrameIds.insert(frameId);
                        acceptedRunId = currentRunId;
                        acceptedRunRequest = pendingRunRequest;
                        if (!cancelRequested && !cancelPending) {
                            if (acceptedRunId >= 0) {
                                cancelRequested = true;
                                g_cancelRunId.store(acceptedRunId, std::memory_order_release);
                            } else {
                                cancelPending = true;
                            }
                        }
                        cancelAccepted = true;
                        ack = ReaderResponse(frame, op, "accepted", revision, false);
                        ack["run_request_id"] = acceptedRunRequest;
                        if (acceptedRunId >= 0) ack["run_id"] = acceptedRunId;
                        ack["cancel_mode"] = "soft_abort_at_event_boundary";
                    }
                }
            } else if (exactlyNext && !duplicateFrame && currentPhase == Phase::Running) {
                lastClientSeq = seq;
                seenFrameIds.insert(frameId);
                busyReply = ReaderResponse(frame, op, "rejected", revision, false);
                busyReply["reason"] = "busy";
                busyReply["message"] = "a run is active; send cancel before another control request";
            }
        }

        if (replyDuplicate) {
            ack["duplicate"] = true;
            NoteDedupSeq(requestId, seq);
            RecordFrame("c2s", command.raw);
            Send(ack);
            return true;
        }
        if (cancelRejected) {
            return ReaderReject(frame, op, cancelReason, cancelMessage);
        }
        if (!exactlyNext || duplicateFrame) return false;
        if (op == "ping") {
            if (ack.is_null() || ack.empty()) return false;
            RecordFrame("c2s", command.raw);
            Send(ack);
            return true;
        }
        if (op == "cancel") {
            if (!cancelAccepted) return false;
            RememberResponse(requestId, seq, bodySha, ack);
            RecordFrame("c2s", command.raw);
            Send(ack);
            return true;
        }
        if (currentPhase != Phase::Running) return false;

        // Non-control frame while a run owns the main thread: prompt busy answer.
        if (busyReply.is_null() || busyReply.empty()) return false;
        RememberResponse(requestId, seq, bodySha, busyReply);
        RecordFrame("c2s", command.raw);
        Send(busyReply);
        return true;
    }

    // ---------------------------------------------------------------- helpers
    SessionJson::Json StateJson() const
    {
        SessionJson::Json state;
        state["state_revision"] = stateRevision;
        state["draft_revision"] = draftRevision;
        state["kernel_state"] = kernelInitialized ? "idle" : "pre_init";
        state["phase"] = phase == Phase::Running ? "running" : (phase == Phase::Idle ? "idle" : "starting");
        if (phase == Phase::Running) {
            SessionJson::Json run;
            run["run_request_id"] = pendingRunRequest;
            run["run_id"] = currentRunId >= 0 ? SessionJson::Json(currentRunId) : SessionJson::Json();
            run["cancel_requested"] = cancelRequested || cancelPending || (currentRunId >= 0 && SessionControl::CancelRequested(currentRunId));
            state["current_run"] = std::move(run);
        }
        if (source) {
            const auto snapshot = source->GetSessionSourceSnapshot();
            SessionJson::Json current;
            current["source_count"] = snapshot.sourceCount;
            current["phase_space"] = snapshot.phaseSpace;
            current["advanced"] = snapshot.advanced;
            current["ion"] = snapshot.ion;
            current["preset"] = snapshot.preset;
            current["particle"] = snapshot.particle;
            current["energy_type"] = snapshot.energyType;
            current["mono_energy_MeV"] = snapshot.monoEnergy;
            current["position_type"] = snapshot.positionType;
            current["position_shape"] = snapshot.positionShape;
            current["position_params"] = snapshot.positionParams;
            current["isotropic"] = snapshot.isotropic;
            current["has_direction"] = snapshot.hasDirection;
            current["direction"] = snapshot.direction;
            state["source"] = std::move(current);
        }
        state["output_root"] = outputRoot;
        state["record_root"] = recordRoot;
        state["session_root"] = sessionRoot;
        return state;
    }

    bool Reject(const SessionJson::Json& frame, const std::string& op, const std::string& reason,
                const std::string& message)
    {
        SessionJson::Json response;
        response["kind"] = "response";
        response["seq"] = frame.value("seq", 0LL);
        response["id"] = frame.value("id", "");
        response["request_id"] = frame.value("request_id", "");
        response["op"] = op;
        response["status"] = "rejected";
        response["reason"] = reason;
        response["message"] = message;
        response["state_revision"] = stateRevision;
        response["duplicate"] = false;
        Send(response);
        return true;
    }

    bool Reply(const SessionJson::Json& frame, const std::string& op, const std::string& status,
               SessionJson::Json payload)
    {
        SessionJson::Json response;
        response["kind"] = "response";
        response["seq"] = frame.value("seq", 0LL);
        response["id"] = frame.value("id", "");
        response["request_id"] = frame.value("request_id", "");
        response["op"] = op;
        response["status"] = status;
        response["state_revision"] = stateRevision;
        response["duplicate"] = false;
        for (auto it = payload.begin(); it != payload.end(); ++it) response[it.key()] = it.value();
        Send(response);
        return true;
    }

    // ---------------------------------------------------------------- run hooks
    void HandleRunBeginInternal(int runId, int plannedEvents)
    {
        SessionJson::Json event;
        bool cancelled = false;
        {
            std::lock_guard<std::mutex> guard(stateMutex);
            if (phase != Phase::Running) return;
            currentRunId = runId;
            if (cancelPending) {
                cancelPending = false;
                cancelRequested = true;
                g_cancelRunId.store(runId, std::memory_order_release);
            }
            cancelled = cancelRequested;
            event["kind"] = "event";
            event["event"] = "run_started";
            event["run_request_id"] = pendingRunRequest;
            event["run_id"] = runId;
            event["planned_events"] = plannedEvents;
            event["cancel_requested"] = cancelled;
            event["state_revision"] = stateRevision;
            event["at"] = NowIso8601();
        }
        Send(event);
    }

    void HandleRunEndInternal(int runId, int plannedEvents, int completedEvents,
                              long long abortedEvents, bool outputFailed, OutputManager* manager)
    {
        std::string runRequest;
        bool cancelled = false;
        {
            std::lock_guard<std::mutex> guard(stateMutex);
            if (currentRunId != runId) return;
            runRequest = pendingRunRequest;
            cancelled = cancelRequested || SessionControl::CancelRequested(runId);
        }

        SessionJson::Json artifacts = SessionJson::Json::array();
        std::string receiptStatus = "completed";
        if (cancelled) {
            receiptStatus = "cancelled";
        } else if (abortedEvents > 0) {
            receiptStatus = "aborted";
        } else if (outputFailed) {
            receiptStatus = "failed";
        }
        lastRunStatus = receiptStatus;
        lastRunCompletedEvents = completedEvents;
        lastRunId = runId;
        if (!replayMode && replayCurrentRunStep >= 0 &&
            replayCurrentRunStep < static_cast<int>(replaySteps.size())) {
            SessionJson::Json& step = replaySteps[static_cast<std::size_t>(replayCurrentRunStep)];
            step["status"] = receiptStatus;
            step["completed_events"] = completedEvents;
            step["run_id"] = runId;
            if (receiptStatus != "completed") {
                replayPlanValid = false;
                replayInvalidReason = "the source session has a " + receiptStatus + " run";
            }
            replayCurrentRunStep = -1;
        }

        if (manager) {
            for (const auto& evidence : manager->CollectRunArtifacts(runId)) {
                SessionJson::Json item;
                item["path"] = evidence.path;
                std::error_code relativeError;
                const auto relative = std::filesystem::relative(evidence.path, outputRoot, relativeError);
                item["relative_to_output"] = relativeError ? std::string() : relative.generic_string();
                item["scope"] = ScopeName(evidence.scope);
                item["run_id"] = OptionalInt(evidence.run_id);
                item["thread_id"] = OptionalInt(evidence.thread_id);
                item["sha256"] = OptionalString(evidence.sha256);
                item["size_bytes"] = OptionalUInt(evidence.size_bytes);
                item["integrity_status"] = evidence.integrity_status;
                item["reason"] = evidence.reason;
                artifacts.push_back(std::move(item));
            }
        }

        SessionJson::Json receipt;
        receipt["schema"] = "g4usim_session_run_receipt_v1";
        receipt["session_id"] = sessionId;
        receipt["run_request_id"] = runRequest;
        receipt["run_id"] = runId;
        receipt["planned_events"] = plannedEvents;
        receipt["completed_events"] = completedEvents;
        receipt["aborted_events"] = abortedEvents;
        receipt["status"] = receiptStatus;
        receipt["cancel_requested"] = cancelled;
        receipt["output_failed"] = outputFailed;
        receipt["artifacts"] = artifacts;
        receipt["source"] = StateJson()["source"];

        std::string receiptPath;
        bool wroteReceipt = true;
        {
            const std::filesystem::path path =
                std::filesystem::path(sessionRoot) / ("run-" + PadRun(runId) + ".json");
            std::ofstream file(path, std::ios::binary | std::ios::trunc);
            bool ok = file.is_open();
            if (ok) {
                const std::string text = receipt.dump();
                file.write(text.data(), static_cast<std::streamsize>(text.size()));
                file.put('\n');
                file.flush();
                ok = file.good();
            }
            if (file.is_open()) file.close();
            if (ok && file.fail()) ok = false;
            wroteReceipt = ok;
            if (wroteReceipt) {
                receiptPath = path.generic_string();
            } else {
                MarkRecordFailure("could not write per-run receipt " + path.generic_string());
            }
        }

        SessionJson::Json event;
        event["kind"] = "event";
        event["event"] = "run_finished";
        event["run_request_id"] = runRequest;
        event["run_id"] = runId;
        event["planned_events"] = plannedEvents;
        event["completed_events"] = completedEvents;
        event["aborted_events"] = abortedEvents;
        event["status"] = receiptStatus;
        event["cancel_requested"] = cancelled;
        event["artifacts"] = artifacts;
        event["receipt"] = receipt;
        event["receipt_path"] = wroteReceipt ? SessionJson::Json(receiptPath) : SessionJson::Json();
        event["receipt_integrity"] = wroteReceipt ? "written" : "unavailable";
        event["at"] = NowIso8601();

        {
            std::lock_guard<std::mutex> guard(stateMutex);
            phase = Phase::Idle;
            currentRunId = -1;
            pendingRunRequest.clear();
            cancelRequested = false;
            cancelPending = false;
            g_cancelRunId.store(-1, std::memory_order_release);
            ++stateRevision;
            event["state_revision"] = stateRevision;
        }
        // The terminal event must always be attributable and bounded. A large
        // artifact list is replaced by a receipt reference instead of letting the
        // writer substitute a bare frame_too_large error (repair item E).
        if (SessionJson::Dump(event).size() > kMaxFrameBytes) {
            SessionJson::Json compact;
            compact["kind"] = "event";
            compact["event"] = "run_finished";
            compact["run_request_id"] = runRequest;
            compact["run_id"] = runId;
            compact["planned_events"] = plannedEvents;
            compact["completed_events"] = completedEvents;
            compact["aborted_events"] = abortedEvents;
            compact["status"] = receiptStatus;
            compact["cancel_requested"] = cancelled;
            compact["artifacts_truncated"] = true;
            compact["artifact_count"] = artifacts.size();
            compact["state_revision"] = event.value("state_revision", 0LL);
            compact["at"] = NowIso8601();
            if (wroteReceipt) {
                SessionJson::Json reference;
                reference["path"] = receiptPath;
                reference["schema"] = "g4usim_session_run_receipt_v1";
                const input_provenance::FileDigest digest = input_provenance::HashFile(receiptPath);
                reference["sha256"] = digest.sha256.empty() ? SessionJson::Json()
                                                            : SessionJson::Json(digest.sha256);
                reference["size_bytes"] = digest.size_bytes;
                compact["receipt_ref"] = std::move(reference);
            }
            if (SessionJson::Dump(compact).size() > kMaxFrameBytes) {
                SessionJson::Json minimal;
                minimal["kind"] = "event";
                minimal["event"] = "run_finished";
                minimal["run_id"] = runId;
                minimal["status"] = receiptStatus;
                minimal["error"] = "run_finished_frame_exceeded";
                minimal["artifact_count"] = artifacts.size();
                MarkRecordFailure("run_finished terminal event exceeded the protocol frame limit");
                Send(minimal);
                return;
            }
            Send(compact);
            return;
        }
        Send(event);
    }

    // ---------------------------------------------------------------- ops
    // apply=false parses and validates every field without touching the SourceManager;
    // replay uses it to validate the whole plan before the first BeamOn.
    bool ApplySourceEdit(const SessionJson::Json& params, std::string& reason, std::string& message,
                         SessionJson::Json& resolved, bool apply = true)
    {
        if (!source) {
            reason = "source_unavailable";
            message = "the backend has no source manager";
            return false;
        }
        if (!source->CanAcceptSessionEdit(reason)) {
            message = "the current source configuration is not editable through the session";
            return false;
        }
        if (!params.is_object()) {
            reason = "invalid_params";
            message = "params must be an object";
            return false;
        }
        const std::string field = params.value("field", "");
        if (field == "particle") {
            const std::string value = params.value("value", "");
            if (!value.empty() && value.size() <= SessionJson::kMaxStringBytes) {
                if (apply) {
                    source->SetParticle(value);
                } else {
                    G4ParticleTable* table = G4ParticleTable::GetParticleTable();
                    if (table == nullptr || table->FindParticle(value) == nullptr) {
                        reason = "invalid_value";
                        message = "particle '" + value + "' is not in the Geant4 particle table";
                        return false;
                    }
                }
            } else {
                reason = "invalid_value"; message = "particle requires a non-empty name"; return false;
            }
        } else if (field == "energy") {
            const auto it = params.find("value");
            if (it == params.end() || !it->is_string()) {
                reason = "invalid_value"; message = "energy requires a string with a unit, e.g. \"100 MeV\""; return false;
            }
            try {
                const double energy = UnitParser::ParseEnergy(it->get<std::string>());
                // Keep the setter's numeric domain even in read-only validation.
                if (!std::isfinite(energy) || energy <= 0.0) {
                    reason = "invalid_value";
                    message = "energy must be finite and greater than zero";
                    return false;
                }
                if (apply) source->SetMonoEnergy(energy);
            } catch (const std::exception& error) {
                reason = "invalid_value"; message = error.what(); return false;
            }
        } else if (field == "position") {
            const auto it = params.find("value");
            if (it == params.end() || !it->is_string()) {
                reason = "invalid_value"; message = "position requires \"x y z unit\""; return false;
            }
            std::array<double, 3> position{};
            if (!ParseLengthVector(it->get<std::string>(), position)) {
                reason = "invalid_value"; message = "position requires \"x y z unit\""; return false;
            }
            if (apply) source->SetPointPosition(position[0], position[1], position[2]);
        } else if (field == "direction") {
            const auto it = params.find("value");
            if (it == params.end() || !it->is_string()) {
                reason = "invalid_value"; message = "direction requires \"dx dy dz\" or a +x/-x token"; return false;
            }
            std::array<double, 3> direction{};
            if (!ParseDirectionTriple(it->get<std::string>(), direction)) {
                reason = "invalid_value"; message = "direction requires three finite non-zero components"; return false;
            }
            if (apply) source->SetDirection(direction[0], direction[1], direction[2]);
        } else if (field == "plane_beam") {
            const std::string radiusText = params.value("radius", "");
            const std::string centerText = params.value("center", "0 0 0 mm");
            const std::string directionText = params.value("direction", "-z");
            std::array<double, 3> center{};
            std::array<double, 3> direction{};
            if (radiusText.empty() || !ParseLengthVector(centerText, center) ||
                !ParseDirectionTriple(directionText, direction)) {
                reason = "invalid_value";
                message = "plane_beam requires radius \"5 mm\", optional center \"x y z unit\" and direction";
                return false;
            }
            try {
                const double radius = UnitParser::ParseLength(radiusText);
                if (!std::isfinite(radius) || radius <= 0.0) {
                    reason = "invalid_value";
                    message = "plane_beam radius must be finite and greater than zero";
                    return false;
                }
                if (apply) source->SetPlaneBeamAt(radius, center[0], center[1], center[2], directionText);
            } catch (const std::exception& error) {
                reason = "invalid_value"; message = error.what(); return false;
            }
        } else {
            reason = "unknown_field";
            message = "allowed fields: particle, energy, position, direction, plane_beam";
            return false;
        }
        const auto snapshot = source->GetSessionSourceSnapshot();
        resolved["source_count"] = snapshot.sourceCount;
        resolved["phase_space"] = snapshot.phaseSpace;
        resolved["advanced"] = snapshot.advanced;
        resolved["ion"] = snapshot.ion;
        resolved["preset"] = snapshot.preset;
        resolved["particle"] = snapshot.particle;
        resolved["energy_type"] = snapshot.energyType;
        resolved["mono_energy_MeV"] = snapshot.monoEnergy;
        resolved["position_type"] = snapshot.positionType;
        resolved["position_shape"] = snapshot.positionShape;
        resolved["position_params"] = snapshot.positionParams;
        resolved["isotropic"] = snapshot.isotropic;
        resolved["has_direction"] = snapshot.hasDirection;
        resolved["direction"] = snapshot.direction;
        resolved["field"] = field;
        return true;
    }

    bool ProcessRequest(const Command& command)
    {
        const SessionJson::Json& frame = command.frame;
        if (!frame.is_object()) {
            SendError("invalid_request", "request must be a JSON object");
            exitCode = 3;
            return false;
        }
        if (phase == Phase::WaitingHello) {
            SendError("handshake_required", "send a hello frame before any request");
            exitCode = 3;
            return false;
        }
        const auto seqIt = frame.find("seq");
        const auto idIt = frame.find("id");
        const auto requestIdIt = frame.find("request_id");
        const auto opIt = frame.find("op");
        if (seqIt == frame.end() || !seqIt->is_number_integer() || idIt == frame.end() ||
            !idIt->is_string() || requestIdIt == frame.end() || !requestIdIt->is_string() ||
            opIt == frame.end() || !opIt->is_string()) {
            SendError("invalid_request", "seq, id, request_id and op are required");
            exitCode = 3;
            return false;
        }
        const long long seq = seqIt->get<long long>();
        const std::string frameId = idIt->get<std::string>();
        const std::string requestId = requestIdIt->get<std::string>();
        const std::string op = opIt->get<std::string>();
        if (!IsHexId(frameId) || !IsHexId(requestId)) {
            SendError("invalid_request", "id and request_id must be 1-64 hex characters");
            exitCode = 3;
            return false;
        }
        SessionJson::Json duplicateResponse;
        bool duplicateSeen = false;
        std::string orderingError;
        std::string orderingMessage;
        {
            std::lock_guard<std::mutex> guard(stateMutex);
            if (seq <= lastClientSeq) {
                std::lock_guard<std::mutex> cacheGuard(dedupMutex);
                const auto cached = dedup.find(requestId);
                if (cached != dedup.end() && cached->second.seq == seq) {
                    duplicateResponse = cached->second.response;
                    duplicateSeen = true;
                } else {
                    orderingError = "out_of_order";
                    orderingMessage = "seq must strictly increase";
                }
            } else if (seenFrameIds.count(frameId) != 0) {
                orderingError = "duplicate_frame_id";
                orderingMessage = "frame id was already used in this session";
            } else if (seq != lastClientSeq + 1) {
                orderingError = "out_of_order";
                orderingMessage = "seq must increase by exactly one";
            } else {
                lastClientSeq = seq;
                seenFrameIds.insert(frameId);
            }
        }
        if (duplicateSeen) {
            duplicateResponse["duplicate"] = true;
            Send(duplicateResponse);
            return true;
        }
        if (!orderingError.empty()) {
            SendError(orderingError, orderingMessage);
            exitCode = 3;
            return false;
        }

        const SessionJson::Json params = frame.contains("params") && frame["params"].is_object()
                                             ? frame["params"]
                                             : SessionJson::Json::object();
        // The idempotency fingerprint covers the stable request body (op plus
        // params); seq/id are transport identity and may change on a replayed
        // frame, so they are excluded by contract.
        SessionJson::Json bodyFingerprint = SessionJson::Json::object();
        bodyFingerprint["op"] = op;
        bodyFingerprint["params"] = params;
        const std::string bodySha = input_provenance::Sha256(SessionJson::Dump(bodyFingerprint));

        const CachedLookup cached = LookupCached(requestId);
        if (cached.found) {
            if (cached.bodySha != bodySha) {
                return Reject(frame, op, "idempotency_conflict",
                              "request_id was already used with a different body");
            }
            SessionJson::Json response = cached.response;
            response["duplicate"] = true;
            Send(response);
            return true;
        }
        if (ExpiredRequest(requestId)) {
            return Reject(frame, op, "expired", "request_id left the idempotency window");
        }

        if (command.arrivedDuringRun && (op == "run" || op == "set_source")) {
            return Reject(frame, op, "busy", "the request arrived while a run was active");
        }

        const auto revisionIt = frame.find("state_revision");
        const bool mutating = op != "get_state";
        if (mutating && (revisionIt == frame.end() || !revisionIt->is_number_integer())) {
            return Reject(frame, op, "invalid_request", "mutating requests require state_revision");
        }
        if (mutating && revisionIt->get<long long>() != stateRevision) {
            return Reject(frame, op, "stale_revision", "state_revision does not match the server state");
        }

        auto remember = [&](SessionJson::Json response) {
            RememberResponse(requestId, seq, bodySha, std::move(response));
        };

        if (op == "get_state") {
            SessionJson::Json payload;
            payload["state"] = StateJson();
            payload["evidence_level"] = "manager_readback";
            SessionJson::Json response;
            response["kind"] = "response";
            response["seq"] = seq;
            response["id"] = frameId;
            response["request_id"] = requestId;
            response["op"] = op;
            response["status"] = "ok";
            response["state_revision"] = stateRevision;
            response["duplicate"] = false;
            for (auto it = payload.begin(); it != payload.end(); ++it) response[it.key()] = it.value();
            remember(response);
            Send(response);
            return true;
        }

        if (op == "shutdown") {
            {
                std::lock_guard<std::mutex> guard(stateMutex);
                if (phase == Phase::Running) return Reject(frame, op, "busy", "a run is in progress");
                phase = Phase::ShuttingDown;
            }
            SessionJson::Json payload;
            payload["session_id"] = sessionId;
            SessionJson::Json response;
            response["kind"] = "response";
            response["seq"] = seq;
            response["id"] = frameId;
            response["request_id"] = requestId;
            response["op"] = op;
            response["status"] = "accepted";
            response["state_revision"] = stateRevision;
            response["duplicate"] = false;
            for (auto it = payload.begin(); it != payload.end(); ++it) response[it.key()] = it.value();
            remember(response);
            Send(response);
            SessionJson::Json closing;
            closing["kind"] = "event";
            closing["event"] = "closing";
            closing["reason"] = "shutdown_requested";
            closing["exit_code"] = exitCode.load(std::memory_order_relaxed);
            closing["session_id"] = sessionId;
            closing["at"] = NowIso8601();
            closing["state_revision"] = stateRevision;
            Send(closing);
            return false;
        }

        if (op == "initialize") {
            if (kernelInitialized) return Reject(frame, op, "already_initialized", "the kernel is already initialized");
            const int status = G4UImanager::GetUIpointer()->ApplyCommand("/run/initialize");
            if (status != 0) {
                {
                    std::lock_guard<std::mutex> guard(stateMutex);
                    exitCode = 2;
                    phase = Phase::ShuttingDown;
                }
                return Reject(frame, op, "kernel_init_failed", "Geant4 /run/initialize returned a non-zero status");
            }
            {
                std::lock_guard<std::mutex> guard(stateMutex);
                kernelInitialized = true;
                ++stateRevision;
            }
            replayPreRunProvenance = ProvenanceIdentity();
            SessionJson::Json payload;
            payload["kernel_state"] = "idle";
            payload["evidence_level"] = "kernel_initialized";
            SessionJson::Json response;
            response["kind"] = "response";
            response["seq"] = seq;
            response["id"] = frameId;
            response["request_id"] = requestId;
            response["op"] = op;
            response["status"] = "applied";
            response["state_revision"] = stateRevision;
            response["duplicate"] = false;
            for (auto it = payload.begin(); it != payload.end(); ++it) response[it.key()] = it.value();
            remember(response);
            Send(response);
            return true;
        }

        if (op == "set_source") {
            if (phase == Phase::Running) return Reject(frame, op, "busy", "source edits are not allowed while a run is active");
            SessionJson::Json resolved = SessionJson::Json::object();
            std::string reason;
            std::string message;
            if (!ApplySourceEdit(params, reason, message, resolved)) {
                return Reject(frame, op, reason, message);
            }
            {
                std::lock_guard<std::mutex> guard(stateMutex);
                ++stateRevision;
                ++draftRevision;
            }
            SessionJson::Json payload;
            payload["requested"] = params;
            payload["resolved"] = resolved;
            payload["application_status"] = "configured";
            payload["evidence_level"] = "unknown";
            payload["kernel_evidence"] = "not_observed";
            payload["status_detail"] =
                "accepted by the source manager; kernel consumption is checked per run";
            SessionJson::Json response;
            response["kind"] = "response";
            response["seq"] = seq;
            response["id"] = frameId;
            response["request_id"] = requestId;
            response["op"] = op;
            response["status"] = "accepted";
            response["state_revision"] = stateRevision;
            response["duplicate"] = false;
            for (auto it = payload.begin(); it != payload.end(); ++it) response[it.key()] = it.value();
            remember(response);
            Send(response);
            if (!replayMode) {
                SessionJson::Json step;
                step["op"] = "set_source";
                step["params"] = params;
                replaySteps.push_back(std::move(step));
            }
            return true;
        }

        if (op == "run") {
            if (phase == Phase::Running) return Reject(frame, op, "busy", "a run is already in progress");
            if (!kernelInitialized) return Reject(frame, op, "kernel_not_initialized", "send initialize before run");
            const auto eventsIt = params.find("events");
            if (eventsIt == params.end() || !eventsIt->is_number_integer()) {
                return Reject(frame, op, "invalid_params", "run requires params.events as an integer");
            }
            const long long events = eventsIt->get<long long>();
            if (events <= 0 || events > kMaxSessionEvents) {
                return Reject(frame, op, "invalid_params", "events must be in 1..100000000");
            }
            // Run prerequisites that depend on the constructed kernel must be
            // validated before accepted/started/replay registration and before
            // BeamOn: a rejected run must not create a run receipt or process a
            // single event. The validation records its failure stage itself.
            try {
                simulation.ValidateScoringVolumeConfigsBeforeRun();
            } catch (const std::exception& error) {
                Reject(frame, op, "scoring_config_invalid", error.what());
                {
                    std::lock_guard<std::mutex> guard(stateMutex);
                    exitCode = 2;
                    phase = Phase::ShuttingDown;
                }
                return false;
            }
            {
                std::lock_guard<std::mutex> guard(stateMutex);
                phase = Phase::Running;
                pendingRunRequest = requestId;
                currentRunId = -1;
                cancelPending = false;
                cancelRequested = false;
            }
            if (!replayMode) {
                SessionJson::Json step;
                step["op"] = "run";
                step["params"]["events"] = events;
                step["run_request_id"] = requestId;
                step["status"] = "pending";
                replaySteps.push_back(std::move(step));
                replayCurrentRunStep = static_cast<int>(replaySteps.size()) - 1;
            }
            SessionJson::Json payload;
            payload["run_request_id"] = requestId;
            payload["planned_events"] = events;
            payload["kernel_state"] = "running";
            SessionJson::Json response;
            response["kind"] = "response";
            response["seq"] = seq;
            response["id"] = frameId;
            response["request_id"] = requestId;
            response["op"] = op;
            response["status"] = "accepted";
            response["state_revision"] = stateRevision;
            response["duplicate"] = false;
            for (auto it = payload.begin(); it != payload.end(); ++it) response[it.key()] = it.value();
            remember(response);
            Send(response);

            if (!replayMode) EnsureReplayDataIdentity();
            G4RunManager* runManager = G4RunManager::GetRunManager();
            if (runManager == nullptr) {
                SendError("run_manager_unavailable", "G4RunManager is not available");
                exitCode = 2;
                return false;
            }
            try {
                runManager->BeamOn(static_cast<int>(events));
            } catch (const std::exception& error) {
                {
                    std::lock_guard<std::mutex> guard(stateMutex);
                    exitCode = 2;
                }
                SendError("run_failed", error.what());
                return false;
            }
            {
                std::lock_guard<std::mutex> guard(stateMutex);
                if (phase == Phase::Running) {
                    // BeamOn returned without a RunAction::EndOfRunAction callback.
                    phase = Phase::Idle;
                    currentRunId = -1;
                    pendingRunRequest.clear();
                    cancelRequested = false;
                    cancelPending = false;
                    g_cancelRunId.store(-1, std::memory_order_release);
                    ++stateRevision;
                    SendError("run_unfinished", "the run ended without a per-run receipt");
                    exitCode = 2;
                }
            }
            {
                std::string protocolErrorText;
                if (ReadProtocolFailure(protocolErrorText)) {
                    ReportProtocolFailure(protocolErrorText);
                    std::lock_guard<std::mutex> guard(stateMutex);
                    exitCode = 3;
                    return false;
                }
            }
            if (eofShutdown) return false;
            return exitCode == 0;
        }

        if (op == "cancel") {
            bool running = false;
            int runId = -1;
            std::string pending;
            {
                std::lock_guard<std::mutex> guard(stateMutex);
                running = phase == Phase::Running;
                runId = currentRunId;
                pending = pendingRunRequest;
            }
            if (!running) return Reject(frame, op, "not_running", "no run is active");
            const auto runRequestIt = params.find("run_request_id");
            if (runRequestIt != params.end() && runRequestIt->is_string() &&
                runRequestIt->get<std::string>() != pending) {
                return Reject(frame, op, "unknown_run", "run_request_id does not match the active run");
            }
            {
                std::lock_guard<std::mutex> guard(stateMutex);
                if (cancelRequested || cancelPending) {
                    // Already requested: acknowledge idempotently.
                } else if (runId >= 0) {
                    cancelRequested = true;
                    g_cancelRunId.store(runId, std::memory_order_release);
                } else {
                    cancelPending = true;
                }
            }
            if (!replayMode) {
                replayPlanValid = false;
                replayInvalidReason = "the source session cancelled a run";
            }
            SessionJson::Json payload;
            payload["run_request_id"] = pending;
            payload["run_id"] = runId >= 0 ? SessionJson::Json(runId) : SessionJson::Json();
            payload["cancel_mode"] = "soft_abort_at_event_boundary";
            SessionJson::Json response;
            response["kind"] = "response";
            response["seq"] = seq;
            response["id"] = frameId;
            response["request_id"] = requestId;
            response["op"] = op;
            response["status"] = "accepted";
            response["state_revision"] = stateRevision;
            response["duplicate"] = false;
            for (auto it = payload.begin(); it != payload.end(); ++it) response[it.key()] = it.value();
            remember(response);
            Send(response);
            return true;
        }

        return Reject(frame, op, "unknown_op",
                      "supported ops: initialize, set_source, run, cancel, get_state, shutdown");
    }

    bool ProcessHello(const Command& command)
    {
        if (phase != Phase::WaitingHello) {
            SendError("duplicate_hello", "hello was already accepted");
            exitCode = 3;
            return false;
        }
        const SessionJson::Json& frame = command.frame;
        const std::string protocol = frame.value("protocol", "");
        if (protocol != kProtocol) {
            SendError("unsupported_protocol", "expected protocol " + std::string(kProtocol));
            exitCode = 3;
            return false;
        }
        {
            std::lock_guard<std::mutex> guard(stateMutex);
            phase = Phase::Idle;
            helloSeen = true;
        }
        SessionJson::Json welcome;
        welcome["kind"] = "welcome";
        welcome["protocol"] = kProtocol;
        welcome["session_id"] = sessionId;
        welcome["at"] = NowIso8601();
        SessionJson::Json backend;
        backend["source_fingerprint"] = G4USIM_SOURCE_FINGERPRINT;
        backend["build_git_commit"] = G4USIM_GIT_COMMIT;
        backend["compiler_id"] = G4USIM_COMPILER_ID;
        welcome["backend"] = std::move(backend);
        welcome["limits"]["max_frame_bytes"] = kMaxFrameBytes;
        welcome["limits"]["max_events_per_run"] = kMaxSessionEvents;
        welcome["state"] = StateJson();
        if (replayMode) welcome["replay"] = replayInfo;
        Send(welcome);
        return true;
    }


    // ---------------------------------------------------------------- replay
    // Capture/validate/repeat the complete controlled-session state. The engine
    // state is captured from CLHEP before any client request and restored before
    // `/run/initialize`; the read-back bytes must match the snapshot exactly.

    bool BuildDataIdentity(SessionJson::Json& data, std::string& errorText)
    {
        errorText.clear();
        struct DatasetFiles {
            std::string env;
            std::string folder;
            std::string resolved;
            bool required = false;
            bool available = false;
            std::vector<std::pair<std::string, std::string>> files;
        };
        std::vector<DatasetFiles> datasets;
        std::vector<std::string> allFiles;
        for (const auto& status : Geant4DataLocator::CheckDatasets()) {
            DatasetFiles item;
            item.env = status.env;
            item.folder = status.folder;
            item.required = status.required;
            item.resolved = status.path;
            if (status.path.empty()) {
                if (status.required) {
                    errorText = "a required Geant4 dataset is missing: " + status.env;
                    return false;
                }
                datasets.push_back(std::move(item));
                continue;
            }
            std::error_code error;
            const std::filesystem::path root(status.path);
            if (!std::filesystem::is_directory(root, error) || error) {
                errorText = "Geant4 dataset directory is missing or unreadable: " + status.path;
                return false;
            }
            item.available = true;
            std::filesystem::recursive_directory_iterator iterator(root, error);
            if (error) {
                errorText = "could not enumerate Geant4 dataset " + status.path + ": " +
                            error.message();
                return false;
            }
            const std::filesystem::recursive_directory_iterator end;
            while (iterator != end) {
                const std::filesystem::path path = iterator->path();
                std::error_code statusError;
                const std::filesystem::file_status entryStatus =
                    iterator->symlink_status(statusError);
                if (statusError) {
                    errorText = "could not stat Geant4 dataset entry " + path.generic_string() +
                                ": " + statusError.message();
                    return false;
                }
                if (std::filesystem::is_symlink(entryStatus)) {
                    errorText = "Geant4 dataset contains an unsupported symbolic link: " +
                                path.generic_string();
                    return false;
                }
                if (std::filesystem::is_regular_file(entryStatus)) {
                    std::error_code relativeError;
                    const std::filesystem::path relative =
                        std::filesystem::relative(path, root, relativeError);
                    if (relativeError) {
                        errorText = "could not resolve Geant4 dataset entry " +
                                    path.generic_string();
                        return false;
                    }
                    item.files.emplace_back(relative.generic_string(), path.string());
                }
                iterator.increment(error);
                if (error) {
                    errorText = "Geant4 dataset enumeration failed under " + status.path +
                                ": " + error.message();
                    return false;
                }
            }
            std::sort(item.files.begin(), item.files.end());
            for (const auto& file : item.files) allFiles.push_back(file.second);
            datasets.push_back(std::move(item));
        }
        std::vector<input_provenance::FileDigest> digests;
        std::string hashError;
        if (!HashFilesParallel(allFiles, digests, hashError)) {
            errorText = hashError;
            return false;
        }
        SessionJson::Json entries = SessionJson::Json::array();
        std::string digest;
        std::size_t fileIndex = 0;
        for (const auto& item : datasets) {
            SessionJson::Json entry;
            entry["env"] = item.env;
            entry["folder"] = item.folder;
            entry["required"] = item.required;
            entry["available"] = item.available;
            entry["path"] = item.resolved.empty() ? SessionJson::Json()
                                                  : SessionJson::Json(item.resolved);
            if (!item.available) {
                entry["manifest_sha256"] = SessionJson::Json();
                entry["file_count"] = 0;
            } else {
                std::string joined;
                for (const auto& file : item.files) {
                    std::error_code sizeError;
                    const auto size = std::filesystem::file_size(file.second, sizeError);
                    const input_provenance::FileDigest& digestEntry = digests[fileIndex];
                    if (sizeError || digestEntry.sha256.empty() ||
                        digestEntry.size_bytes != static_cast<std::uint64_t>(size)) {
                        errorText = "could not read the complete Geant4 dataset file " +
                                    file.second;
                        return false;
                    }
                    joined += file.first + "|" + std::to_string(size) + "|" +
                              digestEntry.sha256 + "\n";
                    ++fileIndex;
                }
                entry["manifest_sha256"] = input_provenance::Sha256(joined);
                entry["file_count"] = static_cast<long long>(item.files.size());
            }
            entries.push_back(entry);
            digest += item.env;
            digest.push_back('\x1f');
            digest += item.folder;
            digest.push_back('\x1f');
            digest += entry.value("manifest_sha256", std::string());
            digest.push_back('\n');
        }
        data["datasets"] = entries;
        data["digest"] = input_provenance::Sha256(digest);
        return true;
    }

    SessionJson::Json ProvenanceIdentity()
    {
        std::vector<std::string> lines;
        SessionJson::Json observations = SessionJson::Json::array();
        for (const auto& item : input_provenance::Snapshot()) {
            // The F1 ledger writes "recorded" for bytes actually read; keep it
            // aligned with src/Config/InputProvenance.cc RecordRead instead of
            // filtering the whole ledger away.
            if (item.status != "recorded" && item.status != "observed") continue;
            const std::string path = ReplayNormalizePath(item.path);
            SessionJson::Json entry;
            entry["path"] = path;
            entry["kind"] = item.kind;
            entry["role"] = item.role;
            entry["capture_method"] = item.capture_method;
            if (item.sha256) entry["sha256"] = *item.sha256;
            if (item.size_bytes) entry["size_bytes"] = *item.size_bytes;
            observations.push_back(entry);
            lines.push_back(path + "|" + item.kind + "|" + item.role + "|" +
                             (item.sha256 ? *item.sha256 : std::string()) + "|" +
                             (item.size_bytes ? std::to_string(*item.size_bytes) : std::string()) +
                             "\n");
        }
        std::sort(lines.begin(), lines.end());
        std::string joined;
        joined.reserve(lines.size() * 64);
        for (const std::string& line : lines) joined += line;
        SessionJson::Json provenance;
        provenance["count"] = static_cast<long long>(lines.size());
        provenance["digest"] = input_provenance::Sha256(joined);
        provenance["observations"] = observations;
        return provenance;
    }

    SessionJson::Json InputIdentity(const std::string& path)
    {
        std::error_code error;
        if (path.empty()) return SessionJson::Json();
        SessionJson::Json entry;
        entry["path"] = ReplayNormalizePath(path);
        if (!std::filesystem::is_regular_file(path, error) || error) {
            entry["missing"] = true;
            return entry;
        }
        const input_provenance::FileDigest digest = input_provenance::HashFile(path);
        entry["sha256"] = digest.sha256;
        entry["size_bytes"] = digest.size_bytes;
        return entry;
    }

    static std::string CompareInputIdentities(const SessionJson::Json& expected,
                                              const SessionJson::Json& current)
    {
        if (!expected.is_object() || !current.is_object()) {
            return "the replay snapshot does not describe the session inputs";
        }
        for (auto it = expected.begin(); it != expected.end(); ++it) {
            const std::string slot = it.key();
            if (!current.contains(slot) || !current[slot].is_object()) {
                return "the replay process does not configure input slot '" + slot + "'";
            }
            const SessionJson::Json& want = it.value();
            const SessionJson::Json& have = current[slot];
            if (want.value("missing", false) != have.value("missing", false)) {
                return "input slot '" + slot + "' presence differs from the source session";
            }
            if (want.value("missing", false)) continue;
            if (want.value("path", std::string()) != have.value("path", std::string())) {
                return "input slot '" + slot + "' points at a different file than the source session";
            }
            if (want.value("sha256", std::string()) != have.value("sha256", std::string()) ||
                want.value("size_bytes", 0) != have.value("size_bytes", 0)) {
                return "input slot '" + slot + "' has different bytes than the source session";
            }
        }
        return {};
    }

    SessionJson::Json CurrentInputIdentity()
    {
        const auto& context = simulation.GetContext();
        SessionJson::Json inputs;
        inputs["main_config"] = InputIdentity(context.GetMainConfig());
        inputs["materials_config"] = InputIdentity(simulation.GetMaterialsConfigFile());
        const GeometryManager* geometry = simulation.GetGeometryManager();
        inputs["geometry_config"] =
            InputIdentity(geometry != nullptr ? geometry->GetGeometryConfigFile() : std::string());
        return inputs;
    }

    void RecordReplayMeta(const std::string& event, const SessionJson::Json& extra = SessionJson::Json())
    {
        SessionJson::Json line;
        line["schema"] = "g4usim-session-log-v1";
        line["at"] = NowIso8601();
        line["direction"] = "meta";
        line["event"] = event;
        line["session_id"] = sessionId;
        if (extra.is_object()) {
            for (auto it = extra.begin(); it != extra.end(); ++it) line[it.key()] = it.value();
        }
        RecordLine(line);
    }

    bool CaptureReplaySnapshot()
    {
        const std::filesystem::path sessionDir(sessionRoot);
        SessionJson::Json snapshot;
        snapshot["schema"] = "g4usim_session_replay_v1";
        snapshot["version"] = 1;
        snapshot["session_id"] = sessionId;
        snapshot["created_at"] = NowIso8601();
        SessionJson::Json backend;
        backend["source_fingerprint"] = G4USIM_SOURCE_FINGERPRINT;
        backend["build_git_commit"] = G4USIM_GIT_COMMIT;
        backend["compiler_id"] = G4USIM_COMPILER_ID;
        backend["geant4_version"] = std::string(G4Version);
        snapshot["backend"] = backend;
        const auto& context = simulation.GetContext();
        snapshot["threads"] = context.GetNumThreads();
        snapshot["seed"]["has_seed"] = context.HasSeed();
        if (context.HasSeed()) snapshot["seed"]["value"] = context.GetSeed();
        snapshot["inputs"] = CurrentInputIdentity();
        snapshot["output_root"] = outputRoot;
        snapshot["provenance"] = ProvenanceIdentity();
        if (snapshot["provenance"].value("count", 0) <= 0) {
            replayPlanValid = false;
            replayInvalidReason = "the session did not record the input bytes it consumed";
            MarkRecordFailure(replayInvalidReason);
            return false;
        }

        const std::filesystem::path rngPath = sessionDir / "rng-start.conf";
        CLHEP::HepRandom::saveEngineStatus(rngPath.string().c_str());
        std::string rngText;
        std::error_code removeError;
        if (!ReplayReadText(rngPath, rngText) || rngText.empty()) {
            replayPlanValid = false;
            replayInvalidReason = "could not capture the CLHEP random engine state";
            MarkRecordFailure(replayInvalidReason);
            return false;
        }
        std::filesystem::remove(rngPath, removeError);
        snapshot["rng"]["status_text"] = rngText;
        snapshot["rng"]["sha256"] = input_provenance::Sha256(rngText);

        if (!ReplayWriteText(sessionDir / "replay-snapshot.json", snapshot.dump() + "\n")) {
            replayPlanValid = false;
            replayInvalidReason = "could not write replay-snapshot.json";
            MarkRecordFailure(replayInvalidReason);
            return false;
        }
        replaySnapshot = std::move(snapshot);
        replaySnapshotReady = true;
        RecordReplayMeta("replay_snapshot_written");
        return true;
    }

    bool ReplayRefuse(const std::string& reason)
    {
        replayInvalidReason = reason;
        replayPrepared = false;
        MarkRecordFailure(reason);
        return false;
    }

    bool ValidateReplayPlan(const SessionJson::Json& steps, std::string& error)
    {
        if (!steps.is_array()) {
            error = "the recorded steps are not an array";
            return false;
        }
        if (steps.empty()) {
            error = "the session recorded no steps";
            return false;
        }
        if (steps.size() > 10000) {
            error = "the recorded step plan is too large";
            return false;
        }
        bool sawRun = false;
        for (std::size_t index = 0; index < steps.size(); ++index) {
            const SessionJson::Json& step = steps[index];
            const std::string prefix = "step " + std::to_string(index);
            if (!step.is_object()) {
                error = prefix + " is not an object";
                return false;
            }
            const auto opIt = step.find("op");
            if (opIt == step.end() || !opIt->is_string()) {
                error = prefix + " has no op";
                return false;
            }
            const std::string op = opIt->get<std::string>();
            const auto paramsIt = step.find("params");
            if (paramsIt == step.end() || !paramsIt->is_object()) {
                error = prefix + " has no params object";
                return false;
            }
            if (op == "set_source") {
                const auto fieldIt = paramsIt->find("field");
                if (fieldIt == paramsIt->end() || !fieldIt->is_string()) {
                    error = prefix + " has an invalid set_source request";
                    return false;
                }
                const std::string field = fieldIt->get<std::string>();
                if (field != "particle" && field != "energy" && field != "position" &&
                    field != "direction" && field != "plane_beam") {
                    error = prefix + " edits an unsupported source field";
                    return false;
                }
                // plane_beam carries a radius instead of a scalar value string;
                // numeric domains are checked by the read-only semantic pass.
                const char* valueKey = field == "plane_beam" ? "radius" : "value";
                const auto valueIt = paramsIt->find(valueKey);
                if (valueIt == paramsIt->end() || !valueIt->is_string()) {
                    error = prefix + " has an invalid source value";
                    return false;
                }
                const std::string value = valueIt->get<std::string>();
                if (value.empty() || value.size() > 4096) {
                    error = prefix + " has an invalid source value";
                    return false;
                }
            } else if (op == "run") {
                sawRun = true;
                if (paramsIt->size() != 1) {
                    error = prefix + " has unexpected run parameters";
                    return false;
                }
                const auto eventsIt = paramsIt->find("events");
                if (eventsIt == paramsIt->end() || !eventsIt->is_number_integer()) {
                    error = prefix + " has no integer events value";
                    return false;
                }
                const long long events = eventsIt->get<long long>();
                if (events <= 0 || events > kMaxSessionEvents) {
                    error = prefix + " has an out-of-range events value";
                    return false;
                }
                const auto statusIt = step.find("status");
                if (statusIt == step.end() || !statusIt->is_string() ||
                    statusIt->get<std::string>() != "completed") {
                    error = prefix + " is not a completed source run";
                    return false;
                }
                const auto completedIt = step.find("completed_events");
                if (completedIt == step.end() || !completedIt->is_number_integer()) {
                    error = prefix + " has no recorded completion count";
                    return false;
                }
                if (completedIt->get<long long>() != events) {
                    error = prefix + " did not complete exactly its planned events";
                    return false;
                }
                const auto runIdIt = step.find("run_id");
                if (runIdIt == step.end() || !runIdIt->is_number_integer() ||
                    runIdIt->get<long long>() < 0) {
                    error = prefix + " has no valid source run id";
                    return false;
                }
                const auto requestIt = step.find("run_request_id");
                if (requestIt == step.end() || !requestIt->is_string()) {
                    error = prefix + " has no source request id";
                    return false;
                }
                const std::string requestId = requestIt->get<std::string>();
                if (requestId.empty() || requestId.size() > 64 ||
                    !std::all_of(requestId.begin(), requestId.end(), [](unsigned char c) {
                        return std::isxdigit(c) != 0;
                    })) {
                    error = prefix + " has an invalid source request id";
                    return false;
                }
            } else {
                error = prefix + " uses an unsupported operation";
                return false;
            }
        }
        if (!sawRun) {
            error = "the session recorded no run step";
            return false;
        }
        return true;
    }

    bool PrepareReplay()
    {
        std::error_code error;
        const std::filesystem::path source(replaySource);
        if (!std::filesystem::is_directory(source, error) || error) {
            return ReplayRefuse("replay source is not a directory: " + replaySource);
        }
        std::string snapshotText;
        std::string manifestText;
        if (!ReplayReadText(source / "replay-snapshot.json", snapshotText)) {
            return ReplayRefuse("replay-snapshot.json is missing or unreadable");
        }
        if (!ReplayReadText(source / "replay-manifest.json", manifestText)) {
            return ReplayRefuse("replay-manifest.json is missing or unreadable");
        }
        SessionJson::Json snapshot;
        SessionJson::Json manifest;
        std::string parseError;
        if (!SessionJson::ParseStrict(snapshotText, snapshot, parseError)) {
            return ReplayRefuse("replay-snapshot.json is invalid: " + parseError);
        }
        if (!SessionJson::ParseStrict(manifestText, manifest, parseError)) {
            return ReplayRefuse("replay-manifest.json is invalid: " + parseError);
        }
        if (snapshot.value("schema", "") != "g4usim_session_replay_v1" ||
            snapshot.value("version", 0) != 1) {
            return ReplayRefuse("unsupported replay snapshot schema");
        }
        if (manifest.value("schema", "") != "g4usim_session_replay_manifest_v1" ||
            manifest.value("version", 0) != 1) {
            return ReplayRefuse("unsupported replay manifest schema");
        }
        if (!manifest.value("replayable", false)) {
            return ReplayRefuse("the source session is not replayable: " +
                                manifest.value("reason", std::string("unknown reason")));
        }
        const auto planIt = manifest.find("steps");
        if (planIt == manifest.end()) {
            return ReplayRefuse("the replay manifest records no steps");
        }
        std::string planError;
        if (!ValidateReplayPlan(*planIt, planError)) {
            return ReplayRefuse("the replay manifest is not replayable: " + planError);
        }
        if (manifest.value("snapshot_sha256", std::string()) !=
            input_provenance::Sha256(snapshotText)) {
            return ReplayRefuse("replay snapshot bytes do not match the manifest digest");
        }
        const SessionJson::Json& backend = snapshot["backend"];
        if (backend.value("source_fingerprint", std::string()) != G4USIM_SOURCE_FINGERPRINT) {
            return ReplayRefuse("build source fingerprint does not match the replay snapshot");
        }
        if (backend.value("geant4_version", std::string()) != std::string(G4Version)) {
            return ReplayRefuse("Geant4 version does not match the replay snapshot");
        }
        const auto& context = simulation.GetContext();
        if (snapshot.value("threads", 0) != context.GetNumThreads()) {
            return ReplayRefuse("thread count does not match the replay snapshot");
        }
        const std::string sourceOutput = ReplayNormalizePath(snapshot.value("output_root", ""));
        if (!sourceOutput.empty() && sourceOutput == ReplayNormalizePath(outputRoot)) {
            return ReplayRefuse(
                "replay needs a new output root; it must differ from the source session output");
        }
        const SessionJson::Json currentProvenance = ProvenanceIdentity();
        if (currentProvenance.value("count", 0) <= 0) {
            return ReplayRefuse("the replay process did not record the inputs it consumed");
        }
        if (currentProvenance.value("digest", std::string()) !=
            snapshot["provenance"].value("digest", std::string())) {
            return ReplayRefuse(
                "the replay process is consuming different input bytes than the source session");
        }
        const std::string inputDifference =
            CompareInputIdentities(snapshot["inputs"], CurrentInputIdentity());
        if (!inputDifference.empty()) {
            return ReplayRefuse(inputDifference);
        }
        const std::string rngText = snapshot["rng"].value("status_text", std::string());
        if (rngText.empty() ||
            input_provenance::Sha256(rngText) != snapshot["rng"].value("sha256", std::string())) {
            return ReplayRefuse("replay snapshot random state is invalid");
        }
        const std::filesystem::path restorePath = std::filesystem::path(sessionRoot) / "rng-restore.conf";
        const std::filesystem::path verifyPath = std::filesystem::path(sessionRoot) / "rng-restore-verify.conf";
        if (!ReplayWriteText(restorePath, rngText)) {
            return ReplayRefuse("could not stage the random engine state");
        }
        CLHEP::HepRandom::restoreEngineStatus(restorePath.string().c_str());
        CLHEP::HepRandom::saveEngineStatus(verifyPath.string().c_str());
        std::string verifyText;
        const bool readBack = ReplayReadText(verifyPath, verifyText);
        std::error_code cleanupError;
        std::filesystem::remove(restorePath, cleanupError);
        std::filesystem::remove(verifyPath, cleanupError);
        if (!readBack || verifyText != rngText) {
            return ReplayRefuse(
                "the restored CLHEP random engine state does not read back identically");
        }
        replaySnapshot = std::move(snapshot);
        replayManifest = std::move(manifest);
        replaySteps = replayManifest.value("steps", SessionJson::Json::array());
        replayInfo["schema"] = "g4usim_session_replay_v1";
        replayInfo["source_session_dir"] = ReplayNormalizePath(replaySource);
        replayInfo["session_id"] = replaySnapshot.value("session_id", std::string());
        replayInfo["steps"] = replaySteps;
        replayInfo["replayable"] = true;
        replaySnapshotReady = true;
        replayPrepared = true;
        RecordReplayMeta("replay_prepared",
                         SessionJson::Json{{"source_session", replayInfo["session_id"]}});
        return true;
    }

    bool ReplaySendOp(const std::string& op, const SessionJson::Json& params,
                      const std::string& requestId, long long idSeed,
                      const std::string& expectedStatus, std::string& failure)
    {
        SessionJson::Json frame;
        ++replayRequestCounter;
        std::ostringstream idText;
        idText << std::hex << std::setw(16) << std::setfill('0')
               << (idSeed + replayRequestCounter);
        frame["seq"] = lastClientSeq + 1;
        frame["id"] = idText.str();
        frame["request_id"] = requestId;
        frame["op"] = op;
        frame["state_revision"] = stateRevision;
        frame["params"] = params;
        Command command;
        command.kind = Command::Kind::Request;
        command.frame = std::move(frame);
        lastResponseStatus.clear();
        lastResponseReason.clear();
        lastResponseMessage.clear();
        if (!ProcessRequest(command)) {
            failure = "replay " + op + " stopped the session instead of being answered";
            return false;
        }
        if (lastResponseStatus != expectedStatus) {
            failure = "replay " + op + " was not accepted (" +
                      (lastResponseStatus.empty() ? "no response" : lastResponseStatus) + ")";
            if (!lastResponseReason.empty()) failure += " [" + lastResponseReason + "]";
            if (!lastResponseMessage.empty()) failure += ": " + lastResponseMessage;
            return false;
        }
        return true;
    }

    int AbortReplayStartup(int code)
    {
        RecordReplayMeta("replay_refused", SessionJson::Json{{"reason", replayInvalidReason}});
        {
            std::lock_guard<std::mutex> guard(recordMutex);
            if (record.is_open()) {
                record.flush();
                record.close();
            }
        }
        stopReader.store(true, std::memory_order_release);
        if (reader.joinable()) reader.join();
        g_activeServer.store(nullptr, std::memory_order_release);
        std::fprintf(stderr, "session replay refused: %s\n", replayInvalidReason.c_str());
        std::fflush(stderr);
        return code;
    }

    void EnsureReplayDataIdentity()
    {
        if (replayDataIdentityReady || !replayPlanValid) return;
        SessionJson::Json identity;
        std::string errorText;
        if (!BuildDataIdentity(identity, errorText)) {
            replayPlanValid = false;
            replayInvalidReason = errorText;
            MarkRecordFailure(errorText);
            return;
        }
        identity["schema"] = "g4usim_session_replay_data_identity_v1";
        identity["captured_at"] = NowIso8601();
        const std::filesystem::path path =
            std::filesystem::path(sessionRoot) / "replay-data-identity.json";
        if (!ReplayWriteText(path, identity.dump() + "\n")) {
            replayPlanValid = false;
            replayInvalidReason = "could not write replay-data-identity.json";
            MarkRecordFailure(replayInvalidReason);
            return;
        }
        replayDataIdentityReady = true;
        RecordReplayMeta("replay_data_identity_captured");
    }

    int ExecuteReplay()
    {
        RecordReplayMeta("replay_started",
                         SessionJson::Json{{"source_session", replayInfo["session_id"]}});
        std::string failure;
        std::ostringstream idText;
        idText << std::hex << std::setw(16) << std::setfill('0') << 0x100000;
        if (!ReplaySendOp("initialize", SessionJson::Json::object(), idText.str(), 0x100000,
                          "applied", failure)) {
            if (failure.empty()) failure = "replay initialize failed";
        }
        if (failure.empty()) {
            SessionJson::Json currentData;
            std::string dataError;
            if (!BuildDataIdentity(currentData, dataError)) {
                failure = "could not verify the Geant4 physics data identity: " + dataError;
            } else if (currentData.value("digest", std::string()) !=
                       replayManifest["data_identity"].value("digest", std::string())) {
                failure = "the replay process is using different Geant4 physics data than the source session";
            } else if (replayManifest["provenance_pre_run"].value("count", 0) > 0) {
                const SessionJson::Json currentProvenance = ProvenanceIdentity();
                if (currentProvenance.value("digest", std::string()) !=
                    replayManifest["provenance_pre_run"].value("digest", std::string())) {
                    failure = "the replay process consumed different input bytes than the source session";
                }
            }
        }
        // Validate every accepted source edit before any BeamOn: an invalid
        // value in a later step must not run the earlier rounds first.  This
        // pre-check is read-only (apply=false): it must not leak a later edit
        // into an earlier run that legitimately reuses the configured source.
        if (failure.empty()) {
            for (std::size_t index = 0; index < replaySteps.size(); ++index) {
                const SessionJson::Json& step = replaySteps[index];
                if (step.value("op", std::string()) != "set_source") continue;
                const SessionJson::Json params =
                    step.value("params", SessionJson::Json::object());
                std::string reason;
                std::string message;
                SessionJson::Json resolved = SessionJson::Json::object();
                if (!ApplySourceEdit(params, reason, message, resolved, false)) {
                    failure = "replay step " + std::to_string(index) +
                              " set_source is invalid (" + reason + "): " + message;
                    break;
                }
            }
        }
        std::size_t executed = 0;
        std::size_t runSteps = 0;
        for (const auto& step : replaySteps) {
            if (step.value("op", std::string()) == "run") ++runSteps;
        }
        if (failure.empty()) {
            for (std::size_t index = 0; index < replaySteps.size(); ++index) {
                const SessionJson::Json& step = replaySteps[index];
                if (!step.is_object()) {
                    failure = "replay step " + std::to_string(index) + " is not an object";
                    break;
                }
                const std::string op = step.value("op", std::string());
                const SessionJson::Json params = step.value("params", SessionJson::Json::object());
                if (op == "set_source") {
                    if (!ReplaySendOp("set_source", params, ReplayIdFor(step, 0x200000),
                                      0x200000, "accepted", failure)) {
                        failure = "replay step " + std::to_string(index) +
                                  " set_source failed: " + failure;
                        break;
                    }
                } else if (op == "run") {
                    const std::string status = step.value("status", std::string());
                    if (status != "completed") {
                        failure = "replay step " + std::to_string(index) +
                                  " is not a completed source run";
                        break;
                    }
                    if (!ReplaySendOp("run", params, ReplayIdFor(step, 0x300000),
                                      0x300000, "accepted", failure)) {
                        failure = "replay step " + std::to_string(index) +
                                  " run failed: " + failure;
                        break;
                    }
                    if (lastRunStatus != "completed") {
                        failure = "the replayed run ended as " + lastRunStatus;
                        break;
                    }
                    const long long expectedCompleted = step.value("completed_events", -1LL);
                    if (lastRunCompletedEvents != expectedCompleted) {
                        failure = "the replayed run completed " +
                                  std::to_string(lastRunCompletedEvents) +
                                  " events but the source run completed " +
                                  std::to_string(expectedCompleted);
                        break;
                    }
                    ++executed;
                } else {
                    failure = "unsupported replay step: " + op;
                    break;
                }
                if (exitCode.load(std::memory_order_relaxed) != 0) {
                    failure = "the replay ended with a failed run";
                    break;
                }
            }
        }
        if (failure.empty() && executed != runSteps) {
            failure = "the replay executed " + std::to_string(executed) +
                      " runs but the source session recorded " + std::to_string(runSteps);
        }
        if (failure.empty() && replayManifest["provenance_final"].value("count", 0) > 0) {
            const SessionJson::Json finalProvenance = ProvenanceIdentity();
            if (finalProvenance.value("digest", std::string()) !=
                replayManifest["provenance_final"].value("digest", std::string())) {
                failure = "the replay process consumed different input bytes while running";
            }
        }
        SessionJson::Json closing;
        closing["kind"] = "event";
        closing["event"] = "closing";
        closing["reason"] = failure.empty() ? "replay_finished" : "replay_failed";
        closing["exit_code"] = failure.empty() ? 0 : 4;
        closing["session_id"] = sessionId;
        closing["at"] = NowIso8601();
        closing["state_revision"] = stateRevision;
        closing["steps_total"] = replaySteps.size();
        closing["steps_executed"] = executed;
        if (!failure.empty()) closing["message"] = failure;
        Send(closing);
        RecordReplayMeta(failure.empty() ? "replay_finished" : "replay_failed",
                         SessionJson::Json{{"reason", failure}});
        if (!failure.empty()) {
            std::fprintf(stderr, "session replay failed: %s\n", failure.c_str());
            std::fflush(stderr);
            exitCode.store(4, std::memory_order_relaxed);
            return 4;
        }
        replayExecuted = true;
        exitCode.store(0, std::memory_order_relaxed);
        return 0;
    }

    std::string ReplayIdFor(const SessionJson::Json& step, long long fallbackSeed)
    {
        const std::string recorded = step.value("run_request_id", std::string());
        if (recorded.size() >= 1 && recorded.size() <= 64 &&
            std::all_of(recorded.begin(), recorded.end(), [](unsigned char c) {
                return std::isxdigit(c) != 0;
            })) {
            return recorded;
        }
        ++replayRequestCounter;
        std::ostringstream out;
        out << std::hex << std::setw(16) << std::setfill('0') << (fallbackSeed + replayRequestCounter);
        return out.str();
    }

    void WriteReplayManifest()
    {
        if (!replaySnapshotReady) return;
        SessionJson::Json manifest;
        manifest["schema"] = "g4usim_session_replay_manifest_v1";
        manifest["version"] = 1;
        manifest["session_id"] = sessionId;
        manifest["snapshot_file"] = "replay-snapshot.json";
        std::string snapshotText;
        const std::filesystem::path snapshotPath =
            std::filesystem::path(sessionRoot) / "replay-snapshot.json";
        if (ReplayReadText(snapshotPath, snapshotText)) {
            manifest["snapshot_sha256"] = input_provenance::Sha256(snapshotText);
        }
        manifest["created_at"] = NowIso8601();
        const int finalExit = exitCode.load(std::memory_order_relaxed);
        manifest["exit_code"] = finalExit;
        manifest["threads"] = simulation.GetContext().GetNumThreads();
        manifest["source_fingerprint"] = G4USIM_SOURCE_FINGERPRINT;
        manifest["output_root"] = outputRoot;
        bool replayable = finalExit == 0 && replayPlanValid && !RecordFailedSnapshot() &&
                          !replaySteps.empty() && !manifest["snapshot_sha256"].is_null();
        for (const auto& step : replaySteps) {
            if (step.value("op", std::string()) == "run" &&
                step.value("status", std::string()) != "completed") {
                replayable = false;
            }
        }
        std::string dataIdentityText;
        const std::filesystem::path dataIdentityPath =
            std::filesystem::path(sessionRoot) / "replay-data-identity.json";
        if (ReplayReadText(dataIdentityPath, dataIdentityText)) {
            SessionJson::Json dataIdentity;
            std::string parseError;
            if (SessionJson::ParseStrict(dataIdentityText, dataIdentity, parseError)) {
                manifest["data_identity"] = dataIdentity;
            } else {
                replayable = false;
                if (replayInvalidReason.empty()) replayInvalidReason = parseError;
            }
        } else {
            replayable = false;
            if (replayInvalidReason.empty()) {
                replayInvalidReason = "the session did not capture its physics data identity";
            }
        }
        manifest["provenance_pre_run"] = replayPreRunProvenance;
        manifest["provenance_final"] = ProvenanceIdentity();
        manifest["replayable"] = replayable;
        manifest["reason"] = replayable ? std::string()
                                        : (replayInvalidReason.empty()
                                               ? std::string("the session did not finish every run")
                                               : replayInvalidReason);
        manifest["steps"] = replaySteps;
        const std::filesystem::path path =
            std::filesystem::path(sessionRoot) / "replay-manifest.json";
        if (!ReplayWriteText(path, manifest.dump() + "\n")) {
            std::fprintf(stderr, "could not write replay-manifest.json: %s\n",
                         path.generic_string().c_str());
            std::fflush(stderr);
            exitCode.store(4, std::memory_order_relaxed);
        } else {
            RecordReplayMeta("replay_manifest_written",
                             SessionJson::Json{{"replayable", replayable}});
        }
    }

    int Run()
    {
        g_activeServer.store(owner, std::memory_order_release);
        // Every session gets its own directory: an existing session log must
        // never be truncated or overwritten by a later session (repair item D).
        std::error_code error;
        std::filesystem::path sessionDir;
        const std::filesystem::path baseRoot(recordRoot);
        const bool baseExisted = std::filesystem::exists(baseRoot);
        std::filesystem::create_directories(baseRoot, error);
        if (error) {
            MarkRecordFailure("could not create session record root " + baseRoot.generic_string());
            exitCode.store(4, std::memory_order_relaxed);
            return exitCode.load(std::memory_order_relaxed);
        }
        bool directoryReady = false;
        for (int attempt = 1; attempt <= 99 && !directoryReady; ++attempt) {
            const std::string name =
                attempt == 1 ? ("session-" + sessionId)
                             : ("session-" + sessionId + "-" + std::to_string(attempt));
            const std::filesystem::path candidate = baseRoot / name;
            std::error_code candidateError;
            if (std::filesystem::create_directory(candidate, candidateError)) {
                sessionDir = candidate;
                directoryReady = true;
            } else if (candidateError) {
                MarkRecordFailure("could not create session record directory " +
                                  candidate.generic_string() + ": " + candidateError.message());
                exitCode.store(4, std::memory_order_relaxed);
                return exitCode.load(std::memory_order_relaxed);
            }
        }
        if (!directoryReady) {
            MarkRecordFailure("could not allocate a unique session record directory under " +
                              baseRoot.generic_string());
            exitCode.store(4, std::memory_order_relaxed);
            return exitCode.load(std::memory_order_relaxed);
        }
        sessionRoot = sessionDir.generic_string();
        const std::filesystem::path logPath = sessionDir / "session.jsonl";
        record.open(logPath, std::ios::binary | std::ios::trunc);
        if (!record.good()) {
            MarkRecordFailure("could not create " + logPath.generic_string());
            exitCode.store(4, std::memory_order_relaxed);
            // A failed startup must not leave a half-created record tree behind,
            // but directories that already existed before this session stay intact.
            std::error_code cleanupError;
            std::filesystem::remove_all(sessionDir, cleanupError);
            if (!baseExisted) {
                const bool empty = std::filesystem::is_empty(baseRoot, cleanupError);
                if (!cleanupError && empty) {
                    std::error_code removeError;
                    std::filesystem::remove(baseRoot, removeError);
                }
            }
            return exitCode.load(std::memory_order_relaxed);
        }
        reader = std::thread([this] { ReaderLoop(); });

        if (replayMode) {
            if (!PrepareReplay()) return AbortReplayStartup(4);
        } else if (!CaptureReplaySnapshot()) {
            return AbortReplayStartup(exitCode.load(std::memory_order_relaxed) != 0
                                          ? exitCode.load(std::memory_order_relaxed)
                                          : 4);
        }

        bool serving = true;
        bool eofExit = false;
        while (serving) {
            Command command;
            bool hasCommand = false;
            {
                std::unique_lock<std::mutex> lock(stateMutex);
                if (queue.empty()) wake.wait_for(lock, kReadPoll);
                if (!queue.empty()) {
                    command = std::move(queue.front());
                    queue.pop_front();
                    hasCommand = true;
                }
            }
            if (!hasCommand) {
                if (eofSeen.load() && queue.empty()) {
                    eofExit = true;
                    break;
                }
                continue;
            }
            if (!command.raw.empty() && command.kind != Command::Kind::Fatal)
                RecordFrame("c2s", command.raw);
            switch (command.kind) {
                case Command::Kind::Hello:
                    serving = ProcessHello(command);
                    break;
                case Command::Kind::Request:
                    serving = ProcessRequest(command);
                    break;
                case Command::Kind::Fatal: {
                    std::string error = command.error;
                    {
                        std::lock_guard<std::mutex> guard(stateMutex);
                        if (!protocolFailed) {
                            protocolFailed = true;
                            protocolError = error;
                        }
                        error = protocolError;
                    }
                    ReportProtocolFailure(error);
                    exitCode = 3;
                    serving = false;
                    break;
                }
                case Command::Kind::Eof: {
                    std::string protocolErrorText;
                    if (ReadProtocolFailure(protocolErrorText)) {
                        ReportProtocolFailure(protocolErrorText);
                        exitCode = 3;
                        serving = false;
                        break;
                    }
                    bool running = false;
                    {
                        std::lock_guard<std::mutex> guard(stateMutex);
                        running = phase == Phase::Running;
                        if (running) {
                            eofShutdown = true;
                            if (currentRunId >= 0) {
                                cancelRequested = true;
                                g_cancelRunId.store(currentRunId, std::memory_order_release);
                            } else {
                                cancelPending = true;
                            }
                        }
                    }
                    if (running) {
                        // Wait for the run to finish; the run callback closes the session.
                        eofSeen.store(true);
                        continue;
                    }
                    eofExit = true;
                    serving = false;
                    break;
                }
            }
            if (replayMode && !replayExecuted && helloSeen && serving &&
                phase == Phase::Idle) {
                replayExecuted = true;
                const int replayCode = ExecuteReplay();
                if (replayCode != 0) exitCode.store(replayCode, std::memory_order_relaxed);
                serving = false;
            }
        }

        {
            std::lock_guard<std::mutex> guard(stateMutex);
            phase = Phase::Stopped;
            bool expected = false;
            if (eofSeen.compare_exchange_strong(expected, false)) {
                // EOF shutdown: closing event without a shutdown request.
                if (exitCode == 0) eofExit = true;
            }
        }
        g_activeServer.store(nullptr, std::memory_order_release);
        stopReader.store(true, std::memory_order_release);
        if (reader.joinable()) {
            // Close stdin so a blocked reader can observe EOF/broken pipe.
#ifdef _WIN32
            // The reader polls with a 50 ms timeout, so simply joining is bounded.
            reader.join();
#else
            reader.join();
#endif
        }
        {
            std::lock_guard<std::mutex> guard(recordMutex);
            if (record.is_open()) {
                SessionJson::Json closing;
                closing["schema"] = "g4usim-session-log-v1";
                closing["at"] = NowIso8601();
                closing["direction"] = "meta";
                closing["event"] = eofExit ? "eof_close" : "session_end";
                closing["exit_code"] = exitCode.load(std::memory_order_relaxed);
                closing["session_id"] = sessionId;
                record << closing.dump() << '\n';
                record.flush();
                const bool closingOk = record.good();
                record.close();
                if (!closingOk || record.fail()) {
                    recordFailed = true;
                    recordError = "could not close the session record cleanly";
                    if (exitCode.load(std::memory_order_relaxed) == 0) {
                        exitCode.store(4, std::memory_order_relaxed);
                    }
                }
            }
            if (recordFailed && exitCode.load(std::memory_order_relaxed) == 0) {
                exitCode.store(4, std::memory_order_relaxed);
            }
        }
        if (!replayMode) WriteReplayManifest();
        return exitCode.load(std::memory_order_relaxed);
    }
};

SessionServer::SessionServer(SimulationManager& simulation, std::string recordRoot,
                             std::string replaySource)
    : simulation_(simulation), recordRoot_(std::move(recordRoot)), replaySource_(std::move(replaySource))
{
    impl_ = new Impl(simulation_, recordRoot_, replaySource_);
    impl_->owner = this;
}

SessionServer::~SessionServer()
{
    delete impl_;
}

int SessionServer::Run()
{
    return impl_->Run();
}

void SessionServer::HandleRunBegin(int runId, int plannedEvents)
{
    impl_->HandleRunBeginInternal(runId, plannedEvents);
}

void SessionServer::HandleRunEnd(int runId, int plannedEvents, int completedEvents,
                                 long long abortedEvents, bool outputFailed,
                                 OutputManager* outputManager)
{
    impl_->HandleRunEndInternal(runId, plannedEvents, completedEvents, abortedEvents, outputFailed,
                                outputManager);
}
