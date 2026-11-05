#include "Scoring/HistoryStatistics.hh"
#include <cmath>
#include <iomanip>
#include <iostream>

int main()
{
    using namespace HistoryStatistics;
    const double events[2][2] = {{1,1}, {0,4}};
    double avg = 0;
    const Key key{"dose","raw_dose","fixture"};
    for (const auto& worker : events) {
        HistoryTally tally;
        HistoryTallySet local;
        for (double x : worker) {
            local.Add(tally, 0.25*x);
            local.Add(tally, 0.75*x);
            local.EndEvent();
        }
        Entry e;
        e.sum=tally.sum;
        e.sumSq=tally.sumSq;
        e.entries=tally.entries;
        e.unit="Gy";
        avg += RelativeError(e.sum,e.sumSq,2)/2;
        Submit(0,"dose","raw_dose","fixture",e);
    }
    const auto merged=Take(0).at(key);
    const double correct=RelativeError(merged.sum,merged.sumSq,4);
    const auto accepted = [](double x){return std::abs(x-.5) < 1e-14;};
    if (merged.sum!=6 || merged.sumSq!=18 || merged.entries!=3 ||
        !accepted(correct) || accepted(avg) || std::abs(avg-std::sqrt(.5)/2)>1e-14)
        return 1;
    std::cout<<std::setprecision(17)<<"{\"S\":"<<merged.sum<<",\"S2\":"<<merged.sumSq
        <<",\"N\":4,\"entries\":"<<merged.entries<<",\"merged_R\":"<<correct
        <<",\"wrong_average\":"<<avg<<",\"correct_accepted\":true,\"average_rejected\":true}\n";
}
