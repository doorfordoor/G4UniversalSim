#pragma once

// History-by-history (per-event) statistics for the built-in scorers (roadmap A3).
//
// A tally collects the contribution of the current event; at the end of the
// event the event value x_i is folded into sum = sum_i x_i and
// sumSq = sum_i x_i^2. With N events in the run (events that scored nothing
// count as x_i = 0):
//   mean per event = sum / N
//   R   = sqrt(sumSq / sum^2 - 1/N)          relative error of the run total/mean
//   FOM = 1 / (R^2 T)                        T = run wall time in seconds
// This is the project's uncorrected event-moment approximation. It omits the
// N/(N-1) finite-sample variance correction; it is not G4StatDouble::rms().
// N<2 or a zero total cannot establish a relative uncertainty. Numerical zero
// is retained for legacy consumers; UncertaintyStatus must accompany it.
// For a ratio of two per-event tallies Q = B/A (track/dose-averaged LET) the
// first-order (delta-method) relative error is
//   R_Q^2 = sumSq_B/B^2 + sumSq_A/A^2 - 2 sum_AB/(A B),
// where sum_AB = sum_i a_i b_i; the 1/N terms cancel.
// sum, sumSq, cross sums, entries and event counts are additive over threads.

#include <map>
#include <string>
#include <tuple>
#include <vector>

struct HistoryTally {
    double sum = 0.0;
    double sumSq = 0.0;
    long long entries = 0;  // events with a non-zero contribution
    double event = 0.0;
    bool pending = false;

    void Close();
};

// Tracks the tallies touched in the current event so EndEvent costs O(touched).
// Tallies must have stable addresses (e.g. std::map values) until Clear().
class HistoryTallySet {
public:
    void Add(HistoryTally& tally, double value);
    void EndEvent();
    void Clear();

private:
    std::vector<HistoryTally*> touched_;
};

namespace HistoryStatistics {

double RelativeError(double sum, double sumSq, long long events);
double RatioRelativeError(double sumNum, double sumSqNum, double sumDen, double sumSqDen, double sumCross);
double FigureOfMerit(double relativeError, double seconds);
const char* UncertaintyStatus(long long events, double numerator, bool ratio = false, double denominator = 0.0);

// One merged quantity of one scorer key. For estimator "total" only sum/sumSq
// are used; for "ratio" the value is num/den with the delta-method error.
struct Entry {
    std::string name;
    std::string unit;
    bool ratio = false;
    double sum = 0.0;      // total: sum of per-event values; ratio: numerator sum
    double sumSq = 0.0;
    double denSum = 0.0;   // ratio only
    double denSumSq = 0.0;
    double crossSum = 0.0; // ratio only: sum_i num_i * den_i
    long long entries = 0;
};

using Key = std::tuple<std::string, std::string, std::string>;  // scorer, quantity, key

// Process-wide, mutex-protected merge of worker partial statistics. Workers
// submit in their EndOfRunAction; the master takes the merged run afterwards
// (Geant4 finishes all worker runs before the master's EndOfRunAction).
void Submit(int runId, const std::string& scorer, const std::string& quantity, const std::string& key,
            const Entry& entry);
std::map<Key, Entry> Take(int runId);
void Clear();

}  // namespace HistoryStatistics
