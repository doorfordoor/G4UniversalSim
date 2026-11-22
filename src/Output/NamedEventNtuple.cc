#include "Output/NamedEventNtuple.hh"
#include "Output/CsvWriter.hh"
#include "Config/InputProvenance.hh"
#include "Utils/StringUtils.hh"

#include <array>
#include <charconv>
#include <cmath>
#include <fstream>
#include <functional>
#include <memory>
#include <queue>
#include <stdexcept>

std::vector<std::string> NamedEventNtuple::Header() const
{
    std::vector<std::string> result{"run_id", "event_id", "thread_id"};
    result.insert(result.end(), columns.begin(), columns.end());
    return result;
}

bool NamedEventNtuple::IsEnergyColumn(const std::string& column)
{
    return column == "raw_edep_MeV" || column == "weighted_edep_MeV";
}

bool NamedEventNtuple::MatchesHeader(const std::string& header)
{
    const auto fields = StringUtils::Split(header, ',', false);
    return (fields.size() == 4 || fields.size() == 5) &&
           fields[0] == "run_id" && fields[1] == "event_id" && fields[2] == "thread_id" &&
           IsEnergyColumn(fields[3]) && (fields.size() == 4 ||
           (IsEnergyColumn(fields[4]) && fields[4] != fields[3]));
}

namespace {
class Cursor {
public:
    Cursor(const EventNtupleShard& shard, const std::string& header, int run, int worker, std::size_t width)
        : shard_(shard), input_(shard.path, std::ios::binary), run_(run), worker_(worker), width_(width)
    {
        if (!input_) throw std::runtime_error("cannot open event ntuple shard " + shard.path);
        std::string actual;
        if (!ReadLine(actual) || actual != header) throw std::runtime_error("event ntuple shard header mismatch");
    }

    bool Advance()
    {
        std::string line;
        if (!ReadLine(line)) {
            if (rows_ != shard_.rows || digest_.Finish().sha256 != shard_.sha256)
                throw std::runtime_error("event ntuple shard contents disagree with closed worker receipt");
            return false;
        }
        fields = StringUtils::Split(line, ',', false);
        if (rows_ >= shard_.rows || fields.size() != width_ ||
            fields[0] != std::to_string(run_) || fields[2] != std::to_string(worker_))
            throw std::runtime_error("event ntuple row count, shape or worker identity mismatch");
        int id;
        const auto& text = fields[1];
        const auto parsed = std::from_chars(text.data(), text.data() + text.size(), id);
        if (parsed.ec != std::errc{} || parsed.ptr != text.data() + text.size() || id <= event)
            throw std::runtime_error("invalid or unordered event ntuple key");
        event = id;
        for (std::size_t i = 3; i < fields.size(); ++i) {
            double value;
            const auto& energy = fields[i];
            const auto end = energy.data() + energy.size();
            const auto number = std::from_chars(energy.data(), end, value);
            if (number.ec != std::errc{} || number.ptr != end || !std::isfinite(value))
                throw std::runtime_error("invalid event ntuple binary64 value");
        }
        ++rows_;
        return true;
    }

    int event = -1;
    std::vector<std::string> fields;
private:
    bool ReadLine(std::string& text)
    {
        // Header plus at most three int32 and two round-trip doubles fit in 256 bytes.
        std::array<char, 256> buffer{};
        input_.getline(buffer.data(), buffer.size());
        const auto count = input_.gcount();
        if (input_.bad() || (input_.fail() && !input_.eof()) || (input_.eof() && count != 0))
            throw std::runtime_error("short, oversized or unreadable event ntuple row");
        if (input_.eof()) return false;
        text.assign(buffer.data(), static_cast<std::size_t>(count - 1));
        digest_.Update(text);
        digest_.Update("\n");
        if (!text.empty() && text.back() == '\r') text.pop_back();
        return true;
    }

    const EventNtupleShard& shard_;
    std::ifstream input_;
    input_provenance::StreamDigest digest_;
    int run_, worker_, rows_ = 0;
    std::size_t width_;
};
}

void MergeEventNtuple(const NamedEventNtuple& definition, const std::map<int, EventNtupleShard>& shards,
                      int runId, int completed, CsvWriter& destination)
{
    const auto columns = definition.Header();
    const auto header = StringUtils::Join(columns, ",");
    destination.WriteHeader(columns);
    std::map<int, std::unique_ptr<Cursor>> cursors;
    using Head = std::pair<int, int>;  // event, worker
    std::priority_queue<Head, std::vector<Head>, std::greater<Head>> pending;
    for (const auto& [worker, shard] : shards) {
        auto cursor = std::make_unique<Cursor>(shard, header, runId, worker, columns.size());
        if (cursor->Advance()) pending.emplace(cursor->event, worker);
        cursors.emplace(worker, std::move(cursor));
    }
    int next = 0;
    while (!pending.empty()) {
        const auto [event, worker] = pending.top();
        pending.pop();
        if (event != next || next >= completed) throw std::runtime_error("event ntuple missing or duplicate key");
        ++next;
        auto& cursor = *cursors.at(worker);
        destination.WriteRow(cursor.fields);
        if (cursor.Advance()) pending.emplace(cursor.event, worker);
    }
    if (next != completed) throw std::runtime_error("event ntuple missing completed event");
}
