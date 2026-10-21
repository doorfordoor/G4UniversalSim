#include "Scoring/HistoryStatistics.hh"

#include <cmath>
#include <mutex>
#include <stdexcept>

void HistoryTally::Close()
{
    if (event != 0.0) {
        sum += event;
        sumSq += event * event;
        ++entries;
    }
    event = 0.0;
    pending = false;
}

void HistoryTallySet::Add(HistoryTally& tally, double value)
{
    if (!tally.pending) {
        tally.pending = true;
        touched_.push_back(&tally);
    }
    tally.event += value;
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

double RelativeError(double sum, double sumSq, long long events)
{
    if (events <= 0 || sum == 0.0) return 0.0;
    const double value = sumSq / (sum * sum) - 1.0 / static_cast<double>(events);
    return value > 0.0 ? std::sqrt(value) : 0.0;
}

double RatioRelativeError(double sumNum, double sumSqNum, double sumDen, double sumSqDen, double sumCross)
{
    if (sumNum == 0.0 || sumDen == 0.0) return 0.0;
    const double value = sumSqNum / (sumNum * sumNum) + sumSqDen / (sumDen * sumDen) -
                         2.0 * sumCross / (sumNum * sumDen);
    return value > 0.0 ? std::sqrt(value) : 0.0;
}

double FigureOfMerit(double relativeError, double seconds)
{
    if (!(relativeError > 0.0) || !(seconds > 0.0)) return 0.0;
    return 1.0 / (relativeError * relativeError * seconds);
}

namespace {
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
    merged.sum += entry.sum;
    merged.sumSq += entry.sumSq;
    merged.denSum += entry.denSum;
    merged.denSumSq += entry.denSumSq;
    merged.crossSum += entry.crossSum;
    merged.entries += entry.entries;
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
