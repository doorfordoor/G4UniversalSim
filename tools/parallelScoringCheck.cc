// Roadmap H3-2 component check: the dedicated parallel-scoring entry point.
//
// This test does not run transport. It drives the real ScoringManager,
// DoseScorer, FluenceScorer and OutputManager through the same lifecycle the
// Geant4 sensitive detector would use, and proves the properties the frozen
// contract attaches to ScoreParallelHit (R-COMP):
//
//   1. a parallel hit reaches exactly one enabled dose and one enabled fluence
//      scorer and produces the declared-reference-mass normalisation;
//   2. it never accumulates the per-event Edep and never writes a hits row;
//   3. a mass-world hit through ScoreHit still does both, so the isolation is
//      a property of the routing and not of an unconfigured manager;
//   4. after the OutputManager latched a failure both entries are inert.
//
// Usage: parallelScoringCheck [output-dir]

#include "Output/OutputManager.hh"
#include "ParallelWorld/ParallelScoringDetector.hh"
#include "Output/OutputRecord.hh"
#include "Scoring/ScoringManager.hh"

#include "G4SystemOfUnits.hh"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

int failures = 0;

void Check(bool condition, const std::string& what)
{
    if (condition) {
        std::cout << "ok: " << what << "\n";
    } else {
        ++failures;
        std::cerr << "FAIL: " << what << "\n";
    }
}

bool Close(double a, double b, double tolerance = 1e-9)
{
    const double scale = std::max(std::fabs(a), std::fabs(b));
    if (scale == 0.0) return a == b;
    return std::fabs(a - b) <= tolerance * scale;
}

constexpr double JoulePerMeV = 1.602176634e-13;
constexpr double ReferenceMassKg = 0.0008;
constexpr double ReferenceVolumeMm3 = 800.0;
const std::string ParallelVolumePath = "/ScoringWorld#0/Slab#0";
const std::string ParallelVolumeName = "Slab";

using Row = std::map<std::string, std::string>;

std::vector<Row> ReadCsv(const std::filesystem::path& path)
{
    std::ifstream stream(path);
    if (!stream) throw std::runtime_error("cannot read " + path.string());
    std::string header;
    if (!std::getline(stream, header)) return {};
    std::vector<std::string> columns;
    {
        std::stringstream parts(header);
        std::string column;
        while (std::getline(parts, column, ',')) columns.push_back(column);
    }
    std::vector<Row> rows;
    std::string line;
    while (std::getline(stream, line)) {
        if (line.empty()) continue;
        Row row;
        std::stringstream cells(line);
        std::string cell;
        std::size_t index = 0;
        while (std::getline(cells, cell, ',')) {
            if (index < columns.size()) row[columns[index]] = cell;
            ++index;
        }
        rows.push_back(std::move(row));
    }
    return rows;
}

std::vector<std::filesystem::path> Matching(const std::filesystem::path& dir,
                                            const std::string& prefix)
{
    std::vector<std::filesystem::path> found;
    if (!std::filesystem::exists(dir)) return found;
    for (const auto& entry : std::filesystem::directory_iterator(dir)) {
        const auto name = entry.path().filename().string();
        if (name.rfind(prefix, 0) == 0 && entry.path().extension() == ".csv") {
            found.push_back(entry.path());
        }
    }
    return found;
}

Row SingleRow(const std::filesystem::path& directory, const std::string& prefix,
              const std::string& volumePath, const std::string& what)
{
    for (const auto& path : Matching(directory, prefix)) {
        for (const Row& row : ReadCsv(path)) {
            const auto found = row.find("volume_path");
            if (found != row.end() && found->second == volumePath) return row;
        }
    }
    throw std::runtime_error(what + ": no row for " + volumePath);
}

double Number(const Row& row, const std::string& key)
{
    const auto found = row.find(key);
    if (found == row.end()) throw std::runtime_error("missing column " + key);
    return std::stod(found->second);
}

