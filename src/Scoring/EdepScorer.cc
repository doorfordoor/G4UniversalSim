#include "Scoring/EdepScorer.hh"

#include "Output/CsvWriter.hh"
#include "Output/OutputManager.hh"
#include "Utils/StringUtils.hh"

#include <iomanip>
#include <set>
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
    volumeRawEdep_.clear();
    volumeWeightedEdep_.clear();
    particleRawEdep_.clear();
    particleWeightedEdep_.clear();
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
        volumeRawEdep_[key] += raw;
        volumeWeightedEdep_[key] += weighted;
    }
    if (particleSummaryEnabled_) {
        const std::string key = SummaryKey(hit.particleName);
        particleRawEdep_[key] += raw;
        particleWeightedEdep_[key] += weighted;
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
    if (volumeSummaryEnabled_) {
        WriteSummaryCsv(output, "edep_volume_summary.csv", volumeRawEdep_, volumeWeightedEdep_);
    }
    if (particleSummaryEnabled_) {
        WriteSummaryCsv(output, "edep_particle_summary.csv", particleRawEdep_, particleWeightedEdep_);
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
    volumeRawEdep_.clear();
    volumeWeightedEdep_.clear();
    particleRawEdep_.clear();
    particleWeightedEdep_.clear();
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

void EdepScorer::WriteSummaryCsv(OutputManager& output,
                                 const std::string& baseFilename,
                                 const std::map<std::string, double>& raw,
                                 const std::map<std::string, double>& weighted) const
{
    CsvWriter writer(output.MakeOutputPath(output.MakeThreadFilename(baseFilename)));
    writer.WriteHeader({"name", "raw_edep", "weighted_edep"});

    std::set<std::string> keys;
    for (const auto& item : raw) keys.insert(item.first);
    for (const auto& item : weighted) keys.insert(item.first);

    for (const std::string& key : keys) {
        const auto rawIt = raw.find(key);
        const auto weightedIt = weighted.find(key);
        writer.WriteRow({
            key,
            ToString(rawIt == raw.end() ? 0.0 : rawIt->second),
            ToString(weightedIt == weighted.end() ? 0.0 : weightedIt->second)
        });
    }
}
