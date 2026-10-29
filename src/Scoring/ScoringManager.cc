#include "Scoring/ScoringManager.hh"

#include "Config/ConfigManager.hh"
#include "Output/AnalysisOutput.hh"
#include "Output/CsvWriter.hh"
#include "Output/OutputManager.hh"
#include "Scoring/DisplacementScorer.hh"
#include "Scoring/DoseScorer.hh"
#include "Scoring/EdepScorer.hh"
#include "Scoring/FluenceScorer.hh"
#include "Scoring/LETScorer.hh"
#include "Scoring/NielTable.hh"
#include "Scoring/NumericChecks.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"
#include "G4ParticleDefinition.hh"
#include "G4ParticleTable.hh"
#include "G4PhysicalVolumeStore.hh"
#include "G4RunManager.hh"

#include <filesystem>
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

// [scoring.displacement] keys are particle names, and IniReader lower-cases every key,
// so a user cannot write the Geant4 spelling "He3" verbatim. A misspelled or wrongly
// cased name used to load a table that no hit can ever match: the DDD stayed at zero
// and the run reported success. The keys are therefore resolved to canonical particle
// names and an unknown name becomes a hard failure with file, line and a candidate.
//
// The Geant4 particle table is empty before the physics list is constructed, so the
// configuration phase usually cannot resolve anything; in that case the raw key is kept
// and ResolvePendingNielNames() finishes the job in BeginRun, before the first event.
struct ParticleNameLookup {
    std::string canonical;                 // empty when no particle matches
    std::vector<std::string> candidates;   // names in the table (empty: table not built yet)
};

ParticleNameLookup LookupParticleName(const std::string& rawKey)
{
    ParticleNameLookup result;
    auto* table = G4ParticleTable::GetParticleTable();
    const std::string key = StringUtils::Trim(rawKey);
    if (G4ParticleDefinition* exact = table->FindParticle(key)) {
        result.canonical = exact->GetParticleName();
        return result;
    }
    const std::string lower = StringUtils::ToLower(key);
    for (G4int index = 0; index < table->entries(); ++index) {
        const std::string name = table->GetParticleName(index);
        result.candidates.push_back(name);
        if (result.canonical.empty() && StringUtils::ToLower(name) == lower) result.canonical = name;
    }
    return result;
}

[[noreturn]] void ThrowUnknownParticleName(const std::string& rawKey, const std::string& location,
                                           const std::vector<std::string>& candidates)
{
    const std::string key = StringUtils::Trim(rawKey);
    std::string message = "[scoring.displacement]/" + key + " (" + location + "): '" + key +
                          "' is not a Geant4 particle name";
    const std::string suggestion = ConfigManager::Suggestion(key, candidates);
    if (!suggestion.empty()) message += "; did you mean '" + suggestion + "'?";
    message += " Particle names are matched case-insensitively against the Geant4 particle table "
               "(for example proton, neutron, e-, gamma, alpha, He3); a name that no particle can produce "
               "would silently keep the displacement damage dose at zero.";
    throw std::runtime_error(message);
}

