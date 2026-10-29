#include "Scoring/HistoryStatistics.hh"
#include "Scoring/NumericChecks.hh"

#include <cmath>
#include <mutex>
#include <stdexcept>

void HistoryTally::Close()
{
    ScoringNumeric::Finite(event, "history event");
    if (event != 0.0) {
        const double nextSum = ScoringNumeric::Add(sum, event, "history sum");
        const double square = ScoringNumeric::Multiply(event, event, "history event square");
        const double nextSumSq = ScoringNumeric::Add(sumSq, square, "history sum of squares");
        const auto nextEntries = ScoringNumeric::AddCount(entries, 1, "history entries");
        sum = nextSum;
        sumSq = nextSumSq;
        entries = nextEntries;
    }
    event = 0.0;
    pending = false;
}

void HistoryTallySet::Add(HistoryTally& tally, double value)
{
    const double next = ScoringNumeric::Add(tally.event, value, "history event accumulation");
    if (!tally.pending) {
        touched_.push_back(&tally);
        tally.pending = true;
    }
    tally.event = next;
}

void HistoryTallySet::EndEvent()
{
    for (HistoryTally* tally : touched_) tally->Close();
    touched_.clear();
}

void HistoryTallySet::Clear()
{
    touched_.clear();
}

namespace HistoryStatistics {

const char* UncertaintyStatus(long long events, double numerator, bool ratio, double denominator)
{
    if (events < 2) return "insufficient_events";
    if (ratio && denominator == 0.0) return "undefined_ratio";
    if (numerator == 0.0) return "zero_total";
    return "approximate";
}

double RelativeError(double sum, double sumSq, long long events)
{
    ScoringNumeric::Finite(sum, "statistics sum");
    ScoringNumeric::Finite(sumSq, "statistics sum of squares");
    if (events <= 0 || sum == 0.0) return 0.0;
    // Equivalent estimator without overflowing sum*sum for many finite events.
    const double value = ScoringNumeric::Finite((sumSq / sum) / sum -
        1.0 / static_cast<double>(events), "relative error variance");
    return value > 0.0 ? std::sqrt(value) : 0.0;
}

double RatioRelativeError(double sumNum, double sumSqNum, double sumDen, double sumSqDen, double sumCross)
{
    for (double value : {sumNum, sumSqNum, sumDen, sumSqDen, sumCross}) {
        ScoringNumeric::Finite(value, "ratio statistics");
    }
    if (sumNum == 0.0 || sumDen == 0.0) return 0.0;
    const double value = ScoringNumeric::Finite((sumSqNum / sumNum) / sumNum +
        (sumSqDen / sumDen) / sumDen - 2.0 * ((sumCross / sumNum) / sumDen), "ratio variance");
    return value > 0.0 ? std::sqrt(value) : 0.0;
}

double FigureOfMerit(double relativeError, double seconds)
{
    ScoringNumeric::Finite(relativeError, "relative error");
    ScoringNumeric::Finite(seconds, "run wall time");
    if (!(relativeError > 0.0) || !(seconds > 0.0)) return 0.0;
    const double inverseScaledError = (1.0 / relativeError) / std::sqrt(seconds);
    return ScoringNumeric::Multiply(inverseScaledError, inverseScaledError, "figure of merit");
}

namespace {
void ValidateEntry(const Entry& entry)
{
    for (double value : {entry.sum, entry.sumSq, entry.denSum, entry.denSumSq, entry.crossSum}) {
        ScoringNumeric::Finite(value, "worker statistics submission");
    }
    ScoringNumeric::AddCount(entry.entries, 0, "worker entries");
    if (entry.sumSq < 0.0 || entry.denSumSq < 0.0) {
        throw std::runtime_error("HistoryStatistics: negative sum of squares");
    }
}

std::mutex& RegistryMutex()
{
    static std::mutex mutex;
    return mutex;
}

std::map<int, std::map<Key, Entry>>& Registry()
{
    static std::map<int, std::map<Key, Entry>> registry;
    return registry;
}
}  // namespace

void Submit(int runId, const std::string& scorer, const std::string& quantity, const std::string& key,
            const Entry& entry)
{
    ValidateEntry(entry);
    std::lock_guard<std::mutex> lock(RegistryMutex());
    auto& runEntries = Registry()[runId];
    const Key id{scorer, quantity, key};
    auto found = runEntries.find(id);
    if (found == runEntries.end()) {
        runEntries.emplace(id, entry);
        return;
    }
    Entry& merged = found->second;
    if (merged.ratio != entry.ratio || merged.unit != entry.unit) {
        throw std::runtime_error("HistoryStatistics: inconsistent submissions for " + scorer + "/" + quantity +
                                 "/" + key);
    }
    Entry candidate = merged;
    candidate.sum = ScoringNumeric::Add(merged.sum, entry.sum, "worker sum merge");
    candidate.sumSq = ScoringNumeric::Add(merged.sumSq, entry.sumSq, "worker square merge");
    candidate.denSum = ScoringNumeric::Add(merged.denSum, entry.denSum, "worker denominator merge");
    candidate.denSumSq = ScoringNumeric::Add(merged.denSumSq, entry.denSumSq, "worker denominator square merge");
    candidate.crossSum = ScoringNumeric::Add(merged.crossSum, entry.crossSum, "worker cross sum merge");
    candidate.entries = ScoringNumeric::AddCount(merged.entries, entry.entries, "worker entries merge");
    merged = std::move(candidate);
}

std::map<Key, Entry> Take(int runId)
{
    std::lock_guard<std::mutex> lock(RegistryMutex());
    std::map<Key, Entry> result;
    auto found = Registry().find(runId);
    if (found != Registry().end()) {
        result = std::move(found->second);
        Registry().erase(found);
    }
    return result;
}

void Clear()
{
    std::lock_guard<std::mutex> lock(RegistryMutex());
    Registry().clear();
}

}  // namespace HistoryStatistics
