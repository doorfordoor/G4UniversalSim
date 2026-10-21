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
constexpr int kRootSchemaVersion = 1;

enum NtupleId : int {
    kHitsNtuple = 0,
    kEventsNtuple = 1,
    kEdepVolumeNtuple = 2,
    kEdepParticleNtuple = 3,
    kDoseNtuple = 4,
    kFluenceNtuple = 5
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

}  // namespace AnalysisOutput
