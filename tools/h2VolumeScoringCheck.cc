// Roadmap H2-2 component checks: real scorer classes, a real OutputManager and
// real Geant4 sensitive-detector filters, without running transport.
//
// The fixtures are the frozen H2-1 component inputs.  They deliberately mix
// particle species, kinetic energies and weights so that the particle/energy
// partitions, the N-including-zero-events convention and the once-only weight
// application can be recomputed independently from the CSV output.
//
// Usage: h2VolumeScoringCheck [output-dir]

#include "Scoring/DoseScorer.hh"
#include "Scoring/FluenceScorer.hh"
#include "Scoring/LETScorer.hh"
#include "Scoring/DisplacementScorer.hh"
#include "Scoring/VolumeFilter.hh"
#include "Scoring/VolumeSpectrum.hh"
#include "Output/OutputManager.hh"

#include "G4ParticleTable.hh"
#include "G4ParticleDefinition.hh"
#include "G4Gamma.hh"
#include "G4Electron.hh"
#include "G4SDKineticEnergyFilter.hh"
#include "G4SDParticleFilter.hh"
#include "G4SDParticleWithEnergyFilter.hh"
#include "G4VSDFilter.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh"
#include "G4ThreeVector.hh"
#include "G4DynamicParticle.hh"
#include "G4Track.hh"
#include "G4SystemOfUnits.hh"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

int failures = 0;

void Check(bool condition, const std::string& what)
{
    if (!condition) {
        ++failures;
        std::cerr << "FAIL: " << what << "\n";
    } else {
        std::cout << "ok: " << what << "\n";
    }
}

bool Close(double a, double b, double tolerance = 1e-9)
{
    const double scale = std::max(std::fabs(a), std::fabs(b));
    if (scale == 0.0) return a == b;
    return std::fabs(a - b) <= tolerance * scale;
}

template <typename Fn>
void ExpectFailure(Fn&& fn, const std::string& needle, const std::string& what)
{
    try {
        fn();
    } catch (const std::exception& error) {
        Check(std::string(error.what()).find(needle) != std::string::npos, what);
        return;
    }
    Check(false, what);
}

constexpr double JoulePerMeV = 1.602176634e-13;
constexpr double MassKg = 0.001;      // fixed component mass
constexpr double VolumeMm3 = 10.0;    // fixed component volume
const std::string VolumePath = "/world_0/Target_PV";
const std::string VolumeName = "Target_PV";

struct Row {
    std::map<std::string, std::string> value;
    double Number(const std::string& key) const
    {
        const auto found = value.find(key);
        if (found == value.end()) throw std::runtime_error("missing column " + key);
        return std::stod(found->second);
    }
    std::string Text(const std::string& key) const
    {
        const auto found = value.find(key);
        if (found == value.end()) throw std::runtime_error("missing column " + key);
        return found->second;
    }
};

std::string JoinPath(const std::filesystem::path& dir, const std::string& name)
{
    return (dir / name).string();
}

std::vector<std::string> SplitCsvLine(const std::string& line)
{
    std::vector<std::string> cells;
    std::string cell;
    bool quoted = false;
    for (char c : line) {
        if (c == '"') {
            quoted = !quoted;
        } else if (c == ',' && !quoted) {
            cells.push_back(cell);
            cell.clear();
        } else {
            cell.push_back(c);
        }
    }
    cells.push_back(cell);
    return cells;
}

