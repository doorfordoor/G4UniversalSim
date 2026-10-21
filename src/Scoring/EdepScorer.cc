#include "Scoring/EdepScorer.hh"

#include "Output/AnalysisOutput.hh"
#include "Output/CsvWriter.hh"
#include "Output/OutputManager.hh"
#include "Utils/StringUtils.hh"
#include "G4SystemOfUnits.hh"

#include <iomanip>
#include <sstream>

EdepScorer::EdepScorer(const std::string& name)
    : ScorerBase(name),
      rawEdepHist_("edep_raw", 200, 0.0, 10.0),
      weightedEdepHist_("edep_weighted", 200, 0.0, 10.0)
{
}

EdepScorer::~EdepScorer() = default;

void EdepScorer::BeginRun(int runID)
{
    currentRunID_ = runID;
    runRawEdep_ = 0.0;
    runWeightedEdep_ = 0.0;
    runTotal_ = EdepTally{};
    events_ = 0;
    touched_.Clear();
    volumeEdep_.clear();
    particleEdep_.clear();
    rawEdepHist_.Reset();
    weightedEdepHist_.Reset();
}

void EdepScorer::EndRun(int)
{
}

void EdepScorer::BeginEvent(int eventID)
{
    currentEventID_ = eventID;
    currentEventRawEdep_ = 0.0;
    currentEventWeightedEdep_ = 0.0;
}

void EdepScorer::EndEvent(int)
{
    runRawEdep_ += currentEventRawEdep_;
    runWeightedEdep_ += currentEventWeightedEdep_;
    runTotal_.raw.event = currentEventRawEdep_;
    runTotal_.weighted.event = currentEventWeightedEdep_;
    runTotal_.raw.Close();
    runTotal_.weighted.Close();
    touched_.EndEvent();
    ++events_;
    if (rawHistogramEnabled_) rawEdepHist_.Fill(currentEventRawEdep_);
    if (weightedHistogramEnabled_) weightedEdepHist_.Fill(currentEventWeightedEdep_);
}

void EdepScorer::ScoreHit(const HitRecord& hit)
{
    const double raw = hit.edep;
    const double weighted = hit.edep * hit.weight;

    currentEventRawEdep_ += raw;
    currentEventWeightedEdep_ += weighted;

    if (volumeSummaryEnabled_) {
        const std::string key = SummaryKey(hit.volumeName);
        EdepTally& tally = volumeEdep_[key];
        touched_.Add(tally.raw, raw);
        touched_.Add(tally.weighted, weighted);
    }
    if (particleSummaryEnabled_) {
        const std::string key = SummaryKey(hit.particleName);
        EdepTally& tally = particleEdep_[key];
        touched_.Add(tally.raw, raw);
        touched_.Add(tally.weighted, weighted);
    }
}

void EdepScorer::Write(OutputManager& output)
{
    if (rawHistogramEnabled_) {
        output.AddHistogram1D(rawEdepHist_);
        output.WriteHistogram1D(rawEdepHist_.GetName());
    }
    if (weightedHistogramEnabled_) {
        output.AddHistogram1D(weightedEdepHist_);
        output.WriteHistogram1D(weightedEdepHist_.GetName());
    }
    SubmitStatistics("edep", "total", runTotal_);
    if (volumeSummaryEnabled_) {
        for (const auto& item : volumeEdep_) SubmitStatistics("edep_volume", item.first, item.second);
        WriteSummaryCsv(output, "edep_volume_summary.csv", volumeEdep_);
    }
    if (particleSummaryEnabled_) {
        for (const auto& item : particleEdep_) SubmitStatistics("edep_particle", item.first, item.second);
        WriteSummaryCsv(output, "edep_particle_summary.csv", particleEdep_);
    }
}

void EdepScorer::Reset()
{
    currentRunID_ = -1;
    currentEventID_ = -1;
    currentEventRawEdep_ = 0.0;
    currentEventWeightedEdep_ = 0.0;
    runRawEdep_ = 0.0;
    runWeightedEdep_ = 0.0;
    runTotal_ = EdepTally{};
    events_ = 0;
    touched_.Clear();
    volumeEdep_.clear();
    particleEdep_.clear();
    rawEdepHist_.Reset();
    weightedEdepHist_.Reset();
}

