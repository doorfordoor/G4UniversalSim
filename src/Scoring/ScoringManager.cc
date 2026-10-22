#include "Scoring/ScoringManager.hh"

#include "Config/ConfigManager.hh"
#include "Output/AnalysisOutput.hh"
#include "Output/CsvWriter.hh"
#include "Output/OutputManager.hh"
#include "Scoring/DoseScorer.hh"
#include "Scoring/EdepScorer.hh"
#include "Scoring/FluenceScorer.hh"
#include "Scoring/LETScorer.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"
#include "G4PhysicalVolumeStore.hh"
#include "G4RunManager.hh"

#include <iostream>
#include <cstdlib>
#include <stdexcept>

namespace {
bool InjectBeginScoringFailure(int runID, const OutputManager* output)
{
    if (runID != 1 || !output || output->GetThreadId() != 0) return false;
#ifdef _WIN32
    char* value = nullptr;
    std::size_t length = 0;
    if (_dupenv_s(&value, &length, "G4USIM_TEST_OUTPUT_FAULT") != 0) return false;
    const bool inject = value && std::string(value) == "begin_scoring_t0";
    std::free(value);
    return inject;
#else
    const char* value = std::getenv("G4USIM_TEST_OUTPUT_FAULT");
    return value && std::string(value) == "begin_scoring_t0";
#endif
}
}  // namespace

ScoringManager::ScoringManager() = default;
ScoringManager::~ScoringManager() = default;

std::unique_ptr<ScoringManager> ScoringManager::CloneForThread(OutputManager* outputManager,
                                                               int threadId) const
{
    (void)threadId;
    auto clone = std::make_unique<ScoringManager>();
    clone->outputManager_ = outputManager;
    clone->enabled_ = enabled_;
    clone->hitOutputEnabled_ = hitOutputEnabled_;
    clone->eventEdepOutputEnabled_ = eventEdepOutputEnabled_;
    clone->edepScoringEnabled_ = edepScoringEnabled_;
    clone->letScoringEnabled_ = letScoringEnabled_;
    clone->letParticles_ = letParticles_;
    clone->doseScoringEnabled_ = doseScoringEnabled_;
    clone->fluenceScoringEnabled_ = fluenceScoringEnabled_;
    clone->autoCreateDefaultScorers_ = autoCreateDefaultScorers_;
    clone->edepRawHistogramEnabled_ = edepRawHistogramEnabled_;
    clone->edepWeightedHistogramEnabled_ = edepWeightedHistogramEnabled_;
    clone->edepVolumeSummaryEnabled_ = edepVolumeSummaryEnabled_;
    clone->edepParticleSummaryEnabled_ = edepParticleSummaryEnabled_;
    clone->rawEdepHistogram_ = rawEdepHistogram_;
    clone->weightedEdepHistogram_ = weightedEdepHistogram_;
    clone->verboseLevel_ = verboseLevel_;
    clone->phaseSpaceVolume_ = phaseSpaceVolume_;
    clone->phaseSpaceParticles_ = phaseSpaceParticles_;
    clone->phaseSpaceKill_ = phaseSpaceKill_;
    if (clone->autoCreateDefaultScorers_) {
        clone->EnsureDefaultScorers();
    }
    return clone;
}

void ScoringManager::SetOutputManager(OutputManager* outputManager)
{
    outputManager_ = outputManager;
}

OutputManager* ScoringManager::GetOutputManager()
{
    return outputManager_;
}

const OutputManager* ScoringManager::GetOutputManager() const
{
    return outputManager_;
}

void ScoringManager::Enable(bool enable)
{
    enabled_ = enable;
}

bool ScoringManager::IsEnabled() const
{
    return enabled_;
}

void ScoringManager::EnableHitOutput(bool enable)
{
    hitOutputEnabled_ = enable;
}

bool ScoringManager::IsHitOutputEnabled() const
{
    return hitOutputEnabled_;
}

void ScoringManager::EnableEventEdepOutput(bool enable)
{
    eventEdepOutputEnabled_ = enable;
}

bool ScoringManager::IsEventEdepOutputEnabled() const
{
    return eventEdepOutputEnabled_;
}

void ScoringManager::EnableEdepScoring(bool enable)
{
    edepScoringEnabled_ = enable;
    SetScorerEnabledIfExists("edep", enable);
}