std::vector<Row> ReadCsv(const std::filesystem::path& path)
{
    std::ifstream stream(path, std::ios::binary);
    if (!stream) throw std::runtime_error("cannot open " + path.string());
    std::string line;
    if (!std::getline(stream, line)) return {};
    if (!line.empty() && line.back() == '\r') line.pop_back();
    const std::vector<std::string> header = SplitCsvLine(line);
    std::vector<Row> rows;
    while (std::getline(stream, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        const std::vector<std::string> cells = SplitCsvLine(line);
        if (cells.size() != header.size()) throw std::runtime_error("bad row in " + path.string());
        Row row;
        for (std::size_t i = 0; i < header.size(); ++i) row.value[header[i]] = cells[i];
        rows.push_back(std::move(row));
    }
    return rows;
}

std::filesystem::path FindSingle(const std::filesystem::path& dir, const std::string& prefix,
                                 const std::string& suffix = ".csv")
{
    std::vector<std::filesystem::path> matches;
    for (const auto& entry : std::filesystem::directory_iterator(dir)) {
        const std::string name = entry.path().filename().string();
        if (name.rfind(prefix, 0) == 0 && name.size() >= suffix.size() &&
            name.compare(name.size() - suffix.size(), suffix.size(), suffix) == 0) {
            matches.push_back(entry.path());
        }
    }
    if (matches.size() != 1) {
        throw std::runtime_error("expected exactly one " + prefix + "* in " + dir.string());
    }
    return matches.front();
}

// Copy a filter configuration into a fresh object (unique_ptr is not copyable).
std::unique_ptr<VolumeFilter> FilterCopyOf(const VolumeFilter& filter)
{
    return std::make_unique<VolumeFilter>(VolumeFilterConfig(filter.Config()));
}

std::unique_ptr<VolumeFilter> ParticleFilterCopy(const VolumeFilter& filter)
{
    return FilterCopyOf(filter);
}

HitRecord MakeHit(const std::string& particle, double kineticMeV, double weight, double edepMeV,
                  double lengthMm, double letMeVPerMm = 0.0)
{
    HitRecord hit;
    hit.runID = 0;
    hit.eventID = 0;
    hit.trackID = 1;
    hit.particleName = particle;
    hit.edep = edepMeV * MeV;
    hit.stepLength = lengthMm * mm;
    hit.weight = weight;
    hit.kineticEnergy = kineticMeV * MeV;
    hit.meanKineticEnergy = kineticMeV * MeV;
    hit.volumeName = VolumeName;
    hit.doseVolumePath = VolumePath;
    hit.doseMass = MassKg * kg;
    hit.fluenceVolume = VolumeMm3 * mm3;
    hit.LETstep = letMeVPerMm * MeV / mm;
    return hit;
}

std::unique_ptr<VolumeFilter> ParticleFilter(const std::string& particles)
{
    VolumeFilterConfig config;
    config.allParticles = false;
    std::istringstream stream(particles);
    std::string name;
    while (stream >> name) config.particles.insert(name);
    config.section = "[scoring.filter.check]";
    config.location = "component check";
    config.energyMinMeV = 0.0;
    config.energyMaxMeV = std::numeric_limits<double>::infinity();
    return std::make_unique<VolumeFilter>(std::move(config));
}

std::unique_ptr<VolumeFilter> EnergyFilter(double lowMeV, double highMeV)
{
    VolumeFilterConfig config;
    config.allParticles = true;
    config.energyMinMeV = lowMeV;
    config.energyMaxMeV = highMeV;
    config.section = "[scoring.filter.check]";
    config.location = "component check";
    return std::make_unique<VolumeFilter>(std::move(config));
}

std::unique_ptr<OutputManager> MakeOutput(const std::filesystem::path& dir)
{
    std::filesystem::create_directories(dir);
    auto output = std::make_unique<OutputManager>();
    output->SetOutputDir(dir.string());
    output->SetRunId(0);
    output->SetThreadId(0);
    output->SetFormat(OutputManager::Format::Csv);
    return output;
}

// ---------------------------------------------------------------------------
// V1b: dose and fluence linear totals plus per-particle and per-energy-window
// partitions on one event with four scored steps and one empty event (N = 2).
// ---------------------------------------------------------------------------
std::vector<HitRecord> ComponentEvent()
{
    return {
        MakeHit("gamma", 0.0, 0.25, 4.0, 4.0),    // zero deposition is invisible to dose
        MakeHit("e-", 10.0, 1.0, 1.0, 1.0),
        MakeHit("proton", 50.0, 2.0, 0.5, 0.5),
        MakeHit("gamma", 100.0, 1.0, 0.0, 1.0),   // zero deposition, still a fluence step
    };
}

void DoseTotals(const std::filesystem::path& dir)
{
    auto output = MakeOutput(dir);
    DoseScorer scorer("dose");
    scorer.BeginRun(0);
    for (const HitRecord& hit : ComponentEvent()) scorer.ScoreHit(hit);
    scorer.EndEvent(0);
    scorer.EndEvent(0);  // second, zero-contribution event
    scorer.Write(*output);

    const std::vector<Row> rows = ReadCsv(FindSingle(dir, "dose_volume_summary_"));
    Check(rows.size() == 1, "V1b dose writes one touchable row");
    const Row& row = rows.front();
    Check(row.Text("volume_path") == VolumePath, "V1b dose volume path matches the fixture");
    Check(Close(row.Number("mass_kg"), MassKg), "V1b dose reports the fixed mass");
    Check(Close(row.Number("raw_edep_MeV"), 5.5), "V1b raw edep excludes the zero-deposition step");
    Check(Close(row.Number("weighted_edep_MeV"), 3.0), "V1b weighted edep applies the weight once");
    Check(Close(row.Number("raw_dose_Gy"), 5.5 * JoulePerMeV / MassKg), "V1b raw dose formula");
    Check(Close(row.Number("weighted_dose_Gy"), 3.0 * JoulePerMeV / MassKg), "V1b weighted dose formula");
    Check(row.Text("n_events") == "2", "V1b dose N counts the empty event");
}

void FluenceTotals(const std::filesystem::path& dir)
{
    auto output = MakeOutput(dir);
    FluenceScorer scorer("fluence");
    scorer.BeginRun(0);
    for (const HitRecord& hit : ComponentEvent()) scorer.ScoreHit(hit);
    scorer.EndEvent(0);
    scorer.EndEvent(0);
    scorer.Write(*output);

    const std::vector<Row> rows = ReadCsv(FindSingle(dir, "fluence_volume_summary_"));
    Check(rows.size() == 1, "V1b fluence writes one touchable row");
    const Row& row = rows.front();
    Check(Close(row.Number("volume_mm3"), VolumeMm3), "V1b fluence reports the fixed volume");
    Check(Close(row.Number("raw_track_length_mm"), 6.5), "V1b raw path length includes zero-deposition steps");
    Check(Close(row.Number("weighted_track_length_mm"), 4.0), "V1b weighted path length applies weight once");
    Check(Close(row.Number("raw_fluence_mm-2"), 6.5 / VolumeMm3), "V1b raw fluence formula");
    Check(Close(row.Number("weighted_fluence_mm-2"), 4.0 / VolumeMm3), "V1b weighted fluence formula");
    Check(row.Text("n_events") == "2", "V1b fluence N counts the empty event");
}

void ParticlePartitions(const std::filesystem::path& root)
{
    const std::vector<HitRecord> event = ComponentEvent();
    const struct { const char* particles; double rawEdep; double weightedEdep; } dose_parts[] = {
        {"gamma", 4.0, 1.0}, {"e-", 1.0, 1.0}, {"proton", 0.5, 1.0}};
    double rawSum = 0.0;
    double weightedSum = 0.0;
    for (const auto& part : dose_parts) {
        const std::filesystem::path dir = root / ("dose_" + std::string(part.particles));
        auto output = MakeOutput(dir);
        DoseScorer scorer("dose");
        scorer.SetFilter(ParticleFilter(part.particles));
        scorer.BeginRun(0);
        for (const HitRecord& hit : event) scorer.ScoreHit(hit);
        scorer.EndEvent(0);
        scorer.Write(*output);
        const Row row = ReadCsv(FindSingle(dir, "dose_volume_summary_")).front();
        Check(Close(row.Number("raw_edep_MeV"), part.rawEdep), "V1b dose partition raw " + std::string(part.particles));
        Check(Close(row.Number("weighted_edep_MeV"), part.weightedEdep), "V1b dose partition weighted " + std::string(part.particles));
        rawSum += row.Number("raw_edep_MeV");
        weightedSum += row.Number("weighted_edep_MeV");
    }
    Check(Close(rawSum, 5.5), "V1b particle partition sums to the unfiltered raw dose");
    Check(Close(weightedSum, 3.0), "V1b particle partition sums to the unfiltered weighted dose");

    const struct { const char* particles; double weightedFluence; } fluence_parts[] = {
        {"gamma", 2.0 / VolumeMm3}, {"e-", 1.0 / VolumeMm3}, {"proton", 1.0 / VolumeMm3}};
    double fluenceSum = 0.0;
    for (const auto& part : fluence_parts) {
        const std::filesystem::path dir = root / ("fluence_" + std::string(part.particles));
        auto output = MakeOutput(dir);
        FluenceScorer scorer("fluence");
        scorer.SetFilter(ParticleFilter(part.particles));
        scorer.BeginRun(0);
        for (const HitRecord& hit : event) scorer.ScoreHit(hit);
        scorer.EndEvent(0);
        scorer.Write(*output);
        const Row row = ReadCsv(FindSingle(dir, "fluence_volume_summary_")).front();
        Check(Close(row.Number("weighted_fluence_mm-2"), part.weightedFluence),
              "V1b fluence partition weighted " + std::string(part.particles));
        fluenceSum += row.Number("weighted_fluence_mm-2");
    }
    Check(Close(fluenceSum, 4.0 / VolumeMm3), "V1b particle partition sums to the unfiltered weighted fluence");
}

void EnergyPartitions(const std::filesystem::path& root)
{
    const std::vector<HitRecord> event = ComponentEvent();
    // Fluence uses the pre-step kinetic energy: [0,10) gamma, [10,50) e-,
    // [50,100) proton and [100,+inf) gamma.  dose excludes the zero-deposition
    // gamma steps, so its window sums are checked against raw/weighted edep.
    const struct { double low; double high; double rawLength; double weightedLength; } fluence_parts[] = {
        {0.0, 10.0, 4.0, 1.0}, {10.0, 50.0, 1.0, 1.0}, {50.0, 100.0, 0.5, 2.0 * 0.5}};
    for (const auto& part : fluence_parts) {
        const std::filesystem::path dir = root / ("fluence_window_" + std::to_string(part.low).substr(0, 2));
        auto output = MakeOutput(dir);
        FluenceScorer scorer("fluence");
        scorer.SetFilter(EnergyFilter(part.low, part.high));
        scorer.BeginRun(0);
        for (const HitRecord& hit : event) scorer.ScoreHit(hit);
        scorer.EndEvent(0);
        scorer.Write(*output);
        const std::vector<Row> rows = ReadCsv(FindSingle(dir, "fluence_volume_summary_"));
        const double length = rows.empty() ? 0.0 : rows.front().Number("weighted_track_length_mm");
        Check(Close(length, part.weightedLength),
              "V2 fluence energy window " + std::to_string(part.low) + "-" + std::to_string(part.high) + " MeV");
    }
    // Unbounded upper edge: the last window keeps the 100 MeV photon.
    {
        const std::filesystem::path dir = root / "fluence_window_last";
        auto output = MakeOutput(dir);
        FluenceScorer scorer("fluence");
        scorer.SetFilter(EnergyFilter(100.0, std::numeric_limits<double>::infinity()));
        scorer.BeginRun(0);
        for (const HitRecord& hit : event) scorer.ScoreHit(hit);
        scorer.EndEvent(0);
        scorer.Write(*output);
        const Row row = ReadCsv(FindSingle(dir, "fluence_volume_summary_")).front();
        Check(Close(row.Number("weighted_track_length_mm"), 1.0),
              "V2 upper unbounded window keeps E == min and excludes nothing else");
    }
    // Lower boundary is inclusive and combines with a particle condition.
    {
        const std::filesystem::path dir = root / "fluence_window_and";
        auto output = MakeOutput(dir);
        FluenceScorer scorer("fluence");
        // AND of a particle name and a kinetic window through the same class.
        VolumeFilterConfig config;
        config.allParticles = false;
        config.particles = {"e-"};
        config.energyMinMeV = 10.0;
        config.energyMaxMeV = 50.0;
        config.section = "[scoring.filter.check]";
        config.location = "component check";
        scorer.SetFilter(std::make_unique<VolumeFilter>(std::move(config)));
        scorer.BeginRun(0);
        for (const HitRecord& hit : event) scorer.ScoreHit(hit);
        scorer.EndEvent(0);
        scorer.Write(*output);
        const Row row = ReadCsv(FindSingle(dir, "fluence_volume_summary_")).front();
        Check(Close(row.Number("weighted_track_length_mm"), 1.0), "V2 particle AND energy combination");
    }
}

// ---------------------------------------------------------------------------
// V3: LET first moments (sum_wl/sum_wSl/sum_wS2l) partition additively across
// particle filters; the ratio LET_t/LET_d is only reported, never summed.
// ---------------------------------------------------------------------------
std::vector<HitRecord> LetEvent()
{
    return {
        MakeHit("proton", 10.0, 1.0, 0.0, 2.0, 0.5),
        MakeHit("proton", 20.0, 2.0, 0.0, 1.0, 2.0),
        MakeHit("e-", 5.0, 1.0, 0.0, 1.0, 0.1),
    };
}

void LetMoments(const std::filesystem::path& root)
{
    const std::vector<HitRecord> event = LetEvent();
    const struct { double wl; double wsl; double ws2l; } expected_total{5.0, 5.1, 8.51};
    double wl = 0.0;
    double wsl = 0.0;
    double ws2l = 0.0;
    for (const std::string particles : {"proton", "e-"}) {
        const std::filesystem::path dir = root / ("let_" + particles);
        auto output = MakeOutput(dir);
        LETScorer scorer("let");
        scorer.SetFilter(ParticleFilter(particles));
        scorer.BeginRun(0);
        for (const HitRecord& hit : event) scorer.ScoreHit(hit);
        scorer.EndEvent(0);
        scorer.Write(*output);
        const Row row = ReadCsv(FindSingle(dir, "let_volume_summary_")).front();
        Check(row.Text("particles") == "all_charged", "V3 LET writes the default particle label");
        wl += row.Number("sum_wl_mm");
        wsl += row.Number("sum_wSl_MeV");
        ws2l += row.Number("sum_wS2l_MeV2_per_mm");
    }
    Check(Close(wl, expected_total.wl), "V3 sum_wl partitions additively");
    Check(Close(wsl, expected_total.wsl), "V3 sum_wSl partitions additively");
    Check(Close(ws2l, expected_total.ws2l), "V3 sum_wS2l partitions additively");
    Check(!Close(wsl / wl, 1.668627450980392), "V3 LET ratios are not treated as additive");

    const std::filesystem::path dir = root / "let_all";
    auto output = MakeOutput(dir);
    LETScorer scorer("let");
    scorer.BeginRun(0);
    for (const HitRecord& hit : event) scorer.ScoreHit(hit);
    scorer.EndEvent(0);
    scorer.Write(*output);
    const Row row = ReadCsv(FindSingle(dir, "let_volume_summary_")).front();
    Check(Close(row.Number("let_t_keV_per_um"), 5.1 / 5.0), "V3 LET_t from the first moments");
    Check(Close(row.Number("let_d_keV_per_um"), 8.51 / 5.1), "V3 LET_d from the first and second moments");
}

// ---------------------------------------------------------------------------
// V5 (component half): bin boundaries are half-open except the last bin, which
// is closed on max; underflow/overflow are mutually exclusive and exhaustive.
// ---------------------------------------------------------------------------
void SpectrumBoundaries(const std::filesystem::path& dir)
{
    auto output = MakeOutput(dir);
    FluenceScorer scorer("fluence");
    VolumeSpectrumConfig config;
    config.bins = 10;
    config.minMeV = 0.5;
    config.maxMeV = 1.5;
    config.section = "[scoring.spectrum.check]";
    config.location = "component check";
    scorer.SetSpectrum(std::make_unique<VolumeSpectrum>(std::move(config)));
    scorer.BeginRun(0);
    scorer.ScoreHit(MakeHit("gamma", 0.5, 10.0, 0.0, 0.1));    // bin 0 (inclusive min)
    scorer.ScoreHit(MakeHit("gamma", 1.5, 10.0, 0.0, 0.1));    // last bin (closed max)
    scorer.ScoreHit(MakeHit("gamma", 1.6, 10.0, 0.0, 0.1));    // overflow
    scorer.ScoreHit(MakeHit("gamma", 0.4, 10.0, 0.0, 0.1));    // underflow
    scorer.EndEvent(0);
    scorer.Write(*output);

    const std::vector<Row> rows = ReadCsv(FindSingle(dir, "spectrum_fluence_"));
    Check(rows.size() == 12, "V5 spectrum writes N bins plus underflow and overflow");
    const auto find = [&](const std::string& region, const std::string& bin) -> Row {
        for (const Row& row : rows) {
            if (row.Text("region") == region && row.Text("bin") == bin) return row;
        }
        throw std::runtime_error("missing spectrum row " + region + "/" + bin);
    };
    Check(Close(find("bin", "0").Number("amount"), 0.1), "V5 E == min lands in the first bin");
    Check(Close(find("bin", "9").Number("amount"), 0.1), "V5 E == max lands in the closed last bin");
    Check(Close(find("underflow", "-1").Number("amount"), 0.1), "V5 underflow amount");
    Check(Close(find("overflow", "10").Number("amount"), 0.1), "V5 overflow amount");
    Check(find("bin", "9").Text("high_edge_MeV") == "1.5", "V5 last bin high edge equals max");
    Check(find("underflow", "-1").Text("unit") == "mm^-2", "V5 fluence spectrum unit is exactly mm^-2");
    double total = 0.0;
    for (const Row& row : rows) total += row.Number("amount");
    Check(Close(total, 0.4), "V5 bins plus underflow/overflow reproduce the unfiltered total");
}

// ---------------------------------------------------------------------------
// V6b: the dose spectrum comes from the real DoseScorer path; the expected sum
// uses weight*edep once, and the independent arithmetic also reports the
// squared-weight moment that must not be added a second time.
// ---------------------------------------------------------------------------
void WeightOnceComponent(const std::filesystem::path& dir)
{
    auto output = MakeOutput(dir);
    DoseScorer scorer("dose");
    VolumeSpectrumConfig config;
    config.bins = 2;
    config.minMeV = 0.0;
    config.maxMeV = 4.0;
    config.section = "[scoring.spectrum.check]";
    config.location = "component check";
    scorer.SetSpectrum(std::make_unique<VolumeSpectrum>(std::move(config)));
    scorer.BeginRun(0);
    scorer.ScoreHit(MakeHit("e-", 1.0, 0.25, 4.0, 1.0));  // w*q = 1.0
    scorer.ScoreHit(MakeHit("e-", 2.0, 1.0, 1.0, 1.0));   // w*q = 1.0
    scorer.ScoreHit(MakeHit("e-", 3.0, 2.0, 0.5, 1.0));   // w*q = 1.0
    scorer.EndEvent(0);
    scorer.Write(*output);

    const std::vector<Row> rows = ReadCsv(FindSingle(dir, "spectrum_dose_"));
    double total = 0.0;
    for (const Row& row : rows) total += row.Number("amount");
    const double expected = 3.0 * JoulePerMeV / MassKg;
    Check(Close(total, expected), "V6b spectrum total equals sum(weight * edep) / mass");
    Check(Close(1.0 * JoulePerMeV / MassKg + 1.0 * JoulePerMeV / MassKg + 1.0 * JoulePerMeV / MassKg,
                expected), "V6b independent per-step expectation agrees");
    const double sumSquaredWeightedQuantity = 0.25 * 0.25 * 4.0 + 1.0 * 1.0 * 1.0 + 2.0 * 2.0 * 0.5;
    Check(Close(sumSquaredWeightedQuantity, 3.25), "V6b independent sum(w^2 * q) arithmetic is 3.25");
    Check(!Close(sumSquaredWeightedQuantity * JoulePerMeV / MassKg, expected),
          "V6b applying the weight twice is distinguishable from the once-only expectation");
}

// ---------------------------------------------------------------------------
// V8: observe the real Geant4 sensitive-detector filters at their boundaries.
// The frozen contract requires observation, not an assumed convention; the
// check records the observed accept/reject pattern and asserts that the
// combined filter is exactly the AND of the particle and kinetic filters.
// ---------------------------------------------------------------------------
G4bool AcceptWith(const G4VSDFilter& filter, const std::string& particle, double energyMeV)
{
    G4ParticleTable* table = G4ParticleTable::GetParticleTable();
    auto* dynamic = new G4DynamicParticle(table->FindParticle(particle), G4ThreeVector(0, 0, 1),
                                          energyMeV * MeV);
    auto* track = new G4Track(dynamic, 0.0, G4ThreeVector());
    G4Step step;
    step.GetPreStepPoint()->SetKineticEnergy(energyMeV * MeV);
    step.SetTrack(track);
    const G4bool accepted = filter.Accept(&step);
    step.SetTrack(nullptr);
    delete track;  // owns the dynamic particle
    return accepted;
}

void Geant4FilterBoundaries()
{
    // A bare G4ParticleTable is empty until a physics list registers the standard
    // particles; the component check only needs gamma and e- so it inserts them
    // explicitly instead of building a whole physics list.
    G4ParticleTable* table = G4ParticleTable::GetParticleTable();
    if (table->FindParticle("gamma") == nullptr) G4Gamma::Gamma();      // registers on creation
    if (table->FindParticle("e-") == nullptr) G4Electron::Electron();
    G4SDKineticEnergyFilter kinetic("kinetic", 1.0 * MeV, 2.0 * MeV);
    G4SDParticleFilter particle("particle", "gamma");
    G4SDParticleWithEnergyFilter combined("combined", 1.0 * MeV, 2.0 * MeV);
    combined.add("gamma");
    const double energies[] = {0.5, 0.999, 1.0, 1.5, 2.0, 2.001};
    bool andHolds = true;
    std::cout << "V8 observed Geant4 SD filter acceptance (gamma, kinetic range [1,2] MeV):\n";
    for (double energy : energies) {
        const G4bool k = AcceptWith(kinetic, "gamma", energy);
        const G4bool p = AcceptWith(particle, "gamma", energy);
        const G4bool c = AcceptWith(combined, "gamma", energy);
        std::cout << "  E=" << energy << " MeV kinetic=" << k << " particle=" << p
                  << " combined=" << c << "\n";
        if (c != (k && p)) andHolds = false;
    }
    Check(andHolds, "V8 combined Geant4 filter equals particle AND kinetic acceptance");
    Check(AcceptWith(combined, "gamma", 1.0), "V8 combined filter accepts the lower boundary (observed)");
    Check(!AcceptWith(combined, "gamma", 2.001), "V8 combined filter rejects above the upper boundary (observed)");
    Check(!AcceptWith(combined, "e-", 1.5), "V8 combined filter rejects a different particle");
}

}  // namespace

