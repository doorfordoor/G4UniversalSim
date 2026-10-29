#include "Scoring/HistoryStatistics.hh"
#include "Scoring/NumericChecks.hh"

#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {
int checks = 0;
void Require(bool condition, const char* label)
{
    if (!condition) throw std::runtime_error(label);
    ++checks;
}
template <typename Operation> void Reject(Operation operation, const char* label)
{
    bool rejected = false;
    try { operation(); } catch (const std::runtime_error&) { rejected = true; }
    Require(rejected, label);
}
}  // namespace

int main()
{
    try {
        const double large = std::numeric_limits<double>::max();
        Require(ScoringNumeric::Multiply(2.0, 3.0, "ordinary") == 6.0, "ordinary product");
        Reject([&]() { ScoringNumeric::Multiply(large, 2.0, "product"); }, "product overflow");
        Reject([&]() { ScoringNumeric::Add(large, large, "sum"); }, "sum overflow");
        Reject([]() { ScoringNumeric::Finite(std::numeric_limits<double>::quiet_NaN(), "input"); }, "NaN");
        Reject([]() { ScoringNumeric::AddCount(std::numeric_limits<long long>::max(), 1, "count"); }, "count overflow");
        Require(ScoringNumeric::PositiveLETStep(1, 1, 1), "ordinary LET step");
        Require(!ScoringNumeric::PositiveLETStep(0, 1, 1), "neutral LET sentinel");
        Require(!ScoringNumeric::PositiveLETStep(1, 0, 1), "zero length LET step");
        Reject([]() { ScoringNumeric::PositiveLETStep(std::numeric_limits<double>::quiet_NaN(), 1, 1); }, "LET NaN stopping power");
        Reject([]() { ScoringNumeric::PositiveLETStep(0, std::numeric_limits<double>::quiet_NaN(), 1); }, "LET NaN length before neutral filter");
        Reject([]() { ScoringNumeric::PositiveLETStep(0, 0, std::numeric_limits<double>::infinity()); }, "LET infinite weight before zero filter");

        HistoryTally tally;
        HistoryTallySet set;
        set.Add(tally, 1.0); set.EndEvent();
        set.Add(tally, 2.0); set.EndEvent();
        Require(tally.sum == 3.0 && tally.sumSq == 5.0 && tally.entries == 2, "ordinary history moments");
        Require(!tally.pending && tally.event == 0.0, "event reset");
        set.Add(tally, 0.0); set.EndEvent();
        Require(tally.sum == 3.0 && tally.entries == 2, "zero contribution");

        HistoryTally overflowing;
        set.Add(overflowing, large);
        Reject([&]() { set.Add(overflowing, large); }, "event addition overflow");
        Require(overflowing.event == large, "failed add preserves event");
        Reject([&]() { overflowing.Close(); }, "event square overflow");
        Require(overflowing.sum == 0 && overflowing.sumSq == 0 && overflowing.entries == 0,
                "failed close is atomic");
        set.Clear();
        HistoryTally squareSum;
        squareSum.sumSq = large * 0.75;
        squareSum.event = std::sqrt(large * 0.5);
        Reject([&]() { squareSum.Close(); }, "sum of finite event squares overflow");
        Require(squareSum.sum == 0 && squareSum.sumSq == large * 0.75 && squareSum.entries == 0,
                "failed square sum preserves history");
        HistoryTally total;
        total.sum = large;
        total.event = large;
        Reject([&]() { total.Close(); }, "run sum overflow");
        Require(total.sum == large && total.entries == 0, "failed run sum preserves history");

        using namespace HistoryStatistics;
        Clear();
        Entry entry;
        entry.name = "detector"; entry.unit = "MeV";
        entry.sum = 1; entry.sumSq = large * 0.75; entry.entries = 1;
        Submit(0, "edep", "weighted", "detector", entry);
        Entry incoming = entry;
        incoming.sum = 2;
        Reject([&]() { Submit(0, "edep", "weighted", "detector", incoming); }, "worker square merge overflow");
        auto rows = Take(0);
        Require(rows.size() == 1 && rows.begin()->second.sum == 1 && rows.begin()->second.entries == 1,
                "failed worker merge is atomic");
        incoming.sumSq = 1; incoming.sum = std::numeric_limits<double>::infinity();
        Reject([&]() { Submit(1, "edep", "weighted", "detector", incoming); }, "first invalid worker rejected");
        Require(Take(1).empty(), "first invalid worker not registered");
        incoming.sum = 1; incoming.sumSq = 1; incoming.entries = -1;
        Reject([&]() { Submit(2, "edep", "weighted", "detector", incoming); }, "negative entries rejected");

        Entry ratio;
        ratio.ratio = true; ratio.unit = "MeV/mm";
        ratio.sum = ratio.sumSq = ratio.denSum = ratio.denSumSq = 1;
        ratio.crossSum = large * 0.75;
        Submit(3, "let", "ratio", "detector", ratio);
        Reject([&]() { Submit(3, "let", "ratio", "detector", ratio); }, "cross moment merge overflow");
        rows = Take(3);
        Require(rows.begin()->second.sum == 1 && rows.begin()->second.denSum == 1, "ratio merge atomic");

        Require(std::abs(RelativeError(3, 5, 2) - std::sqrt(1.0 / 18)) < 1e-14, "ordinary error unchanged");
        Require(std::abs(RelativeError(2e154, 1e308, 8) - std::sqrt(0.125)) < 1e-14,
                "finite moments do not overflow denominator");
        Require(std::abs(FigureOfMerit(0.5, 2) - 2) < 1e-14, "ordinary FOM");
        Require(std::abs(FigureOfMerit(1e-200, 1e300) / 1e100 - 1) < 1e-14,
                "representable FOM avoids intermediate overflow");
        Require(std::string(UncertaintyStatus(0, 0)) == "insufficient_events", "empty uncertainty");
        Require(std::string(UncertaintyStatus(1, 2)) == "insufficient_events", "one history uncertainty");
        Require(std::string(UncertaintyStatus(2, 3)) == "approximate", "two history approximation");
        Require(std::string(UncertaintyStatus(2, 0)) == "zero_total", "zero observed total");
        Require(std::string(UncertaintyStatus(2, 1, true, 0)) == "undefined_ratio", "zero ratio denominator");
        std::cout << "checks=" << checks << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