bool ScoringManager::IsEdepScoringEnabled() const
{
    return edepScoringEnabled_;
}

void ScoringManager::EnableLETScoring(bool enable)
{
    letScoringEnabled_ = enable;
    SetScorerEnabledIfExists("let", enable);
}

bool ScoringManager::IsLETScoringEnabled() const
{
    return letScoringEnabled_;
}

void ScoringManager::SetLETParticles(const std::set<std::string>& particles)
{
    letParticles_ = particles;
    if (auto* scorer = dynamic_cast<LETScorer*>(GetScorer("let"))) scorer->SetParticles(particles);
}

const std::set<std::string>& ScoringManager::GetLETParticles() const
{
    return letParticles_;
}

void ScoringManager::EnableDoseScoring(bool enable)
{
    doseScoringEnabled_ = enable;
    SetScorerEnabledIfExists("dose", enable);
}

bool ScoringManager::IsDoseScoringEnabled() const
{
    return doseScoringEnabled_;
}

void ScoringManager::EnableFluenceScoring(bool enable)
{
    fluenceScoringEnabled_ = enable;
    SetScorerEnabledIfExists("fluence", enable);
}

bool ScoringManager::IsFluenceScoringEnabled() const
{
    return fluenceScoringEnabled_;
}

void ScoringManager::SetAutoCreateDefaultScorers(bool enable)
{
    autoCreateDefaultScorers_ = enable;
}

bool ScoringManager::IsAutoCreateDefaultScorersEnabled() const
{
    return autoCreateDefaultScorers_;
}

void ScoringManager::ConfigureEdepHistogram(int bins, double min, double max)
{
    if (bins <= 0) throw std::runtime_error("ScoringManager::ConfigureEdepHistogram requires bins > 0");
    if (!(max > min)) throw std::runtime_error("ScoringManager::ConfigureEdepHistogram requires max > min");
    rawEdepHistogram_ = {bins, min, max, true};
    if (auto* scorer = GetEdepScorer()) scorer->ConfigureRawHistogram(bins, min, max);
}

ScoringManager::EdepHistogramBinning ScoringManager::GetEdepHistogramBinning(bool weighted) const
{
    const HistogramConfig& config = weighted ? weightedEdepHistogram_ : rawEdepHistogram_;
    return {config.bins, config.min, config.max};
}

void ScoringManager::ConfigureWeightedEdepHistogram(int bins, double min, double max)
{
    if (bins <= 0) throw std::runtime_error("ScoringManager::ConfigureWeightedEdepHistogram requires bins > 0");
    if (!(max > min)) throw std::runtime_error("ScoringManager::ConfigureWeightedEdepHistogram requires max > min");
    weightedEdepHistogram_ = {bins, min, max, true};
    if (auto* scorer = GetEdepScorer()) scorer->ConfigureWeightedHistogram(bins, min, max);
}

void ScoringManager::SetVerboseLevel(int level)
{
    if (level < 0) throw std::runtime_error("ScoringManager::SetVerboseLevel requires level >= 0");
    verboseLevel_ = level;
}

int ScoringManager::GetVerboseLevel() const
{
    return verboseLevel_;
}

void ScoringManager::Clear()
{
    scorers_.clear();
    currentRunID_ = -1;
    currentEventID_ = -1;
    currentEventRawEdep_ = 0.0;
    currentEventWeightedEdep_ = 0.0;
}

void ScoringManager::RegisterScorer(std::unique_ptr<ScorerBase> scorer)
{
    if (!scorer) throw std::runtime_error("ScoringManager::RegisterScorer received null scorer");
    if (StringUtils::Trim(scorer->GetName()).empty()) {
        throw std::runtime_error("ScoringManager::RegisterScorer received scorer with empty name");
    }
    if (HasScorer(scorer->GetName())) {
        throw std::runtime_error("ScoringManager::RegisterScorer duplicate scorer name: '" + scorer->GetName() + "'");
    }
    scorers_.push_back(std::move(scorer));
}

