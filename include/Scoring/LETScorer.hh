#pragma once

#include "Scoring/ScorerBase.hh"

#include <map>
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
class LETScorer : public ScorerBase {
public:
    explicit LETScorer(const std::string& name = "let");
    ~LETScorer() override;

    void BeginRun(int runID) override;
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
    };
    int runID_ = -1;
    std::set<std::string> particles_;
    std::map<std::string, VolumeLET> volumes_;
};