std::string NielKeyLocation(const ConfigManager& config, const std::string& rawKey)
{
    const std::string lower = StringUtils::ToLower(StringUtils::Trim(rawKey));
    for (const IniFieldInfo& field : config.GetFields()) {
        if (field.normalizedSection != "scoring.displacement") continue;
        if (field.normalizedKey != lower) continue;
        return config.GetMainConfigPath() + " line " + std::to_string(field.lineNumber);
    }
    return "main config";
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
    clone->effectiveState_ = effectiveState_->Clone();
    clone->enabled_ = enabled_;
    clone->hitOutputEnabled_ = hitOutputEnabled_;
    clone->eventEdepOutputEnabled_ = eventEdepOutputEnabled_;
    clone->edepScoringEnabled_ = edepScoringEnabled_;
    clone->letScoringEnabled_ = letScoringEnabled_;
    clone->letParticles_ = letParticles_;
    clone->doseScoringEnabled_ = doseScoringEnabled_;
    clone->fluenceScoringEnabled_ = fluenceScoringEnabled_;
    clone->displacementScoringEnabled_ = displacementScoringEnabled_;
    clone->nielTables_ = nielTables_;
    clone->nielNamesPending_ = nielNamesPending_;
    clone->nielPendingLocations_ = nielPendingLocations_;
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
    clone->trajectories_ = TrajectoryRecorder(trajectories_.GetSettings());
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

void ScoringManager::EnableDisplacementScoring(bool enable)
{
    displacementScoringEnabled_ = enable;
    SetScorerEnabledIfExists("displacement", enable);
}

bool ScoringManager::IsDisplacementScoringEnabled() const
{
    return displacementScoringEnabled_;
}

void ScoringManager::SetNielTables(const std::map<std::string, std::shared_ptr<const NielTable>>& tables)
{
    nielTables_ = tables;
    if (auto* scorer = dynamic_cast<DisplacementScorer*>(GetScorer("displacement"))) scorer->SetTables(tables);
}

const std::map<std::string, std::shared_ptr<const NielTable>>& ScoringManager::GetNielTables() const
{
    return nielTables_;
}

void ScoringManager::ResolvePendingNielNames()
{
    if (!nielNamesPending_) return;
    std::map<std::string, std::shared_ptr<const NielTable>> resolved;
    for (const auto& entry : nielTables_) {
        const ParticleNameLookup lookup = LookupParticleName(entry.first);
        if (lookup.canonical.empty()) {
            if (lookup.candidates.empty()) {
                throw std::runtime_error("[scoring.displacement]/" + entry.first +
                                         ": the Geant4 particle table is empty when the run starts, so the "
                                         "NIEL table key cannot be validated");
            }
            const auto location = nielPendingLocations_.find(entry.first);
            ThrowUnknownParticleName(entry.first,
                                     location == nielPendingLocations_.end() ? "main config" : location->second,
                                     lookup.candidates);
        }
        if (resolved.count(lookup.canonical) != 0) {
            throw std::runtime_error("[scoring.displacement]/" + entry.first + " and another key both resolve "
                                     "to the Geant4 particle '" + lookup.canonical + "'");
        }
        resolved[lookup.canonical] = entry.second;
    }
    nielNamesPending_ = false;
    nielPendingLocations_.clear();
    SetNielTables(resolved);
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
    nielTables_.clear();
    nielNamesPending_ = false;
    nielPendingLocations_.clear();
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

    if (displacementScoringEnabled_ && !HasScorer("displacement")) {
        auto scorer = std::make_unique<DisplacementScorer>("displacement");
        scorer->SetEnabled(true);
        scorer->SetTables(nielTables_);
        RegisterScorer(std::move(scorer));
    }

    SetScorerEnabledIfExists("edep", edepScoringEnabled_);
    SetScorerEnabledIfExists("let", letScoringEnabled_);
    SetScorerEnabledIfExists("dose", doseScoringEnabled_);
    SetScorerEnabledIfExists("fluence", fluenceScoringEnabled_);
    SetScorerEnabledIfExists("displacement", displacementScoringEnabled_);
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
    // The particle table exists by now, so an unresolvable [scoring.displacement] key can be
    // rejected before the first event instead of leaving the DDD silently at zero.
    ResolvePendingNielNames();
    currentRunID_ = runID;
    BeginPhaseSpaceRun();
    if (trajectories_.IsEnabled() && outputManager_) {
        outputManager_->Initialize();
        trajectories_.BeginRun(outputManager_->MakeOutputPath(outputManager_->MakeThreadFilename("trajectories.json")),
                               runID, outputManager_->GetThreadId());
    }
    if (autoCreateDefaultScorers_) EnsureDefaultScorers();
    if (!enabled_) return;
    for (ScorerBase* scorer : EnabledScorers()) scorer->BeginRun(runID);
}

void ScoringManager::EndRun(int runID)
{
    EndPhaseSpaceRun();
    const std::string trajectoryFile = trajectories_.EndRun();
    if (!trajectoryFile.empty() && outputManager_) outputManager_->RegisterGeneratedFile(trajectoryFile);
    if (!enabled_) return;
    for (ScorerBase* scorer : EnabledScorers()) scorer->EndRun(runID);
}

void ScoringManager::BeginEvent(int eventID)
{
    if (outputManager_ && outputManager_->HasOutputFailure()) return;
    try {
        currentEventID_ = eventID;
        currentEventRawEdep_ = 0.0;
        currentEventWeightedEdep_ = 0.0;
        trajectories_.BeginEvent(eventID);
        if (!enabled_) return;
        for (ScorerBase* scorer : EnabledScorers()) scorer->BeginEvent(eventID);
    } catch (const std::exception& error) {
        ReportScoringFailure("scoring_begin_event", error.what());
    } catch (...) {
        ReportScoringFailure("scoring_begin_event", "unknown exception");
    }
}

void ScoringManager::EndEvent(int eventID)
{
    // A failed event must not be folded into statistics or published as valid.
    if (outputManager_ && outputManager_->HasOutputFailure()) return;
    try {
        if (eventID != currentEventID_ && verboseLevel_ > 0) {
            std::cerr << "[ScoringManager] EndEvent eventID mismatch: current="
                      << currentEventID_ << ", input=" << eventID << '\n';
        }

        if (enabled_) {
            for (ScorerBase* scorer : EnabledScorers()) scorer->EndEvent(eventID);
        }
        if (trajectories_.IsRecording()) {
            try {
                if (outputManager_ && outputManager_->HasOutputFailure()) {
                    trajectories_.BeginEvent(-1);   // drop it: the run is being aborted
                }
                trajectories_.EndEvent();
            } catch (const std::exception& error) {
                if (outputManager_) outputManager_->RecordOutputFailure("trajectory_write", error.what());
                if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
            }
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
    } catch (const std::exception& error) {
        ReportScoringFailure("scoring_end_event", error.what());
    } catch (...) {
        ReportScoringFailure("scoring_end_event", "unknown exception");
    }
}

void ScoringManager::ScoreHit(const HitRecord& hit)
{
    if (!enabled_) return;
    if (outputManager_ && outputManager_->HasOutputFailure()) return;

    try {
        const double weighted = ScoringNumeric::Multiply(hit.edep, hit.weight, "weighted hit Edep");
        const double nextRaw = ScoringNumeric::Add(currentEventRawEdep_, hit.edep, "event raw Edep");
        const double nextWeighted = ScoringNumeric::Add(currentEventWeightedEdep_, weighted, "event weighted Edep");
        currentEventRawEdep_ = nextRaw;
        currentEventWeightedEdep_ = nextWeighted;
    } catch (const std::exception& error) {
        ReportScoringFailure("scoring_event_accumulate", error.what());
        return;
    }

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

void ScoringManager::ScoreDisplacementStep(const HitRecord& hit)
{
    if (!enabled_ || !displacementScoringEnabled_) return;
    if (outputManager_ && outputManager_->HasOutputFailure()) return;
    ScorerBase* scorer = GetScorer("displacement");
    if (!scorer || !scorer->IsEnabled()) return;
    try {
        scorer->ScoreHit(hit);
    } catch (const std::exception& error) {
        if (outputManager_) outputManager_->RecordOutputFailure("scoring_displacement", error.what());
        if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
    }
}

void ScoringManager::ReportFluenceTransportFailure(const std::string& message)
{
    if (outputManager_) outputManager_->RecordOutputFailure("scoring_fluence", message);
    if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
}

void ScoringManager::ReportScoringFailure(const std::string& stage, const std::string& message)
{
    if (outputManager_) outputManager_->RecordOutputFailure(stage, message);
    std::cerr << "[ScoringFailure] " << stage << ": " << message << '\n';
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
    if (config.HasKey("output", "trajectories") || config.HasKey("output", "trajectory_min_energy") ||
        config.HasKey("output", "trajectory_max_points")) {
        TrajectorySettings settings;
        settings.events = config.GetInt("output", "trajectories", 0);
        if (settings.events < 0) throw std::runtime_error("[output]/trajectories must be >= 0 (events whose tracks are written)");
        const std::string minimum = StringUtils::Trim(config.GetString("output", "trajectory_min_energy", "0 MeV"));
        settings.minEnergy = UnitParser::ParseEnergy(minimum);
        if (settings.minEnergy < 0.0) throw std::runtime_error("[output]/trajectory_min_energy must be >= 0");
        const int maxPoints = config.GetInt("output", "trajectory_max_points", 2000000);
        if (maxPoints < 1) throw std::runtime_error("[output]/trajectory_max_points must be >= 1");
        settings.maxPoints = static_cast<std::size_t>(maxPoints);
        trajectories_ = TrajectoryRecorder(settings);
    }
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
    if (!config.HasSection("scoring")) {
        effectiveState_->reader = config.GetMainReader();
        effectiveState_->Accept(config.GetMainReader(), ExportEffectiveConfigFields());
        return;
    }

    Enable(config.GetBool("scoring", "enabled", enabled_));
    EnableHitOutput(config.GetBool("scoring", "hits", hitOutputEnabled_));
    EnableEventEdepOutput(config.GetBool("scoring", "event_edep", eventEdepOutputEnabled_));
    EnableEdepScoring(config.GetBool("scoring", "edep", edepScoringEnabled_));
    EnableLETScoring(config.GetBool("scoring", "let", letScoringEnabled_));
    EnableDoseScoring(config.GetBool("scoring", "dose", doseScoringEnabled_));
    EnableFluenceScoring(config.GetBool("scoring", "fluence", fluenceScoringEnabled_));
    EnableDisplacementScoring(config.GetBool("scoring", "displacement", displacementScoringEnabled_));
    SetAutoCreateDefaultScorers(config.GetBool("scoring", "auto_create_default_scorers", autoCreateDefaultScorers_));
    if (enabled_ && (doseScoringEnabled_ || fluenceScoringEnabled_ || displacementScoringEnabled_) &&
        !autoCreateDefaultScorers_) {
        throw std::runtime_error("Dose/Fluence/Displacement scoring requires [scoring]/auto_create_default_scorers = true");
    }
    if (config.HasSection("scoring.displacement")) {
        std::map<std::string, std::shared_ptr<const NielTable>> tables;
        std::map<std::string, std::string> pendingLocations;
        for (const std::string& key : config.GetKeys("scoring.displacement")) {
            const std::string location = NielKeyLocation(config, key);
            const ParticleNameLookup lookup = LookupParticleName(key);
            std::string particle = lookup.canonical;
            if (particle.empty()) {
                // Nothing is in the particle table before the physics list is built, so only a
                // populated table proves the name wrong here; otherwise BeginRun decides.
                if (!lookup.candidates.empty()) ThrowUnknownParticleName(key, location, lookup.candidates);
                particle = StringUtils::Trim(key);
                pendingLocations[particle] = location;
            }
            std::filesystem::path file = std::filesystem::u8path(
                StringUtils::Trim(config.GetString("scoring.displacement", key)));
            if (file.empty()) {
                throw std::runtime_error("[scoring.displacement]/" + particle + " (" + location +
                                         ") needs a NIEL table file");
            }
            if (file.is_relative() && !config.GetMainConfigPath().empty()) {
                file = std::filesystem::u8path(config.GetMainConfigPath()).parent_path() / file;
            }
            try {
                tables[particle] = NielTable::Load(file.u8string());
            } catch (const std::exception& error) {
                throw std::runtime_error("[scoring.displacement]/" + particle + " (" + location + "): " +
                                         error.what());
            }
        }
        SetNielTables(tables);
        nielPendingLocations_ = pendingLocations;
        nielNamesPending_ = !pendingLocations.empty();
    }
    if (enabled_ && displacementScoringEnabled_ && nielTables_.empty()) {
        throw std::runtime_error("[scoring]/displacement = true needs [scoring.displacement] with "
                                 "<particle> = <NIEL table CSV> entries (header energy_MeV,niel_MeV_cm2_g)");
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
    effectiveState_->reader = config.GetMainReader();
    effectiveState_->Accept(config.GetMainReader(), ExportEffectiveConfigFields());
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
              << ", displacement=" << (displacementScoringEnabled_ ? "true" : "false")
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

const TrajectorySettings& ScoringManager::GetTrajectorySettings() const
{
    return trajectories_.GetSettings();
}

bool ScoringManager::RecordsTrajectories() const
{
    return trajectories_.IsRecording();
}

void ScoringManager::RecordTrajectoryStep(const G4Step* step)
{
    trajectories_.RecordStep(step);
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