void ScoringManager::EnsureDefaultScorers()
{
    if (edepScoringEnabled_ && !HasScorer("edep")) {
        auto scorer = std::make_unique<EdepScorer>("edep");
        ApplyEdepSettings(*scorer);
        RegisterScorer(std::move(scorer));
    } else if (auto* scorer = GetEdepScorer()) {
        ApplyEdepSettings(*scorer);
    }

    if (letScoringEnabled_ && !HasScorer("let")) {
        auto scorer = std::make_unique<LETScorer>("let");
        scorer->SetEnabled(true);
        scorer->SetParticles(letParticles_);
        RegisterScorer(std::move(scorer));
    }
    if (doseScoringEnabled_ && !HasScorer("dose")) {
        auto scorer = std::make_unique<DoseScorer>("dose");
        scorer->SetEnabled(true);
        RegisterScorer(std::move(scorer));
    }
    if (fluenceScoringEnabled_ && !HasScorer("fluence")) {
        auto scorer = std::make_unique<FluenceScorer>("fluence");
        scorer->SetEnabled(true);
        RegisterScorer(std::move(scorer));
    }

    SetScorerEnabledIfExists("edep", edepScoringEnabled_);
    SetScorerEnabledIfExists("let", letScoringEnabled_);
    SetScorerEnabledIfExists("dose", doseScoringEnabled_);
    SetScorerEnabledIfExists("fluence", fluenceScoringEnabled_);
}

bool ScoringManager::HasScorer(const std::string& name) const
{
    return GetScorer(name) != nullptr;
}

ScorerBase* ScoringManager::GetScorer(const std::string& name)
{
    const std::string key = NormalizeName(name);
    for (auto& scorer : scorers_) {
        if (NormalizeName(scorer->GetName()) == key) return scorer.get();
    }
    return nullptr;
}

const ScorerBase* ScoringManager::GetScorer(const std::string& name) const
{
    const std::string key = NormalizeName(name);
    for (const auto& scorer : scorers_) {
        if (NormalizeName(scorer->GetName()) == key) return scorer.get();
    }
    return nullptr;
}

std::vector<std::string> ScoringManager::GetScorerNames() const
{
    std::vector<std::string> names;
    names.reserve(scorers_.size());
    for (const auto& scorer : scorers_) names.push_back(scorer->GetName());
    return names;
}

void ScoringManager::BeginRun(int runID)
{
    // Test-only deterministic fault in the real Geant4 worker run callback.
    if (InjectBeginScoringFailure(runID, outputManager_)) {
        throw std::runtime_error("Injected ScoringManager::BeginRun failure");
    }
    currentRunID_ = runID;
    BeginPhaseSpaceRun();
    if (autoCreateDefaultScorers_) EnsureDefaultScorers();
    if (!enabled_) return;
    for (ScorerBase* scorer : EnabledScorers()) scorer->BeginRun(runID);
}

void ScoringManager::EndRun(int runID)
{
    EndPhaseSpaceRun();
    if (!enabled_) return;
    for (ScorerBase* scorer : EnabledScorers()) scorer->EndRun(runID);
}

void ScoringManager::BeginEvent(int eventID)
{
    currentEventID_ = eventID;
    currentEventRawEdep_ = 0.0;
    currentEventWeightedEdep_ = 0.0;
    if (!enabled_) return;
    for (ScorerBase* scorer : EnabledScorers()) scorer->BeginEvent(eventID);
}

void ScoringManager::EndEvent(int eventID)
{
    if (eventID != currentEventID_ && verboseLevel_ > 0) {
        std::cerr << "[ScoringManager] EndEvent eventID mismatch: current="
                  << currentEventID_ << ", input=" << eventID << '\n';
    }

    if (enabled_) {
        for (ScorerBase* scorer : EnabledScorers()) scorer->EndEvent(eventID);
    }

    // ROOT histograms are filled per event (the CSV path bins inside EdepScorer
    // and writes at end of run); Geant4 merges them across worker threads.
    if (enabled_ && outputManager_ && outputManager_->WritesRoot() &&
        !outputManager_->HasOutputFailure()) {
        const EdepScorer* edep = GetEdepScorer();
        if (edep && edep->IsEnabled()) {
            AnalysisOutput::FillEdepHistograms(
                edep->IsRawHistogramEnabled(), edep->GetCurrentEventRawEdep(),
                edep->IsWeightedHistogramEnabled(), edep->GetCurrentEventWeightedEdep());
        }
    }

    if (enabled_ && eventEdepOutputEnabled_ && outputManager_ &&
        !outputManager_->HasOutputFailure()) {
        EventEdepRecord record;
        record.runID = currentRunID_;
        record.eventID = currentEventID_;
        record.rawEdep = currentEventRawEdep_;
        record.weightedEdep = currentEventWeightedEdep_;
        try {
            outputManager_->WriteEventEdep(record);
        } catch (const std::exception& error) {
            outputManager_->RecordOutputFailure("event_edep_write", error.what());
            if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
        }
    }
}