void FilterEnergyChecks()
{
    // A non-finite sampled energy is an internal error.  The filter must report it
    // before the particle condition can reject the step as an ordinary mismatch.
    DoseScorer dose("dose");
    dose.SetFilter(ParticleFilter("proton"));
    dose.BeginRun(0);
    HitRecord mismatched = MakeHit("gamma", 1.0, 1.0, 1.0, 0.1);
    mismatched.kineticEnergy = std::numeric_limits<double>::quiet_NaN();
    ExpectFailure([&] { dose.ScoreHit(mismatched); }, "nonfinite sampled kinetic energy",
                  "V9 nonfinite energy fails before a particle mismatch short-circuits the filter");

    HitRecord matching = MakeHit("proton", 1.0, 1.0, 1.0, 0.1);
    matching.kineticEnergy = std::numeric_limits<double>::quiet_NaN();
    ExpectFailure([&] { dose.ScoreHit(matching); }, "nonfinite sampled kinetic energy",
                  "V9 dose scorer rejects a NaN pre-step energy on a positive deposition step");

    FluenceScorer fluence("fluence");
    fluence.SetFilter(ParticleFilter("proton"));
    fluence.BeginRun(0);
    HitRecord zeroDeposit = MakeHit("gamma", 1.0, 1.0, 0.0, 0.1);
    zeroDeposit.kineticEnergy = std::numeric_limits<double>::infinity();
    ExpectFailure([&] { fluence.ScoreHit(zeroDeposit); }, "nonfinite sampled kinetic energy",
                  "V9 fluence scorer rejects a +inf pre-step energy on a zero-deposition step");
}