HitRecord MakeHit(const std::string& volumePath, const std::string& volumeName, double edepMeV,
                  double stepLengthMm, int eventId)
{
    HitRecord record;
    record.runID = 0;
    record.eventID = eventId;
    record.trackID = 1;
    record.parentID = 0;
    record.particleName = "proton";
    record.edep = edepMeV * MeV;
    record.ndep = 0.0;
    record.stepLength = stepLengthMm * mm;
    record.kineticEnergy = 10.0 * MeV;
    record.weight = 1.0;
    record.volumeName = volumeName;
    record.doseVolumePath = volumePath;
    // Geant4 mass unit: DoseScorer divides by ScalarUnit(kg) when writing kg.
    record.doseMass = ReferenceMassKg * kg;
    record.fluenceVolume = ReferenceVolumeMm3 * mm * mm * mm;
    record.meanKineticEnergy = 10.0 * MeV;
    record.processName = "parallel_world_step";
    return record;
}

void ParallelEntryOnly(std::filesystem::path root)
{
    OutputManager output;
    output.SetOutputDir(root.string());
    output.SetRunId(0);
    output.SetThreadId(0);
    output.SetFormat(OutputManager::Format::Csv);

    ScoringManager manager;
    manager.SetOutputManager(&output);
    manager.Enable(true);
    manager.EnableHitOutput(true);
    manager.EnableEventEdepOutput(true);
    manager.EnableEdepScoring(false);
    manager.EnableDoseScoring(true);
    manager.EnableFluenceScoring(true);
    manager.SetAutoCreateDefaultScorers(true);

    manager.BeginRun(0);
    manager.BeginEvent(1);
    manager.ScoreParallelHit(MakeHit(ParallelVolumePath, ParallelVolumeName, 10.0, 0.5, 1));
    Check(Close(manager.GetCurrentEventRawEdep(), 0.0),
          "ScoreParallelHit does not accumulate raw Edep");
    Check(Close(manager.GetCurrentEventWeightedEdep(), 0.0),
          "ScoreParallelHit does not accumulate weighted Edep");
    manager.EndEvent(1);
    manager.EndRun(0);
    manager.WriteAll();
    output.Flush();
    output.Close();

    // The per-event file still exists (EndEvent is the normal lifecycle) but the
    // row must be zero; the hits file must not be created at all.
    const auto eventFiles = Matching(root, "event_edep");
    Check(eventFiles.size() == 1, "event_edep file is written by the normal event lifecycle");
    if (eventFiles.size() == 1) {
        const auto rows = ReadCsv(eventFiles.front());
        Check(rows.size() == 1, "one event row for one event (rows=" + std::to_string(rows.size()) + ")");
        if (rows.size() == 1) {
            Check(Close(Number(rows.front(), "raw_edep_MeV"), 0.0), "event raw edep is zero");
            Check(Close(Number(rows.front(), "weighted_edep_MeV"), 0.0), "event weighted edep is zero");
        }
    }
    Check(Matching(root, "hits_").empty(), "parallel hits never create a hits file");

    const Row dose = SingleRow(root, "dose_volume_summary", ParallelVolumePath, "dose");
    Check(Close(Number(dose, "mass_kg"), ReferenceMassKg), "dose row uses the declared reference mass");
    Check(Close(Number(dose, "weighted_edep_MeV"), 10.0), "dose row carries exactly one ghost step");
    Check(Close(Number(dose, "weighted_dose_Gy"), 10.0 * JoulePerMeV / ReferenceMassKg),
          "dose normalisation uses the declared reference mass");
    Check(Close(Number(dose, "n_events"), 1.0), "dose statistics count the event once");

    const Row fluence = SingleRow(root, "fluence_volume_summary", ParallelVolumePath, "fluence");
    Check(Close(Number(fluence, "volume_mm3"), ReferenceVolumeMm3),
          "fluence row uses the declared reference volume");
    Check(Close(Number(fluence, "weighted_fluence_mm-2"), 0.5 / ReferenceVolumeMm3),
          "fluence normalisation uses the declared reference volume");
}