void ScoringManager::ScoreHit(const HitRecord& hit)
{
    if (!enabled_) return;
    if (outputManager_ && outputManager_->HasOutputFailure()) return;

    currentEventRawEdep_ += hit.edep;
    currentEventWeightedEdep_ += hit.edep * hit.weight;

    if (hitOutputEnabled_ && outputManager_) {
        HitRecord row = hit;
        row.runID = currentRunID_;
        try {
            outputManager_->WriteHit(row);
        } catch (const std::exception& error) {
            outputManager_->RecordOutputFailure("hits_write", error.what());
            if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
            return;
        }
    }

    for (ScorerBase* scorer : EnabledScorers()) {
        try {
            scorer->ScoreHit(hit);
        } catch (const std::exception& error) {
            if (outputManager_) outputManager_->RecordOutputFailure("scoring_" + scorer->GetName(), error.what());
            if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
            return;
        }
    }
}

void ScoringManager::ScoreFluenceStep(const HitRecord& hit)
{
    if (!enabled_ || !fluenceScoringEnabled_) return;
    if (outputManager_ && outputManager_->HasOutputFailure()) return;
    ScorerBase* scorer = GetScorer("fluence");
    if (!scorer || !scorer->IsEnabled()) return;
    try {
        scorer->ScoreHit(hit);
    } catch (const std::exception& error) {
        ReportFluenceTransportFailure(error.what());
    }
}

void ScoringManager::ScoreLETStep(const HitRecord& hit)
{
    if (!enabled_ || !letScoringEnabled_) return;
    if (outputManager_ && outputManager_->HasOutputFailure()) return;
    ScorerBase* scorer = GetScorer("let");
    if (!scorer || !scorer->IsEnabled()) return;
    try {
        scorer->ScoreHit(hit);
    } catch (const std::exception& error) {
        if (outputManager_) outputManager_->RecordOutputFailure("scoring_let", error.what());
        if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
    }
}

void ScoringManager::ReportFluenceTransportFailure(const std::string& message)
{
    if (outputManager_) outputManager_->RecordOutputFailure("scoring_fluence", message);
    if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
}

double ScoringManager::GetCurrentEventRawEdep() const
{
    return currentEventRawEdep_;
}

double ScoringManager::GetCurrentEventWeightedEdep() const
{
    return currentEventWeightedEdep_;
}

int ScoringManager::GetCurrentEventID() const
{
    return currentEventID_;
}

void ScoringManager::WriteAll()
{
    if (!enabled_ || !outputManager_) return;
    for (ScorerBase* scorer : EnabledScorers()) scorer->Write(*outputManager_);
}