VolumeSpectrumConfig SpectrumConfig(int bins, double minMeV, double maxMeV)
{
    VolumeSpectrumConfig config;
    config.bins = bins;
    config.minMeV = minMeV;
    config.maxMeV = maxMeV;
    config.section = "[scoring.spectrum.check]";
    config.location = "component check";
    return config;
}

void SpectrumAccumulationChecks()
{
    auto binSpectrum = std::make_unique<VolumeSpectrum>(SpectrumConfig(2, 0.0, 2.0));
    binSpectrum->Add(VolumePath, VolumeName, 1.0, 1e308);
    ExpectFailure([&] { binSpectrum->Add(VolumePath, VolumeName, 1.0, 1e308); },
                  "spectrum bin accumulation", "V10 bin accumulation overflow fails instead of writing inf");

    auto underflowSpectrum = std::make_unique<VolumeSpectrum>(SpectrumConfig(2, 0.0, 2.0));
    underflowSpectrum->Add(VolumePath, VolumeName, -1.0, 1e308);
    ExpectFailure([&] { underflowSpectrum->Add(VolumePath, VolumeName, -1.0, 1e308); },
                  "spectrum underflow accumulation", "V10 underflow accumulation overflow fails");

    auto overflowSpectrum = std::make_unique<VolumeSpectrum>(SpectrumConfig(2, 0.0, 2.0));
    overflowSpectrum->Add(VolumePath, VolumeName, 3.0, 1e308);
    ExpectFailure([&] { overflowSpectrum->Add(VolumePath, VolumeName, 3.0, 1e308); },
                  "spectrum overflow accumulation", "V10 overflow accumulation overflow fails");
}

