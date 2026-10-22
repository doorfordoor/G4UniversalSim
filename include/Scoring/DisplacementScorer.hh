#pragma once

#include "Scoring/HistoryStatistics.hh"
#include "Scoring/NielTable.hh"
#include "Scoring/ScorerBase.hh"

#include <map>
#include <memory>
#include <string>

// Displacement damage dose (DDD) per daughter-free sensitive touchable
// (roadmap B2, experimental): the track-length fluence of each tabulated
// particle folded with its NIEL(E) table,
//   DDD = sum over steps of  w * l * NIEL(E_mean) / V          (MeV/g)
// with track weight w, step length l, solid volume V and E_mean the mean of the
// pre- and post-step kinetic energies. Particles without a table are not
// scored; steps outside a table's energy range add to out_of_range_track_length
// and contribute no DDD. The result is as good as the supplied NIEL tables and
// the fluence estimate; Geant4's own non-ionizing energy deposit is not used.
class DisplacementScorer : public ScorerBase {
public:
    using TableMap = std::map<std::string, std::shared_ptr<const NielTable>>;

    explicit DisplacementScorer(const std::string& name = "displacement");
    ~DisplacementScorer() override;

    void SetTables(const TableMap& tables);

    void BeginRun(int runID) override;
    void EndEvent(int eventID) override;
    void ScoreHit(const HitRecord& hit) override;
    void Write(OutputManager& output) override;
    void Reset() override;

private:
    struct ParticleData {
        HistoryTally ddd;              // MeV/g
        double trackLength = 0.0;      // weighted, mm, inside the table range
        double outOfRangeLength = 0.0; // weighted, mm
    };
    struct VolumeData {
        std::string name;
        double volume = 0.0;           // Geant4 volume units
        HistoryTally total;            // MeV/g, all tabulated particles
        std::map<std::string, ParticleData> particles;
    };
    TableMap tables_;
    int runID_ = -1;
    long long events_ = 0;
    std::map<std::string, VolumeData> volumes_;
    HistoryTallySet touched_;
};