void ScoringManager::LoadFromConfig(const ConfigManager& config)
{
    if (config.HasSection("phase_space")) {
        phaseSpaceVolume_ = StringUtils::Trim(config.GetString("phase_space", "volume", ""));
        if (phaseSpaceVolume_.empty()) {
            throw std::runtime_error("[phase_space]/volume must name the physical volume whose entering particles are recorded");
        }
        phaseSpaceParticles_.clear();
        const std::string particles = StringUtils::Trim(config.GetString("phase_space", "particles", "all"));
        if (StringUtils::ToLower(particles) != "all") {
            for (const std::string& part : StringUtils::Split(particles, ',')) {
                const std::string name = StringUtils::Trim(part);
                if (!name.empty()) phaseSpaceParticles_.insert(name);
            }
            if (phaseSpaceParticles_.empty()) throw std::runtime_error("[phase_space]/particles must be 'all' or a particle list");
        }
        phaseSpaceKill_ = config.GetBool("phase_space", "kill", false);
    }
    if (!config.HasSection("scoring")) return;

    Enable(config.GetBool("scoring", "enabled", enabled_));
    EnableHitOutput(config.GetBool("scoring", "hits", hitOutputEnabled_));
    EnableEventEdepOutput(config.GetBool("scoring", "event_edep", eventEdepOutputEnabled_));
    EnableEdepScoring(config.GetBool("scoring", "edep", edepScoringEnabled_));
    EnableLETScoring(config.GetBool("scoring", "let", letScoringEnabled_));
    EnableDoseScoring(config.GetBool("scoring", "dose", doseScoringEnabled_));
    EnableFluenceScoring(config.GetBool("scoring", "fluence", fluenceScoringEnabled_));
    SetAutoCreateDefaultScorers(config.GetBool("scoring", "auto_create_default_scorers", autoCreateDefaultScorers_));
    if (enabled_ && (doseScoringEnabled_ || fluenceScoringEnabled_) && !autoCreateDefaultScorers_) {
        throw std::runtime_error("Dose/Fluence scoring requires [scoring]/auto_create_default_scorers = true");
    }
    SetVerboseLevel(config.GetInt("scoring", "verbose", verboseLevel_));

    if (config.HasSection("scoring.edep")) {
        edepRawHistogramEnabled_ = config.GetBool("scoring.edep", "raw_histogram", edepRawHistogramEnabled_);
        edepWeightedHistogramEnabled_ = config.GetBool("scoring.edep", "weighted_histogram", edepWeightedHistogramEnabled_);
        edepVolumeSummaryEnabled_ = config.GetBool("scoring.edep", "volume_summary", edepVolumeSummaryEnabled_);
        edepParticleSummaryEnabled_ = config.GetBool("scoring.edep", "particle_summary", edepParticleSummaryEnabled_);

        const int bins = config.GetInt("scoring.edep", "bins", rawEdepHistogram_.bins);
        const double min = config.HasKey("scoring.edep", "min")
            ? UnitParser::ParseEnergy(config.GetString("scoring.edep", "min"))
            : rawEdepHistogram_.min;
        const double max = config.HasKey("scoring.edep", "max")
            ? UnitParser::ParseEnergy(config.GetString("scoring.edep", "max"))
            : rawEdepHistogram_.max;

        ConfigureEdepHistogram(bins, min, max);
        ConfigureWeightedEdepHistogram(bins, min, max);
    }

    if (auto* scorer = GetEdepScorer()) {
        ApplyEdepSettings(*scorer);
    }

    if (config.HasKey("scoring.let", "particles")) {
        std::set<std::string> particles;
        const std::string text = StringUtils::Trim(config.GetString("scoring.let", "particles"));
        if (StringUtils::ToLower(text) != "all") {
            for (const std::string& part : StringUtils::Split(text, ',')) {
                const std::string name = StringUtils::Trim(part);
                if (!name.empty()) particles.insert(name);
            }
            if (particles.empty()) throw std::runtime_error("[scoring.let] particles must be 'all' or a particle list");
        }
        SetLETParticles(particles);
    }
}

void ScoringManager::PrintSummary() const
{
    std::cout << "[ScoringManager] enabled=" << (enabled_ ? "true" : "false")
              << ", hitOutput=" << (hitOutputEnabled_ ? "true" : "false")
              << ", eventEdepOutput=" << (eventEdepOutputEnabled_ ? "true" : "false")
              << ", edep=" << (edepScoringEnabled_ ? "true" : "false")
              << ", let=" << (letScoringEnabled_ ? "true" : "false")
              << ", dose=" << (doseScoringEnabled_ ? "true" : "false")
              << ", fluence=" << (fluenceScoringEnabled_ ? "true" : "false")
              << ", autoCreateDefaultScorers=" << (autoCreateDefaultScorers_ ? "true" : "false")
              << ", verbose=" << verboseLevel_
              << ", currentRunID=" << currentRunID_
              << ", currentEventID=" << currentEventID_
              << ", currentRawEdep=" << currentEventRawEdep_
              << ", currentWeightedEdep=" << currentEventWeightedEdep_
              << ", scorers=" << scorers_.size()
              << ", outputManager=" << (outputManager_ ? "connected" : "null")
              << '\n';
    for (const auto& scorer : scorers_) {
        std::cout << "  - " << scorer->GetName()
                  << " enabled=" << (scorer->IsEnabled() ? "true" : "false")
                  << '\n';
    }
}