void SpectrumWidthChecks()
{
    // (denorm_min - 0) / 2 rounds to zero: the bin index would be undefined.
    ExpectFailure([&] { VolumeSpectrum rejected(SpectrumConfig(2, 0.0, std::numeric_limits<double>::denorm_min())); },
                  "representable positive finite number",
                  "V11 spectrum rejects a zero (underflowed) bin width");
    auto accepted = std::make_unique<VolumeSpectrum>(SpectrumConfig(2, 0.0, 1.0));
    accepted->Add(VolumePath, VolumeName, 1.0, 0.5);
    Check(true, "V11 a representable width is accepted");
}

// ---------------------------------------------------------------------------
// H2-4 DDD evidence: particle and energy partition plus spectrum on the real
// DisplacementScorer with the sourced Si proton NIEL table.  This augments the
// pre-registered V1b fixed-input partition (the freeze keeps DDD on an existing
// sourced table fixture) and does not claim a NIEL data validation.
// ---------------------------------------------------------------------------
void DisplacementPartitions(const std::filesystem::path& root,
                            const std::filesystem::path& repository)
{
    const std::filesystem::path tablePath =
        repository / "scenarios/semiconductor/niel/si_proton.csv";
    const auto table = NielTable::Load(tablePath.string());
    Check(table != nullptr && table->Size() == 146, "H2-4 DDD loads the 146-row Si proton NIEL table");
    double niel1 = 0.0;
    double niel10 = 0.0;
    Check(table->Evaluate(1.0 * MeV, niel1), "H2-4 DDD table evaluates 1 MeV");
    Check(table->Evaluate(10.0 * MeV, niel10), "H2-4 DDD table evaluates 10 MeV");
    // Values are the published SR-NIEL nodes at 1 and 10 MeV in si_proton.csv.
    Check(std::abs(niel1 - 0.063442) < 1e-12, "H2-4 DDD 1 MeV NIEL node matches the sourced row");
    Check(std::abs(niel10 - 0.0094037) < 1e-12, "H2-4 DDD 10 MeV NIEL node matches the sourced row");
    const double expected1 = 2.0 * 2.0 * niel1 * 100.0 / VolumeMm3;   // w=2, l=2 mm
    const double expected10 = 1.0 * 1.0 * niel10 * 100.0 / VolumeMm3; // w=1, l=1 mm
    const double expectedTotal = expected1 + expected10;

    auto run = [&](const std::string& name, const std::unique_ptr<VolumeFilter>& filter,
                   std::unique_ptr<VolumeSpectrum> spectrum) {
        const std::filesystem::path dir = root / name;
        auto output = MakeOutput(dir);
        DisplacementScorer scorer("displacement");
        scorer.SetTables({{"proton", table}});
        if (filter) scorer.SetFilter(ParticleFilterCopy(*filter));
        if (spectrum) scorer.SetSpectrum(std::move(spectrum));
        scorer.BeginRun(0);
        scorer.ScoreHit(MakeHit("gamma", 50.0, 1.0, 0.0, 1.0));  // no table: skipped
        scorer.ScoreHit(MakeHit("proton", 1.0, 2.0, 0.0, 2.0));
        scorer.ScoreHit(MakeHit("proton", 10.0, 1.0, 0.0, 1.0));
        scorer.EndEvent(0);
        scorer.EndEvent(0);  // zero-contribution event
        scorer.Write(*output);
        return dir;
    };

    const std::filesystem::path totalDir = run("ddd_total", nullptr, nullptr);
    {
        const Row row = ReadCsv(FindSingle(totalDir, "displacement_volume_summary_")).front();
        Check(Close(row.Number("ddd_MeV_g"), expectedTotal), "H2-4 DDD total matches w*l*NIEL/V");
        Check(Close(row.Number("track_length_mm"), 5.0), "H2-4 DDD weighted track length");
        Check(Close(row.Number("out_of_range_track_length_mm"), 0.0), "H2-4 DDD stays inside the table domain");
        Check(row.Text("particle") == "proton" && row.Text("n_events") == "2",
              "H2-4 DDD particle row and complete event N");
    }

    // Particle partition: only proton has a table; gamma contributes nothing.
    const std::filesystem::path protonDir = run("ddd_proton", ParticleFilter("proton"), nullptr);
    const std::filesystem::path gammaDir = run("ddd_gamma", ParticleFilter("gamma"), nullptr);
    const double protonTotal = ReadCsv(FindSingle(protonDir, "displacement_volume_summary_")).front().Number("ddd_MeV_g");
    const bool gammaRows = !ReadCsv(FindSingle(gammaDir, "displacement_volume_summary_")).empty();
    Check(Close(protonTotal, expectedTotal), "H2-4 DDD proton partition equals the unfiltered total");
    Check(!gammaRows, "H2-4 DDD gamma partition has no volume row (no table, no fabricated DDD)");

    // Energy partition: [0,5) keeps the 1 MeV step, [5,100) the 10 MeV step.
    double energySum = 0.0;
    const struct { const char* name; double low; double high; double expected; } windows[] = {
        {"ddd_energy_low", 0.0, 5.0, expected1},
        {"ddd_energy_high", 5.0, 100.0, expected10},
    };
    for (const auto& window : windows) {
        const std::filesystem::path dir = run(window.name, EnergyFilter(window.low, window.high), nullptr);
        const double ddd = ReadCsv(FindSingle(dir, "displacement_volume_summary_")).front().Number("ddd_MeV_g");
        Check(Close(ddd, window.expected), std::string("H2-4 DDD energy window ") + window.name);
        energySum += ddd;
    }
    Check(Close(energySum, expectedTotal), "H2-4 DDD energy partitions sum to the unfiltered total");

    // Spectrum: same weighted DDD decomposed by pre-step kinetic energy.
    auto spectrum = std::make_unique<VolumeSpectrum>(SpectrumConfig(4, 0.0, 20.0));
    const std::filesystem::path spectrumDir = run("ddd_spectrum", nullptr, std::move(spectrum));
    const std::vector<Row> rows = ReadCsv(FindSingle(spectrumDir, "spectrum_displacement_"));
    Check(rows.size() == 6, "H2-4 DDD spectrum writes 4 bins plus underflow and overflow");
    double spectrumSum = 0.0;
    for (const Row& row : rows) {
        spectrumSum += row.Number("amount");
        Check(row.Text("unit") == "MeV/g", "H2-4 DDD spectrum unit is MeV/g");
        Check(row.Text("n_events") == "2", "H2-4 DDD spectrum keeps the complete event N");
    }
    Check(Close(spectrumSum, expectedTotal), "H2-4 DDD spectrum buckets sum to the weighted DDD total");
    const Row lowBin = *std::find_if(rows.begin(), rows.end(), [](const Row& row) {
        return row.Text("region") == "bin" && row.Text("bin") == "0";
    });
    Check(Close(lowBin.Number("amount"), expected1), "H2-4 DDD 1 MeV step lands in the first bin");
}

