#include "Output/AnalysisOutput.hh"

#include "Output/OutputRecord.hh"

#include "G4AnalysisManager.hh"
#include "G4Threading.hh"

#include <stdexcept>
#include <string>

namespace {

thread_local bool booked = false;
thread_local bool fileOpen = false;

class NtupleBuilder {
public:
    NtupleBuilder(G4AnalysisManager* manager, int expectedId, const char* name, const char* title)
        : manager_(manager)
    {
        const int id = manager_->CreateNtuple(name, title);
        if (id != expectedId) {
            throw std::runtime_error(std::string("AnalysisOutput: ntuple '") + name + "' got id " +
                                     std::to_string(id) + ", expected " + std::to_string(expectedId));
        }
    }
    NtupleBuilder& I(const char* name) { manager_->CreateNtupleIColumn(name); return *this; }
    NtupleBuilder& D(const char* name) { manager_->CreateNtupleDColumn(name); return *this; }
    NtupleBuilder& S(const char* name) { manager_->CreateNtupleSColumn(name); return *this; }
    void Finish() { manager_->FinishNtuple(); }

private:
    G4AnalysisManager* manager_;
};

void CheckH1(int id, int expected, const char* name)
{
    if (id != expected) {
        throw std::runtime_error(std::string("AnalysisOutput: histogram '") + name + "' got id " +
                                 std::to_string(id) + ", expected " + std::to_string(expected));
    }
}

void Book(G4AnalysisManager* manager, const AnalysisOutput::H1Binning& raw,
          const AnalysisOutput::H1Binning& weighted)
{
    manager->SetVerboseLevel(0);
    manager->SetDefaultFileType("root");
    // Merge worker ntuples into the master's file. Must precede booking and
    // must be set identically on master and workers.
    if (G4Threading::IsMultithreadedApplication()) manager->SetNtupleMerging(true);

    CheckH1(manager->CreateH1("edep_raw", "Event energy deposition (raw);edep [MeV];events",
                              raw.bins, raw.min, raw.max),
            AnalysisOutput::kEdepRawH1, "edep_raw");
    CheckH1(manager->CreateH1("edep_weighted", "Event energy deposition (weighted);edep [MeV];weighted events",
                              weighted.bins, weighted.min, weighted.max),
            AnalysisOutput::kEdepWeightedH1, "edep_weighted");

    // Column names and units mirror the CSV v3 contract (internal units: MeV, mm).
    NtupleBuilder(manager, AnalysisOutput::kHitsNtuple, "hits", "Sensitive-detector hits")
        .I("runID").I("eventID").I("trackID").I("parentID").S("particle")
        .D("edep_MeV").D("ndep_MeV").D("stepLength_mm")
        .D("x0_mm").D("y0_mm").D("z0_mm").D("x1_mm").D("y1_mm").D("z1_mm")
        .D("px").D("py").D("pz").D("kineticEnergy_MeV")
        .S("process").S("volume").D("weight").I("threadID")
        .Finish();
    NtupleBuilder(manager, AnalysisOutput::kEventsNtuple, "events", "Per-event energy deposition")
        .I("runID").I("eventID").D("raw_edep_MeV").D("weighted_edep_MeV").I("threadID")
        .Finish();
    NtupleBuilder(manager, AnalysisOutput::kEdepVolumeNtuple, "edep_volume",
                  "Energy deposition per volume (one row per worker; sum over threadID)")
        .I("runID").I("threadID").S("name").D("raw_edep_MeV").D("weighted_edep_MeV")
        .Finish();
    NtupleBuilder(manager, AnalysisOutput::kEdepParticleNtuple, "edep_particle",
                  "Energy deposition per particle (one row per worker; sum over threadID)")
        .I("runID").I("threadID").S("name").D("raw_edep_MeV").D("weighted_edep_MeV")
        .Finish();
    NtupleBuilder(manager, AnalysisOutput::kDoseNtuple, "dose",
                  "Dose per sensitive touchable (experimental; one row per worker)")
        .I("runID").I("threadID").S("volume_path").S("volume_name").D("mass_kg")
        .D("raw_edep_MeV").D("weighted_edep_MeV").D("raw_dose_Gy").D("weighted_dose_Gy")
        .Finish();
    NtupleBuilder(manager, AnalysisOutput::kFluenceNtuple, "fluence",
                  "Track-length fluence per sensitive touchable (experimental; one row per worker)")
        .I("runID").I("threadID").S("volume_path").S("volume_name").D("volume_mm3")
        .D("raw_track_length_mm").D("weighted_track_length_mm")
        .D("raw_fluence_mm-2").D("weighted_fluence_mm-2")
        .Finish();
    NtupleBuilder(manager, AnalysisOutput::kMeshNtuple, "mesh",
                  "Geant4 scoring-mesh cells (/score/), one row per worker; sum columns over threadID")
        .I("runID").I("threadID").S("mesh").S("quantity").S("unit").I("i0").I("i1").I("i2")
        .D("sum").D("sum_sq").I("entries").D("n_events")
        .Finish();
}

// Small helper so fill code reads as a column list.
class RowFiller {
public:
    RowFiller(G4AnalysisManager* manager, int ntupleId) : manager_(manager), ntupleId_(ntupleId) {}
    RowFiller& I(int value) { manager_->FillNtupleIColumn(ntupleId_, column_++, value); return *this; }
    RowFiller& D(double value) { manager_->FillNtupleDColumn(ntupleId_, column_++, value); return *this; }
    RowFiller& S(const std::string& value) { manager_->FillNtupleSColumn(ntupleId_, column_++, value); return *this; }
    void Add() { manager_->AddNtupleRow(ntupleId_); }

private:
    G4AnalysisManager* manager_;
    int ntupleId_;
    int column_ = 0;
};

}  // namespace

