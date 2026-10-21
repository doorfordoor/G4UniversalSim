#pragma once

// ROOT output layer built on Geant4's analysis category (G4AnalysisManager).
//
// One ROOT file is produced per run (g4usim.root, g4usim_r1.root, ...).
// Histograms and ntuples filled on worker threads are merged into that single
// file by Geant4 (histogram merging + ntuple merging), so no per-thread files
// or manual merge step are needed.
//
// All functions operate on the calling thread's G4AnalysisManager instance and
// are no-ops while no file is open on that thread.

#include <string>

struct HitRecord;
struct EventEdepRecord;

namespace AnalysisOutput {

// Version of the ROOT object layout below. Bump on any column/object change.
// v2: added the "mesh" ntuple (Geant4 command-based scoring meshes).
// v3: added the "let" ntuple (track-/dose-averaged LET).
constexpr int kRootSchemaVersion = 3;

enum NtupleId : int {
    kHitsNtuple = 0,
    kEventsNtuple = 1,
    kEdepVolumeNtuple = 2,
    kEdepParticleNtuple = 3,
    kDoseNtuple = 4,
    kFluenceNtuple = 5,
    kMeshNtuple = 6,
    kLetNtuple = 7
};

enum H1Id : int {
    kEdepRawH1 = 0,
    kEdepWeightedH1 = 1
};

struct H1Binning {
    int bins = 200;
    double min = 0.0;   // Geant4 internal energy units (MeV)
    double max = 10.0;
};

// Book objects on first use for this thread, apply current binning, open file.
void BeginRun(const std::string& filePath, const H1Binning& raw, const H1Binning& weighted);
// Write and close the file if this thread opened one. Returns true if closed.
bool EndRun();
bool IsOpen();

void FillHit(const HitRecord& record, int threadId);
void FillEvent(const EventEdepRecord& record, int threadId);
void FillEdepHistograms(bool fillRaw, double rawMeV, bool fillWeighted, double weightedMeV);
void FillEdepSummary(bool byVolume, int runId, int threadId, const std::string& name,
                     double rawMeV, double weightedMeV);
void FillDose(int runId, int threadId, const std::string& volumePath, const std::string& volumeName,
              double massKg, double rawEdepMeV, double weightedEdepMeV,
              double rawDoseGy, double weightedDoseGy);
void FillFluence(int runId, int threadId, const std::string& volumePath, const std::string& volumeName,
                 double volumeMm3, double rawTrackLengthMm, double weightedTrackLengthMm,
                 double rawFluencePerMm2, double weightedFluencePerMm2);

// One row per non-empty scoring-mesh cell per worker thread (worker partial
// results; sum, sum_sq, entries and n_events are additive over threadID).
void FillMeshCell(int runId, int threadId, const std::string& mesh, const std::string& quantity,
                  const std::string& unit, int i0, int i1, int i2, double sum, double sumSquares,
                  int entries, long long events);

// LET sums per sensitive touchable, one row per worker (sums additive over threadID).
void FillLET(int runId, int threadId, const std::string& volumePath, const std::string& volumeName,
             const std::string& particles, long long steps, double sumWLmm, double sumWSlMeV,
             double sumWS2lMeV2PerMm, double letTkeVPerUm, double letDkeVPerUm);

}  // namespace AnalysisOutput
