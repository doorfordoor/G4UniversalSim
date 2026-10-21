#pragma once

#include "Scoring/HistoryStatistics.hh"
#include "Scoring/ScorerBase.hh"

#include <map>
#include <vector>
#include <set>
#include <string>

// Track- and dose-averaged LET per sensitive physical touchable.
//
// For every charged step in a sensitive volume the SensitiveDetector supplies
// S = unrestricted electronic stopping power (G4EmCalculator::ComputeElectronicDEDX)
// at the step's mean kinetic energy, in HitRecord::LETstep (Geant4 units, MeV/mm).
// With step length l and track weight w the scorer accumulates
//   sum_wl = sum w*l,  sum_wSl = sum w*S*l,  sum_wS2l = sum w*S^2*l
// and reports LET_t = sum_wSl / sum_wl and LET_d = sum_wS2l / sum_wSl
// (keV/um, numerically equal to MeV/mm). The sums are additive across threads.
// For the statistical error the per-event sums a = sum w*l, b = sum w*S*l and
// c = sum w*S^2*l are also folded into sum a^2, b^2, c^2, a*b and b*c, giving the
// delta-method relative error of the ratios LET_t = B/A and LET_d = C/B
// (see Scoring/HistoryStatistics.hh).
class LETScorer : public ScorerBase {
public:
    explicit LETScorer(const std::string& name = "let");
    ~LETScorer() override;

    void BeginRun(int runID) override;
    void EndEvent(int eventID) override;
    void ScoreHit(const HitRecord& hit) override;
    void Write(OutputManager& output) override;
    void Reset() override;

    // Empty set = all charged particles.
    void SetParticles(const std::set<std::string>& particles);
    const std::set<std::string>& GetParticles() const;

private:
    struct VolumeLET {
        std::string name;
        long long steps = 0;
        double sumWL = 0.0;    // mm
        double sumWSL = 0.0;   // MeV
        double sumWS2L = 0.0;  // MeV^2/mm
        // Per-event second moments (see class comment).
        double sumSqWL = 0.0;        // mm^2
        double sumSqWSL = 0.0;       // MeV^2
        double sumSqWS2L = 0.0;      // MeV^4/mm^2
        double sumWLxWSL = 0.0;      // MeV*mm
        double sumWSLxWS2L = 0.0;    // MeV^3/mm
        long long entries = 0;       // events with a contribution
        double eventWL = 0.0;
        double eventWSL = 0.0;
        double eventWS2L = 0.0;
        bool pending = false;
    };
    int runID_ = -1;
    long long events_ = 0;
    std::vector<VolumeLET*> touched_;
    std::set<std::string> particles_;
    std::map<std::string, VolumeLET> volumes_;
};