namespace AnalysisOutput {

void BeginRun(const std::string& filePath, const H1Binning& raw, const H1Binning& weighted)
{
    if (raw.bins <= 0 || !(raw.max > raw.min) || weighted.bins <= 0 || !(weighted.max > weighted.min)) {
        throw std::runtime_error("AnalysisOutput: invalid edep histogram binning");
    }
    auto* manager = G4AnalysisManager::Instance();
    if (!booked) {
        Book(manager, raw, weighted);
        booked = true;
    } else {
        manager->SetH1(kEdepRawH1, raw.bins, raw.min, raw.max);
        manager->SetH1(kEdepWeightedH1, weighted.bins, weighted.min, weighted.max);
    }
    if (!manager->OpenFile(filePath)) {
        throw std::runtime_error("AnalysisOutput: cannot open ROOT file '" + filePath + "'");
    }
    fileOpen = true;
}

bool EndRun()
{
    if (!fileOpen) return false;
    fileOpen = false;
    auto* manager = G4AnalysisManager::Instance();
    const bool written = manager->Write();
    const bool closed = manager->CloseFile();
    if (!written || !closed) {
        throw std::runtime_error("AnalysisOutput: failed to write/close ROOT file");
    }
    return true;
}

bool IsOpen()
{
    return fileOpen;
}

void FillHit(const HitRecord& r, int threadId)
{
    if (!fileOpen) return;
    RowFiller(G4AnalysisManager::Instance(), kHitsNtuple)
        .I(r.runID).I(r.eventID).I(r.trackID).I(r.parentID).S(r.particleName)
        .D(r.edep).D(r.ndep).D(r.stepLength)
        .D(r.x0).D(r.y0).D(r.z0).D(r.x1).D(r.y1).D(r.z1)
        .D(r.px).D(r.py).D(r.pz).D(r.kineticEnergy)
        .S(r.processName).S(r.volumeName).D(r.weight).I(threadId)
        .Add();
}

void FillEvent(const EventEdepRecord& r, int threadId)
{
    if (!fileOpen) return;
    RowFiller(G4AnalysisManager::Instance(), kEventsNtuple)
        .I(r.runID).I(r.eventID).D(r.rawEdep).D(r.weightedEdep).I(threadId)
        .Add();
}

void FillEdepHistograms(bool fillRaw, double rawMeV, bool fillWeighted, double weightedMeV)
{
    if (!fileOpen) return;
    auto* manager = G4AnalysisManager::Instance();
    if (fillRaw) manager->FillH1(kEdepRawH1, rawMeV);
    if (fillWeighted) manager->FillH1(kEdepWeightedH1, weightedMeV);
}

void FillEdepSummary(bool byVolume, int runId, int threadId, const std::string& name,
                     double rawMeV, double weightedMeV)
{
    if (!fileOpen) return;
    RowFiller(G4AnalysisManager::Instance(), byVolume ? kEdepVolumeNtuple : kEdepParticleNtuple)
        .I(runId).I(threadId).S(name).D(rawMeV).D(weightedMeV)
        .Add();
}

void FillDose(int runId, int threadId, const std::string& volumePath, const std::string& volumeName,
              double massKg, double rawEdepMeV, double weightedEdepMeV,
              double rawDoseGy, double weightedDoseGy)
{
    if (!fileOpen) return;
    RowFiller(G4AnalysisManager::Instance(), kDoseNtuple)
        .I(runId).I(threadId).S(volumePath).S(volumeName).D(massKg)
        .D(rawEdepMeV).D(weightedEdepMeV).D(rawDoseGy).D(weightedDoseGy)
        .Add();
}

void FillFluence(int runId, int threadId, const std::string& volumePath, const std::string& volumeName,
                 double volumeMm3, double rawTrackLengthMm, double weightedTrackLengthMm,
                 double rawFluencePerMm2, double weightedFluencePerMm2)
{
    if (!fileOpen) return;
    RowFiller(G4AnalysisManager::Instance(), kFluenceNtuple)
        .I(runId).I(threadId).S(volumePath).S(volumeName).D(volumeMm3)
        .D(rawTrackLengthMm).D(weightedTrackLengthMm)
        .D(rawFluencePerMm2).D(weightedFluencePerMm2)
        .Add();
}

void FillMeshCell(int runId, int threadId, const std::string& mesh, const std::string& quantity,
                  const std::string& unit, int i0, int i1, int i2, double sum, double sumSquares,
                  int entries, long long events)
{
    if (!fileOpen) return;
    RowFiller(G4AnalysisManager::Instance(), kMeshNtuple)
        .I(runId).I(threadId).S(mesh).S(quantity).S(unit).I(i0).I(i1).I(i2)
        .D(sum).D(sumSquares).I(entries).D(static_cast<double>(events))
        .Add();
}

}  // namespace AnalysisOutput