bool ScoringManager::IsPhaseSpaceEnabled() const
{
    return !phaseSpaceVolume_.empty();
}

const std::string& ScoringManager::GetPhaseSpaceVolume() const
{
    return phaseSpaceVolume_;
}

bool ScoringManager::AcceptsPhaseSpaceParticle(const std::string& particle) const
{
    return phaseSpaceParticles_.empty() || phaseSpaceParticles_.count(particle) > 0;
}

bool ScoringManager::KillsPhaseSpaceParticles() const
{
    return phaseSpaceKill_;
}

void ScoringManager::BeginPhaseSpaceRun()
{
    phaseSpaceWriter_.reset();
    if (phaseSpaceVolume_.empty() || !outputManager_) return;
    if (!G4PhysicalVolumeStore::GetInstance()->GetVolume(phaseSpaceVolume_, false)) {
        throw std::runtime_error("[phase_space]/volume '" + phaseSpaceVolume_ +
                                 "' is not a physical volume of the built geometry (usually <name>_PV)");
    }
    outputManager_->Initialize();
    phaseSpaceWriter_ = std::make_unique<CsvWriter>(
        outputManager_->MakeOutputPath(outputManager_->MakeThreadFilename("phase_space.csv")));
    phaseSpaceWriter_->WriteHeader(PhaseSpace::Header());
}

void ScoringManager::EndPhaseSpaceRun()
{
    if (!phaseSpaceWriter_) return;
    phaseSpaceWriter_->Close();
    if (outputManager_) outputManager_->RegisterGeneratedFile(phaseSpaceWriter_->GetFilename());
    phaseSpaceWriter_.reset();
}

void ScoringManager::RecordPhaseSpace(PhaseSpaceParticle particle)
{
    if (!phaseSpaceWriter_) return;
    if (outputManager_ && outputManager_->HasOutputFailure()) return;
    particle.runID = currentRunID_;
    particle.eventID = currentEventID_;
    try {
        phaseSpaceWriter_->WriteRow(PhaseSpace::Row(particle));
    } catch (const std::exception& error) {
        if (outputManager_) outputManager_->RecordOutputFailure("phase_space_write", error.what());
        if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
    }
}

std::string ScoringManager::NormalizeName(const std::string& name)
{
    return StringUtils::ToLower(StringUtils::Trim(name));
}

std::vector<ScorerBase*> ScoringManager::EnabledScorers()
{
    std::vector<ScorerBase*> result;
    for (auto& scorer : scorers_) {
        if (scorer->IsEnabled()) result.push_back(scorer.get());
    }
    return result;
}

std::vector<const ScorerBase*> ScoringManager::EnabledScorers() const
{
    std::vector<const ScorerBase*> result;
    for (const auto& scorer : scorers_) {
        if (scorer->IsEnabled()) result.push_back(scorer.get());
    }
    return result;
}

EdepScorer* ScoringManager::GetEdepScorer()
{
    return dynamic_cast<EdepScorer*>(GetScorer("edep"));
}

const EdepScorer* ScoringManager::GetEdepScorer() const
{
    return dynamic_cast<const EdepScorer*>(GetScorer("edep"));
}

void ScoringManager::ApplyEdepSettings(EdepScorer& scorer) const
{
    scorer.SetEnabled(edepScoringEnabled_);
    scorer.EnableRawHistogram(edepRawHistogramEnabled_);
    scorer.EnableWeightedHistogram(edepWeightedHistogramEnabled_);
    scorer.EnableVolumeSummary(edepVolumeSummaryEnabled_);
    scorer.EnableParticleSummary(edepParticleSummaryEnabled_);
    if (rawEdepHistogram_.configured) {
        scorer.ConfigureRawHistogram(rawEdepHistogram_.bins, rawEdepHistogram_.min, rawEdepHistogram_.max);
    }
    if (weightedEdepHistogram_.configured) {
        scorer.ConfigureWeightedHistogram(weightedEdepHistogram_.bins, weightedEdepHistogram_.min, weightedEdepHistogram_.max);
    }
}

void ScoringManager::SetScorerEnabledIfExists(const std::string& name, bool enable)
{
    if (auto* scorer = GetScorer(name)) {
        scorer->SetEnabled(enable);
    }
}