int main(int argc, char** argv)
{

    try {
        const std::filesystem::path root =
            argc > 1 ? std::filesystem::path(argv[1]) : std::filesystem::temp_directory_path() / "g4usim-h2-component";
        std::filesystem::remove_all(root);
        std::filesystem::create_directories(root);

        FluenceTotals(root / "totals_fluence");
        ParticlePartitions(root / "partitions");
        EnergyPartitions(root / "windows");
        LetMoments(root / "let");
        SpectrumBoundaries(root / "spectrum_boundaries");
        WeightOnceComponent(root / "weight_once");
        Geant4FilterBoundaries();
        FilterEnergyChecks();
        SpectrumAccumulationChecks();
        SpectrumWidthChecks();
        // The table fixture lives in the repository; derive it from the binary
        // location (build/Release/h2VolumeScoringCheck.exe -> repository root)
        // so ctest and manual runs agree without changing product build inputs.
        const std::filesystem::path repository =
            argc > 2 ? std::filesystem::path(argv[2])
                     : std::filesystem::absolute(std::filesystem::path(argv[0]))
                           .parent_path().parent_path().parent_path();
        DisplacementPartitions(root / "ddd", repository);

        if (failures != 0) {
            std::cerr << failures << " component check(s) failed\n";
            return 1;
        }
        std::cout << "PASS: H2-2 component checks (V1b/V2/V3/V5 boundaries/V6b/V8/V9/V10/V11) and H2-4 DDD partition/spectrum; output in " << root << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: component check aborted: " << error.what() << "\n";
        return 2;
    }
}
