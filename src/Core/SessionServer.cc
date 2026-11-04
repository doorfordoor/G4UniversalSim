// Versioned controlled-session server (F2, protocol g4usim-session-v1).
//
// Threading model: the process main thread owns every Geant4 call. A reader
// thread only parses stdin frames, records a cancel intent and wakes the main
// loop; it never touches Geant4 or the session state without the state mutex.

#include "Core/SessionServer.hh"

#include "Config/InputProvenance.hh"
#include "Core/SessionJson.hh"
#include "Core/SimulationManager.hh"
#include "Output/OutputManager.hh"
#include "Source/SourceManager.hh"
#include "Utils/UnitParser.hh"

#include "BuildInfo.hh"
#include "G4RunManager.hh"
#include "G4UImanager.hh"

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

    Impl(SimulationManager& manager, std::string root)
        : simulation(manager), recordRoot(std::move(root))
    {
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
    bool ApplySourceEdit(const SessionJson::Json& params, std::string& reason, std::string& message,
                         SessionJson::Json& resolved)
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
                source->SetParticle(value);
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
                source->SetMonoEnergy(energy);
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
            source->SetPointPosition(position[0], position[1], position[2]);
        } else if (field == "direction") {
            const auto it = params.find("value");
            if (it == params.end() || !it->is_string()) {
                reason = "invalid_value"; message = "direction requires \"dx dy dz\" or a +x/-x token"; return false;
            }
            std::array<double, 3> direction{};
            if (!ParseDirectionTriple(it->get<std::string>(), direction)) {
                reason = "invalid_value"; message = "direction requires three finite non-zero components"; return false;
            }
            source->SetDirection(direction[0], direction[1], direction[2]);
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
                source->SetPlaneBeamAt(radius, center[0], center[1], center[2], directionText);
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
            {
                std::lock_guard<std::mutex> guard(stateMutex);
                phase = Phase::Running;
                pendingRunRequest = requestId;
                currentRunId = -1;
                cancelPending = false;
                cancelRequested = false;
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
        Send(welcome);
        return true;
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
        return exitCode.load(std::memory_order_relaxed);
    }
};

SessionServer::SessionServer(SimulationManager& simulation, std::string recordRoot)
    : simulation_(simulation), recordRoot_(std::move(recordRoot))
{
    impl_ = new Impl(simulation_, recordRoot_);
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