void MassEntryStillCounts(std::filesystem::path root)
{
    OutputManager output;
    output.SetOutputDir(root.string());
    output.SetRunId(1);
    output.SetThreadId(0);
    output.SetFormat(OutputManager::Format::Csv);

    ScoringManager manager;
    manager.SetOutputManager(&output);
    manager.Enable(true);
    manager.EnableHitOutput(true);
    manager.EnableEventEdepOutput(true);
    manager.EnableEdepScoring(false);
    manager.EnableDoseScoring(true);

    manager.BeginRun(1);
    manager.BeginEvent(2);
    manager.ScoreHit(MakeHit("/world_0/MassSlab#0", "MassSlab", 4.0, 0.25, 2));
    Check(Close(manager.GetCurrentEventRawEdep(), 4.0),
          "ScoreHit still accumulates the mass-world Edep");
    manager.EndEvent(2);
    manager.EndRun(1);
    manager.WriteAll();
    output.Flush();
    output.Close();
    const auto hits = Matching(root, "hits_");
    Check(!hits.empty(), "ScoreHit still writes a hits file");
    if (!hits.empty()) {
        Check(ReadCsv(hits.front()).size() == 1, "hits file carries the mass-world row");
    }
}

void LatchedFailureIsInert(std::filesystem::path root)
{
    OutputManager output;
    output.SetOutputDir(root.string());
    output.SetRunId(2);
    output.SetThreadId(0);
    output.SetFormat(OutputManager::Format::Csv);

    ScoringManager manager;
    manager.SetOutputManager(&output);
    manager.Enable(true);
    manager.EnableDoseScoring(true);
    manager.EnableFluenceScoring(true);
    manager.SetAutoCreateDefaultScorers(true);

    manager.BeginRun(2);
    manager.BeginEvent(3);
    output.RecordOutputFailure("scoring_parallel", "injected failure", 2);
    manager.ScoreParallelHit(MakeHit(ParallelVolumePath, ParallelVolumeName, 1.0, 0.1, 3));
    manager.ScoreHit(MakeHit("/world_0/MassSlab#0", "MassSlab", 1.0, 0.1, 3));
    Check(Close(manager.GetCurrentEventRawEdep(), 0.0),
          "both entries are inert after the output manager latched a failure");
    Check(Matching(root, "hits_").empty(), "no hits are written after the latched failure");
    manager.EndEvent(3);
    manager.EndRun(2);
    manager.WriteAll();
    output.Flush();
    output.Close();
}

void MissingThreadManagerLatches()
{
    OutputManager output;
    parallel_world::ParallelScoringDetector::ReportMissingThreadManager(&output);
    Check(output.HasOutputFailure(), "a missing thread-local manager latches a shared output failure");
    const auto failure = output.GetOutputFailure();
    Check(failure.stage == "parallel_world_scoring",
          "the latched failure carries the parallel_world_scoring stage");
    Check(failure.message.find("thread-local ScoringManager") != std::string::npos,
          "the latched failure explains the missing thread binding");
}

}  // namespace

int main(int argc, char** argv)
{
    try {
        const std::filesystem::path root =
            argc > 1 ? std::filesystem::path(argv[1])
                     : std::filesystem::temp_directory_path() / "g4usim-h3-component";
        std::filesystem::remove_all(root);
        std::filesystem::create_directories(root);
        ParallelEntryOnly(root / "parallel_entry");
        MassEntryStillCounts(root / "mass_entry");
        LatchedFailureIsInert(root / "latched_failure");
        MissingThreadManagerLatches();
        if (failures != 0) {
            std::cerr << failures << " component check(s) failed\n";
            return 1;
        }
        std::cout << "PASS: H3-2 component checks (dedicated parallel routing, R-COMP); output in " << root
                  << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: component check aborted: " << error.what() << "\n";
        return 2;
    }
}