void EdepScorer::EnableRawHistogram(bool enable)
{
    rawHistogramEnabled_ = enable;
}

bool EdepScorer::IsRawHistogramEnabled() const
{
    return rawHistogramEnabled_;
}

void EdepScorer::EnableWeightedHistogram(bool enable)
{
    weightedHistogramEnabled_ = enable;
}

bool EdepScorer::IsWeightedHistogramEnabled() const
{
    return weightedHistogramEnabled_;
}

void EdepScorer::ConfigureRawHistogram(int bins, double min, double max)
{
    rawEdepHist_.Configure("edep_raw", bins, min, max);
}

void EdepScorer::ConfigureWeightedHistogram(int bins, double min, double max)
{
    weightedEdepHist_.Configure("edep_weighted", bins, min, max);
}

void EdepScorer::EnableVolumeSummary(bool enable)
{
    volumeSummaryEnabled_ = enable;
}

bool EdepScorer::IsVolumeSummaryEnabled() const
{
    return volumeSummaryEnabled_;
}

void EdepScorer::EnableParticleSummary(bool enable)
{
    particleSummaryEnabled_ = enable;
}

bool EdepScorer::IsParticleSummaryEnabled() const
{
    return particleSummaryEnabled_;
}

double EdepScorer::GetCurrentEventRawEdep() const
{
    return currentEventRawEdep_;
}

double EdepScorer::GetCurrentEventWeightedEdep() const
{
    return currentEventWeightedEdep_;
}

double EdepScorer::GetRunRawEdep() const
{
    return runRawEdep_;
}

double EdepScorer::GetRunWeightedEdep() const
{
    return runWeightedEdep_;
}

std::string EdepScorer::SummaryKey(const std::string& value)
{
    const std::string trimmed = StringUtils::Trim(value);
    return trimmed.empty() ? "unknown" : trimmed;
}

std::string EdepScorer::ToString(double value)
{
    std::ostringstream oss;
    oss << std::setprecision(12) << value;
    return oss.str();
}

void EdepScorer::SubmitStatistics(const std::string& scorer, const std::string& key,
                                  const EdepTally& tally) const
{
    for (const bool weighted : {false, true}) {
        const HistoryTally& t = weighted ? tally.weighted : tally.raw;
        HistoryStatistics::Entry entry;
        entry.name = key;
        entry.unit = "MeV";
        entry.sum = t.sum / MeV;
        entry.sumSq = t.sumSq / (MeV * MeV);
        entry.entries = t.entries;
        HistoryStatistics::Submit(currentRunID_, scorer, weighted ? "weighted_edep" : "raw_edep", key, entry);
    }
}

void EdepScorer::WriteSummaryCsv(OutputManager& output,
                                 const std::string& baseFilename,
                                 const std::map<std::string, EdepTally>& tallies) const
{
    const double mev2 = MeV * MeV;
    if (output.WritesRoot()) {
        const bool byVolume = baseFilename.rfind("edep_volume", 0) == 0;
        for (const auto& item : tallies) {
            const EdepTally& t = item.second;
            AnalysisOutput::FillEdepSummary(byVolume, currentRunID_, output.GetThreadId(), item.first,
                                            t.raw.sum / MeV, t.weighted.sum / MeV,
                                            t.raw.sumSq / mev2, t.weighted.sumSq / mev2, events_);
        }
    }
    if (!output.WritesCsv()) return;
    CsvWriter writer(output.MakeOutputPath(output.MakeThreadFilename(baseFilename)));
    writer.WriteHeader({"name", "raw_edep_MeV", "weighted_edep_MeV",
                        "raw_edep_sum_sq_MeV2", "weighted_edep_sum_sq_MeV2", "n_events"});
    for (const auto& item : tallies) {
        const EdepTally& t = item.second;
        writer.WriteRow({item.first, ToString(t.raw.sum / MeV), ToString(t.weighted.sum / MeV),
                         ToString(t.raw.sumSq / mev2), ToString(t.weighted.sumSq / mev2),
                         std::to_string(events_)});
    }
    writer.Close();
    output.RegisterGeneratedFile(writer.GetFilename());
}
