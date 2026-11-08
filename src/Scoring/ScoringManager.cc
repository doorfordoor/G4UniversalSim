#include "Scoring/ScoringManager.hh"

#include "Config/ConfigManager.hh"
#include "Config/EffectiveRuntime.hh"
#include "Config/InputProvenance.hh"
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

#include <algorithm>
#include <exception>
#include <cmath>
#include <filesystem>
#include <limits>
#include <fstream>
#include <iterator>
#include <memory>
#include <set>
#include <iostream>
#include <cstdint>
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


// ---------------------------------------------------------------------------
// Roadmap H2-2: [scoring.filter.<scorer>] / [scoring.spectrum.<scorer>] support.
// ---------------------------------------------------------------------------
constexpr const char* kFilterSectionPrefix = "scoring.filter.";
constexpr const char* kSpectrumSectionPrefix = "scoring.spectrum.";

bool IsVolumeFilterSection(const std::string& section)
{
    return section.rfind(kFilterSectionPrefix, 0) == 0;
}

bool IsVolumeSpectrumSection(const std::string& section)
{
    return section.rfind(kSpectrumSectionPrefix, 0) == 0;
}

bool HasVolumeSections(const ConfigManager& config)
{
    for (const IniSectionInfo& info : config.GetSectionInfo()) {
        if (IsVolumeFilterSection(info.section) || IsVolumeSpectrumSection(info.section)) return true;
    }
    return false;
}

std::string VolumeSectionLocation(const ConfigManager& config, const IniSectionInfo& info)
{
    const std::string path = config.GetMainConfigPath();
    return (path.empty() ? std::string("<main ini>") : path) + ":" + std::to_string(info.lineNumber) +
           " [" + info.section + "]";
}

std::string JoinNames(const std::set<std::string>& names)
{
    std::string text;
    for (const std::string& name : names) {
        if (!text.empty()) text += ", ";
        text += name;
    }
    return text;
}

void RejectUnknownVolumeKeys(const ConfigManager& config, const IniSectionInfo& info,
                             const std::set<std::string>& allowed)
{
    for (const std::string& key : config.GetKeys(info.section)) {
        if (allowed.count(key) != 0) continue;
        throw std::runtime_error("Unknown key '" + key + "' in [" + info.section + "] at " +
                                 VolumeSectionLocation(config, info) + "; expected " + JoinNames(allowed));
    }
}

double VolumeEnergy(const ConfigManager& config, const IniSectionInfo& info, const std::string& key,
                    const std::string& text, bool minimum)
{
    double value = 0.0;
    try {
        value = UnitParser::ParseEnergy(text);
    } catch (const std::exception&) {
        throw std::runtime_error("[" + info.section + "]/" + key + " at " + VolumeSectionLocation(config, info) +
                                 " is not a valid energy: '" + text + "'");
    }
    if (!std::isfinite(value) || (minimum && value < 0.0)) {
        throw std::runtime_error("[" + info.section + "]/" + key + " at " + VolumeSectionLocation(config, info) +
                                 " must be a finite " + (minimum ? "non-negative " : "") + "energy, got '" + text +
                                 "'");
    }
    return value;
}

void ParseVolumeParticles(const ConfigManager& config, const IniSectionInfo& info, bool& allParticles,
                          std::set<std::string>& particles)
{
    allParticles = false;
    particles.clear();
    if (!config.HasKey(info.section, "particles")) return;
    const std::string raw = StringUtils::Trim(config.GetString(info.section, "particles"));
    if (raw.empty()) {
        throw std::runtime_error("[" + info.section + "]/particles at " + VolumeSectionLocation(config, info) +
                                 " must list at least one Geant4 particle name or 'all'");
    }
    std::vector<std::string> tokens;
    for (const std::string& piece : StringUtils::Split(raw, ',')) {
        const std::string token = StringUtils::Trim(piece);
        if (token.empty()) {
            throw std::runtime_error("[" + info.section + "]/particles at " + VolumeSectionLocation(config, info) +
                                     " contains an empty particle name");
        }
        tokens.push_back(token);
    }
    const bool hasAll = std::find(tokens.begin(), tokens.end(), "all") != tokens.end();
    if (hasAll) {
        if (tokens.size() != 1) {
            throw std::runtime_error("[" + info.section + "]/particles at " + VolumeSectionLocation(config, info) +
                                     " cannot mix 'all' with other particle names");
        }
        allParticles = true;
        return;
    }
    for (const std::string& token : tokens) particles.insert(token);
}

bool RequireCsvForSpectra(const OutputManager* output, const std::vector<std::string>& sections,
                          const std::string& stage)
{
    if (sections.empty() || !output) return true;
    if (output->WritesCsv()) return true;
    std::string message = "Kinetic-energy spectra require CSV output; " + stage + " resolved format is ";
    message += OutputManager::FormatName(output->GetFormat());
    message += " (requested " + std::string(OutputManager::FormatName(output->GetRequestedFormat()));
    const std::string reason = output->FormatSelectionReason();
    if (!reason.empty()) message += ", reason: " + reason;
    message += ") for ";
    for (std::size_t i = 0; i < sections.size(); ++i) {
        if (i != 0) message += ", ";
        message += "[" + sections[i] + "]";
    }
    throw std::runtime_error(message);
}

}  // namespace

ScoringManager::ScoringManager() = default;
ScoringManager::~ScoringManager() = default;

std::unique_ptr<ScoringManager> ScoringManager::CloneForThread(OutputManager* outputManager,
                                                               int threadId) const
{
    // Validate the entire collection before invoking any factory (also sequential).
    const auto descriptions = GetScorerDescriptions();
    auto clone = std::make_unique<ScoringManager>();
    clone->outputManager_ = outputManager;
    clone->scorerFactories_ = scorerFactories_;
    clone->scorerFactories_.Freeze();
    clone->letParticleLocation_ = letParticleLocation_;
    clone->phaseParticleLocation_ = phaseParticleLocation_;
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
    clone->filterSpecs_ = filterSpecs_;
    clone->spectrumSpecs_ = spectrumSpecs_;
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
    for (const auto& description : descriptions) {
        clone->RegisterDescription(description, threadId, builtinScorerIds_.count(description.Id()) != 0);
    }
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
    letParticleLocation_ = "C++ SetLETParticles";
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
    enteredScorers_.clear();
    enteredScorerRun_ = -1;
    scorerRunReady_ = false;
    scorers_.clear();
    builtinScorerIds_.clear();
    scorerDescriptions_.clear();
    nielTables_.clear();
    nielNamesPending_ = false;
    nielPendingLocations_.clear();
    filterSpecs_.clear();
    spectrumSpecs_.clear();
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

void ScoringManager::RegisterScorerFactory(const std::string& type, ScorerFactoryRegistry::Factory factory)
{
    scorerFactories_.Register(type, factory);
}

void ScoringManager::RegisterScorer(const ScorerDescription& description)
{
    // These five IDs retain the existing Manager setters as their sole authority.
    // Extensions may use other IDs, including with an explicitly chosen builtin type.
    for (const auto* id : {"edep", "let", "dose", "fluence", "displacement"})
        if (description.Id() == id)
            throw std::runtime_error("Reserved builtin scorer id: " + description.Id() + "; use the Manager settings");
    // Registration is not worker construction, even in a sequential process.
    RegisterDescription(description, -1, false);
}

void ScoringManager::RegisterDescription(const ScorerDescription& description, int threadId, bool builtin)
{
    if (HasScorer(description.Id())) throw std::runtime_error("Duplicate scorer id: " + description.Id());
    // Prepare all allocations before publishing either the descriptor or instance.
    auto descriptions = scorerDescriptions_;
    auto builtinIds = builtinScorerIds_;
    if (builtin) builtinIds.insert(description.Id());
    else descriptions.emplace(description.Id(), description);
    scorers_.reserve(scorers_.size() + 1);
    auto instance = scorerFactories_.Create(description, threadId);
    scorers_.push_back(std::move(instance));
    scorerDescriptions_.swap(descriptions);
    builtinScorerIds_.swap(builtinIds);
}

ScorerDescription ScoringManager::DescribeBuiltin(const std::string& id) const
{
    ScorerSettings settings;
    bool enabled = false;
    if (id == "edep") {
        enabled = edepScoringEnabled_;
        settings.rawEnabled = edepRawHistogramEnabled_;
        settings.weightedEnabled = edepWeightedHistogramEnabled_;
        settings.volumeSummary = edepVolumeSummaryEnabled_;
        settings.particleSummary = edepParticleSummaryEnabled_;
        settings.rawHistogram = {rawEdepHistogram_.bins, rawEdepHistogram_.min, rawEdepHistogram_.max, rawEdepHistogram_.configured};
        settings.weightedHistogram = {weightedEdepHistogram_.bins, weightedEdepHistogram_.min, weightedEdepHistogram_.max, weightedEdepHistogram_.configured};
    } else if (id == "let") {
        enabled = letScoringEnabled_;
        settings.particles = letParticles_;
    } else if (id == "dose") enabled = doseScoringEnabled_;
    else if (id == "fluence") enabled = fluenceScoringEnabled_;
    else if (id == "displacement") {
        enabled = displacementScoringEnabled_;
        settings.nielTables = nielTables_;
    } else throw std::runtime_error("Unknown builtin scorer identity: " + id);
    return ScorerDescription(id, id, enabled, std::move(settings));
}

std::vector<ScorerDescription> ScoringManager::GetScorerDescriptions() const
{
    std::vector<ScorerDescription> result;
    for (const auto& scorer : scorers_) {
        const auto id = NormalizeName(scorer->GetName());
        if (builtinScorerIds_.count(id)) result.push_back(DescribeBuiltin(id));
        else {
            const auto found = scorerDescriptions_.find(id);
            if (found == scorerDescriptions_.end())
                throw std::runtime_error("Cannot clone legacy scorer '" + id +
                    "': RegisterScorer(unique_ptr) has no rebuild description; register a type factory and description");
            if (found->second.Enabled() != scorer->IsEnabled())
                throw std::runtime_error("Cannot clone scorer '" + id +
                    "': instance enabled state differs from its immutable description; "
                    "register the intended configuration instead of modifying the runtime instance");
            result.push_back(found->second);
        }
    }
    return result;
}

void ScoringManager::EnsureDefaultScorers()
{
    // Build the complete missing default set locally before publishing any member.
    auto builtinIds = builtinScorerIds_;
    std::vector<std::unique_ptr<ScorerBase>> pending;
    for (const auto* id : {"edep", "let", "dose", "fluence", "displacement"}) {
        const auto description = DescribeBuiltin(id);
        if (description.Enabled() && !HasScorer(id)) {
            builtinIds.insert(id);
            pending.push_back(scorerFactories_.Create(description, G4Threading::G4GetThreadId()));
        }
    }
    scorers_.reserve(scorers_.size() + pending.size());
    for (auto& scorer : pending) scorers_.push_back(std::move(scorer));
    builtinScorerIds_.swap(builtinIds);
    if (auto* scorer = GetEdepScorer()) ApplyEdepSettings(*scorer);
    SetScorerEnabledIfExists("edep", edepScoringEnabled_);
    SetScorerEnabledIfExists("let", letScoringEnabled_);
    SetScorerEnabledIfExists("dose", doseScoringEnabled_);
    SetScorerEnabledIfExists("fluence", fluenceScoringEnabled_);
    SetScorerEnabledIfExists("displacement", displacementScoringEnabled_);
    ApplyVolumeConfigsToScorers();
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
    enteredScorers_.clear();
    enteredScorerRun_ = runID;
    scorerRunReady_ = false;
    // Test-only deterministic fault in the real Geant4 worker run callback.
    if (InjectBeginScoringFailure(runID, outputManager_)) {
        throw std::runtime_error("Injected ScoringManager::BeginRun failure");
    }
    // The particle table exists by now, so an unresolvable [scoring.displacement] key can be
    // rejected before the first event instead of leaving the DDD silently at zero.
    ValidateLegacyParticleSelectors();
    ResolvePendingNielNames();
    scorerFactories_.Freeze();
    currentRunID_ = runID;
    BeginPhaseSpaceRun();
    if (trajectories_.IsEnabled() && outputManager_) {
        outputManager_->Initialize();
        trajectories_.BeginRun(outputManager_->MakeOutputPath(outputManager_->MakeThreadFilename("trajectories.json")),
                               runID, outputManager_->GetThreadId());
    }
    if (autoCreateDefaultScorers_) EnsureDefaultScorers();
    if (!enabled_) return;
    try {
        ValidateVolumeConfigsForRun();
    } catch (const std::exception& error) {
        const std::string message = error.what();
        if (outputManager_) {
            const bool particleFailure = message.find("unknown Geant4 particle") != std::string::npos;
            outputManager_->RecordOutputFailure(particleFailure ? "scoring_filter_particle" : "scoring_volume_config",
                                                message, runID);
        }
        throw;
    }
    const auto enabledScorers = EnabledScorers();
    enteredScorers_.reserve(enabledScorers.size());
    for (ScorerBase* scorer : enabledScorers) {
        // Include a callback that throws after acquiring resources, but never
        // send EndRun to an instance whose BeginRun was not entered.
        enteredScorers_.push_back(scorer);
        scorer->BeginRun(runID);
    }
    RecordVolumeFilterAttachReceipts(runID);
    scorerRunReady_ = true;
}

void ScoringManager::EndRun(int runID)
{
    if (enteredScorerRun_ != runID) return;
    auto entered = std::move(enteredScorers_);
    enteredScorers_.clear();
    const bool ready = scorerRunReady_;
    enteredScorerRun_ = -1;
    scorerRunReady_ = false;
    std::exception_ptr firstFailure;
    const auto attempt = [&firstFailure](const auto& operation) {
        try { operation(); }
        catch (...) { if (!firstFailure) firstFailure = std::current_exception(); }
    };
    attempt([&]() { EndPhaseSpaceRun(); });
    attempt([&]() {
        const std::string trajectoryFile = trajectories_.EndRun();
        if (!trajectoryFile.empty() && outputManager_)
            outputManager_->RegisterGeneratedFile(trajectoryFile, OutputManager::ArtifactScope::Thread,
                                                  outputManager_->GetRunId(), outputManager_->GetThreadId());
    });
    for (ScorerBase* scorer : entered) attempt([&]() { scorer->EndRun(runID); });
    // A partial BeginRun is not evidence that every filter was applied.
    if (ready) attempt([&]() { RecordVolumeFilterRunReceipts(runID); });
    if (firstFailure) std::rethrow_exception(firstFailure);
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

void ScoringManager::ScoreParallelHit(const HitRecord& hit)
{
    if (!enabled_) return;
    if (outputManager_ && outputManager_->HasOutputFailure()) return;
    // The dedicated H3 routing: no hits collection, no event Edep accumulation,
    // no LET/displacement/edep scorers. Exactly one dose and one fluence call per
    // ghost step; the scorers themselves skip zero-edep/zero-length steps.
    if (doseScoringEnabled_) {
        ScorerBase* scorer = GetScorer("dose");
        if (scorer != nullptr && scorer->IsEnabled()) {
            try {
                scorer->ScoreHit(hit);
            } catch (const std::exception& error) {
                if (outputManager_) outputManager_->RecordOutputFailure("scoring_dose", error.what());
                if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
                return;
            }
        }
    }
    if (fluenceScoringEnabled_) {
        ScorerBase* scorer = GetScorer("fluence");
        if (scorer != nullptr && scorer->IsEnabled()) {
            try {
                scorer->ScoreHit(hit);
            } catch (const std::exception& error) {
                if (outputManager_) outputManager_->RecordOutputFailure("scoring_fluence", error.what());
                if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
            }
        }
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
    RecordVolumeSpectrumWriteReceipts(outputManager_->GetRunId());
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
        phaseParticleLocation_ = config.GetMainConfigPath();
        for (const auto& field : config.GetFields())
            if (field.normalizedSection == "phase_space" && field.normalizedKey == "particles")
                phaseParticleLocation_ += " line " + std::to_string(field.lineNumber);
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
    if (!config.HasSection("scoring") && HasVolumeSections(config)) {
        throw std::runtime_error("[scoring.filter.*] and [scoring.spectrum.*] require a [scoring] section");
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
    if (HasVolumeSections(config)) {
        if (!autoCreateDefaultScorers_) {
            throw std::runtime_error("[scoring.filter.*] and [scoring.spectrum.*] require "
                                     "[scoring]/auto_create_default_scorers = true (no built-in scorer would be created)");
        }
        ParseVolumeConfig(config);
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
        letParticleLocation_ = config.GetMainConfigPath();
        for (const auto& field : config.GetFields())
            if (field.normalizedSection == "scoring.let" && field.normalizedKey == "particles")
                letParticleLocation_ += " line " + std::to_string(field.lineNumber);
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
    if (outputManager_) outputManager_->RegisterGeneratedFile(phaseSpaceWriter_->GetFilename(), OutputManager::ArtifactScope::Thread,
        outputManager_->GetRunId(), outputManager_->GetThreadId());
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

// ---------------------------------------------------------------------------
// Roadmap H2-2: volume filter / spectrum configuration and evidence.
// ---------------------------------------------------------------------------

namespace {

std::string FileSha256(const std::filesystem::path& path)
{
    std::ifstream input(path, std::ios::binary);
    const std::string bytes((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    return input_provenance::Sha256(bytes);
}

std::pair<long long, long long> FilterCounts(ScoringManager& manager, const std::string& scorer)
{
    if (auto* dose = dynamic_cast<DoseScorer*>(manager.GetScorer(scorer))) {
        return {dose->GetFilterAcceptedSteps(), dose->GetFilterRejectedSteps()};
    }
    if (auto* fluence = dynamic_cast<FluenceScorer*>(manager.GetScorer(scorer))) {
        return {fluence->GetFilterAcceptedSteps(), fluence->GetFilterRejectedSteps()};
    }
    if (auto* let = dynamic_cast<LETScorer*>(manager.GetScorer(scorer))) {
        return {let->GetFilterAcceptedSteps(), let->GetFilterRejectedSteps()};
    }
    if (auto* displacement = dynamic_cast<DisplacementScorer*>(manager.GetScorer(scorer))) {
        return {displacement->GetFilterAcceptedSteps(), displacement->GetFilterRejectedSteps()};
    }
    return {0, 0};
}

std::string FormatFailureMessage(const std::string& stage, const OutputManager& output,
                                 const std::vector<std::string>& sections)
{
    std::string message = "Kinetic-energy spectra require CSV output; " + stage + " resolved format is ";
    message += OutputManager::FormatName(output.GetFormat());
    message += " (requested " + std::string(OutputManager::FormatName(output.GetRequestedFormat()));
    const std::string reason = output.FormatSelectionReason();
    if (!reason.empty()) message += ", reason: " + reason;
    message += ") for ";
    for (std::size_t i = 0; i < sections.size(); ++i) {
        if (i != 0) message += ", ";
        message += "[" + sections[i] + "]";
    }
    return message;
}

}  // namespace

void ScoringManager::ParseVolumeConfig(const ConfigManager& config)
{
    filterSpecs_.clear();
    spectrumSpecs_.clear();
    const std::set<std::string> filterScorers{"dose", "fluence", "let", "displacement"};
    const std::set<std::string> spectrumScorers{"dose", "fluence", "displacement"};
    const std::set<std::string> filterKeys{"particles", "energy_min", "energy_max"};
    const std::set<std::string> spectrumKeys{"bins", "min", "max"};
    std::vector<std::string> spectrumSections;

    for (const IniSectionInfo& info : config.GetSectionInfo()) {
        const bool filterSection = IsVolumeFilterSection(info.section);
        const bool spectrumSection = IsVolumeSpectrumSection(info.section);
        if (!filterSection && !spectrumSection) continue;
        const std::string prefix = filterSection ? kFilterSectionPrefix : kSpectrumSectionPrefix;
        const std::string scorer = info.section.substr(prefix.size());
        const std::string location = VolumeSectionLocation(config, info);

        if (filterSection) {
            if (filterScorers.count(scorer) == 0) {
                throw std::runtime_error("Unknown scoring filter topic '" + scorer +
                                         "'; expected dose, fluence, let or displacement (" + location + ")");
            }
            RejectUnknownVolumeKeys(config, info, filterKeys);
            const bool scorerEnabled = scorer == "dose"        ? doseScoringEnabled_
                                       : scorer == "fluence"  ? fluenceScoringEnabled_
                                       : scorer == "let"      ? letScoringEnabled_
                                                              : displacementScoringEnabled_;
            if (!enabled_ || !scorerEnabled) {
                throw std::runtime_error("[" + info.section + "] at " + location + " requires [scoring] " +
                                         scorer + " = true (a filter cannot enable a scorer)");
            }
            VolumeFilterConfig cfg;
            cfg.section = info.section;
            cfg.location = location;
            ParseVolumeParticles(config, info, cfg.allParticles, cfg.particles);
            const bool hasParticles = config.HasKey(info.section, "particles");
            const bool hasMin = config.HasKey(info.section, "energy_min");
            const bool hasMax = config.HasKey(info.section, "energy_max");
            if (!hasParticles && !hasMin && !hasMax) {
                throw std::runtime_error("[" + info.section + "] at " + location +
                                         " declares no condition; set at least one of particles, energy_min or "
                                         "energy_max");
            }
            if (hasMin) {
                cfg.energyMinMeV =
                    VolumeEnergy(config, info, "energy_min", config.GetString(info.section, "energy_min"), true);
            }
            if (hasMax) {
                cfg.energyMaxMeV =
                    VolumeEnergy(config, info, "energy_max", config.GetString(info.section, "energy_max"), false);
            }
            if (!(cfg.energyMaxMeV > cfg.energyMinMeV)) {
                throw std::runtime_error("[" + info.section + "] at " + location +
                                         " energy_max must be greater than energy_min");
            }
            filterSpecs_.push_back(VolumeFilterSpec{scorer, std::move(cfg), location});
            continue;
        }

        if (scorer == "let") {
            throw std::runtime_error("Spectrum for scorer 'let' is not supported; LET is a ratio and cannot be "
                                     "binned additively (" + location + ")");
        }
        if (spectrumScorers.count(scorer) == 0) {
            throw std::runtime_error("Unknown scoring spectrum topic '" + scorer +
                                     "'; expected dose, fluence or displacement (" + location + ")");
        }
        RejectUnknownVolumeKeys(config, info, spectrumKeys);
        const bool scorerEnabled = scorer == "dose" ? doseScoringEnabled_
                                   : scorer == "fluence" ? fluenceScoringEnabled_
                                                          : displacementScoringEnabled_;
        if (!enabled_ || !scorerEnabled) {
            throw std::runtime_error("[" + info.section + "] at " + location + " requires [scoring] " + scorer +
                                     " = true (a spectrum cannot enable a scorer)");
        }
        if (!config.HasKey(info.section, "bins") || !config.HasKey(info.section, "min") ||
            !config.HasKey(info.section, "max")) {
            throw std::runtime_error("[" + info.section + "] at " + location + " requires bins, min and max");
        }
        const std::string binsText = StringUtils::Trim(config.GetString(info.section, "bins"));
        long long bins = 0;
        try {
            std::size_t consumed = 0;
            bins = std::stoll(binsText, &consumed);
            if (consumed != binsText.size()) bins = 0;
        } catch (const std::exception&) {
            bins = 0;
        }
        if (bins < 1) {
            throw std::runtime_error("[" + info.section + "]/bins at " + location +
                                     " must be an integer >= 1, got '" + binsText + "'");
        }
        if (bins > 1000000) {
            throw std::runtime_error("[" + info.section + "]/bins at " + location +
                                     " is unreasonably large; use at most 1000000 bins");
        }
        VolumeSpectrumConfig cfg;
        cfg.section = info.section;
        cfg.location = location;
        cfg.bins = static_cast<int>(bins);
        cfg.minMeV = VolumeEnergy(config, info, "min", config.GetString(info.section, "min"), true);
        cfg.maxMeV = VolumeEnergy(config, info, "max", config.GetString(info.section, "max"), false);
        if (!(cfg.maxMeV > cfg.minMeV)) {
            throw std::runtime_error("[" + info.section + "] at " + location +
                                     " max must be greater than min");
        }
        const double width = (cfg.maxMeV - cfg.minMeV) / static_cast<double>(cfg.bins);
        if (!std::isfinite(width) || width <= 0.0) {
            throw std::runtime_error("[" + info.section + "] at " + location +
                                     " bin width (max - min) / bins is not a representable positive finite number");
        }
        spectrumSections.push_back(info.section);
        spectrumSpecs_.push_back(VolumeSpectrumSpec{scorer, std::move(cfg), location});
    }

    if (!spectrumSections.empty() && outputManager_ && !outputManager_->WritesCsv()) {
        throw std::runtime_error(FormatFailureMessage("configuration", *outputManager_, spectrumSections));
    }
}

void ScoringManager::ApplyVolumeConfigsToScorers()
{
    for (const VolumeFilterSpec& spec : filterSpecs_) {
        auto filter = std::make_unique<VolumeFilter>(spec.config);
        if (auto* dose = dynamic_cast<DoseScorer*>(GetScorer(spec.scorer))) {
            dose->SetFilter(std::move(filter));
        } else if (auto* fluence = dynamic_cast<FluenceScorer*>(GetScorer(spec.scorer))) {
            fluence->SetFilter(std::move(filter));
        } else if (auto* let = dynamic_cast<LETScorer*>(GetScorer(spec.scorer))) {
            let->SetFilter(std::move(filter));
        } else if (auto* displacement = dynamic_cast<DisplacementScorer*>(GetScorer(spec.scorer))) {
            displacement->SetFilter(std::move(filter));
        }
    }
    for (const VolumeSpectrumSpec& spec : spectrumSpecs_) {
        auto spectrum = std::make_unique<VolumeSpectrum>(spec.config);
        if (auto* dose = dynamic_cast<DoseScorer*>(GetScorer(spec.scorer))) {
            dose->SetSpectrum(std::move(spectrum));
        } else if (auto* fluence = dynamic_cast<FluenceScorer*>(GetScorer(spec.scorer))) {
            fluence->SetSpectrum(std::move(spectrum));
        } else if (auto* displacement = dynamic_cast<DisplacementScorer*>(GetScorer(spec.scorer))) {
            displacement->SetSpectrum(std::move(spectrum));
        }
    }
}

void ScoringManager::ValidateLegacyParticleSelectors() const
{
    const auto validate = [](const std::set<std::string>& particles, const std::string& section,
                             const std::string& location) {
        if (particles.empty()) return; // existing all semantics
        auto* table = G4ParticleTable::GetParticleTable();
        for (const auto& token : particles) {
            if (table->entries() == 0)
                throw std::runtime_error("[" + section + "]/particles at " + location +
                    " cannot validate token '" + token + "': Geant4 particle table is not ready");
            if (!table->FindParticle(token))
                throw std::runtime_error("[" + section + "]/particles at " + location +
                    " lists unknown Geant4 particle '" + token + "'");
        }
    };
    validate(letParticles_, "scoring.let", letParticleLocation_);
    validate(phaseSpaceParticles_, "phase_space", phaseParticleLocation_);
}

void ScoringManager::ValidateVolumeConfigsForRun()
{
    ValidateLegacyParticleSelectors();
    if (spectrumSpecs_.empty() && filterSpecs_.empty()) return;
    // This runs before the event loop, so default scorers may not be created
    // yet (BeginRun calls EnsureDefaultScorers). The parsed enable flags are
    // therefore the authoritative record of whether a topic is active.
    const auto active = [this](const std::string& scorer) {
        if (scorer == "dose") return doseScoringEnabled_;
        if (scorer == "fluence") return fluenceScoringEnabled_;
        if (scorer == "let") return letScoringEnabled_;
        if (scorer == "displacement") return displacementScoringEnabled_;
        return false;
    };
    std::vector<std::string> spectrumSections;
    for (const VolumeSpectrumSpec& spec : spectrumSpecs_) spectrumSections.push_back(spec.config.section);
    if (!spectrumSections.empty() && outputManager_ && !outputManager_->WritesCsv()) {
        throw std::runtime_error(FormatFailureMessage("run begin", *outputManager_, spectrumSections));
    }
    for (const VolumeSpectrumSpec& spec : spectrumSpecs_) {
        if (!active(spec.scorer)) {
            throw std::runtime_error("[scoring.spectrum." + spec.scorer + "] at " + spec.location +
                                     " targets scorer '" + spec.scorer + "' which is not active; enable it in "
                                     "[scoring] or remove the spectrum section");
        }
    }
    for (const VolumeFilterSpec& spec : filterSpecs_) {
        if (!active(spec.scorer)) {
            throw std::runtime_error("[scoring.filter." + spec.scorer + "] at " + spec.location +
                                     " targets scorer '" + spec.scorer + "' which is not active; enable it in "
                                     "[scoring] or remove the filter section");
        }
        if (!spec.config.HasParticleCondition() || spec.config.allParticles) continue;
        for (const std::string& name : spec.config.particles) {
            if (G4ParticleTable::GetParticleTable()->FindParticle(name) == nullptr) {
                throw std::runtime_error("[scoring.filter." + spec.scorer + "]/particles at " + spec.location +
                                         " lists unknown Geant4 particle '" + name + "'");
            }
        }
    }
}

void ScoringManager::RecordVolumeFilterAttachReceipts(int runId)
{
    if (filterSpecs_.empty()) return;
    using namespace effective_config;
    const int actualThread = G4Threading::G4GetThreadId();
    for (const VolumeFilterSpec& spec : filterSpecs_) {
        Value energyMax = std::isfinite(spec.config.energyMaxMeV)
            ? Value(spec.config.energyMaxMeV) : Value();
        Value::Object observed{{"section", spec.config.section},
                               {"location", spec.location},
                               {"particle_filter", spec.config.HasParticleCondition()},
                               {"all_particles", spec.config.allParticles},
                               {"energy_min_MeV", spec.config.energyMinMeV},
                               {"energy_max_MeV", std::move(energyMax)}};
        if (!spec.config.allParticles) {
            observed["particles"] = Value::Array{};
            auto& list = std::get<Value::Array>(observed["particles"].data);
            for (const std::string& name : spec.config.particles) list.emplace_back(name);
        }
        auto receipt = Receipt("scoring/filter/" + spec.scorer + "/attached", std::move(observed),
                               "scoring_filter_attach", "Scorer accepted the parsed volume filter before its first event",
                               "kernel_constructed", "applied");
        auto& details = std::get<Value::Object>(receipt.data);
        details["run_id"] = runId;
        details["thread_id"] = actualThread;
        effectiveState_->Record(std::move(receipt));
    }
}

void ScoringManager::RecordVolumeFilterRunReceipts(int runId)
{
    if (filterSpecs_.empty()) return;
    using namespace effective_config;
    const int actualThread = G4Threading::G4GetThreadId();
    for (const VolumeFilterSpec& spec : filterSpecs_) {
        const auto counts = FilterCounts(*this, spec.scorer);
        const long long accepted = counts.first;
        const long long rejected = counts.second;
        const bool observedSteps = accepted + rejected > 0;
        const std::string status = observedSteps ? "applied" : "unknown";
        const std::string level = observedSteps ? "run_validated" : "thread_applied";
        const std::string reason =
            observedSteps ? "" : "no scored steps observed; runtime filtering not validated";
        // long long -> Value is ambiguous on LP64 (int64_t is long), so the
        // receipt counters are converted explicitly and keep their integer type.
        Value::Object observed{{"candidate_steps", Value(static_cast<std::int64_t>(accepted + rejected))},
                               {"accepted_steps", Value(static_cast<std::int64_t>(accepted))},
                               {"rejected_steps", Value(static_cast<std::int64_t>(rejected))},
                               {"section", spec.config.section},
                               {"location", spec.location}};
        auto receipt = Receipt("scoring/filter/" + spec.scorer, std::move(observed), "scoring_filter_run",
                               "Cumulative filter decisions observed by this thread", level, status, reason);
        auto& details = std::get<Value::Object>(receipt.data);
        details["run_id"] = runId;
        details["thread_id"] = actualThread;
        effectiveState_->Record(std::move(receipt));
    }
}

void ScoringManager::RecordVolumeSpectrumWriteReceipts(int runId)
{
    if (spectrumSpecs_.empty() || !outputManager_) return;
    using namespace effective_config;
    const int actualThread = G4Threading::G4GetThreadId();
    std::vector<OutputManager::ArtifactEvidence> artifacts;
    try {
        artifacts = outputManager_->CollectRunArtifacts(runId);
    } catch (const std::exception&) {
        artifacts.clear();
    }
    for (const VolumeSpectrumSpec& spec : spectrumSpecs_) {
        const std::string expected = outputManager_->MakeThreadFilename("spectrum_" + spec.scorer + ".csv");
        const std::filesystem::path expectedPath = std::filesystem::u8path(outputManager_->MakeOutputPath(expected));
        const OutputManager::ArtifactEvidence* found = nullptr;
        for (const auto& artifact : artifacts) {
            if (artifact.path.empty()) continue;
            const std::filesystem::path candidate = std::filesystem::u8path(artifact.path).filename();
            if (candidate == expectedPath.filename()) {
                found = &artifact;
                break;
            }
        }
        Value::Object observed{{"section", spec.config.section},
                               {"location", spec.location},
                               {"bins", spec.config.bins},
                               {"min_MeV", spec.config.minMeV},
                               {"max_MeV", spec.config.maxMeV}};
        std::string status = "unknown";
        std::string level = "thread_applied";
        std::string reason = "spectrum file was not observed in the generated-file registry";
        if (found) {
            observed["path"] = outputManager_->MakeOutputPath(expected);
            observed["sha256"] = found->sha256.has_value() ? Value(*found->sha256) : Value();
            observed["size_bytes"] = found->size_bytes.has_value() ? Value(static_cast<std::int64_t>(*found->size_bytes)) : Value();
            status = "applied";
            level = "run_validated";
            reason.clear();
        }
        auto receipt = Receipt("scoring/spectrum/" + spec.scorer, std::move(observed), "scoring_spectrum_write",
                               "Spectrum file written and registered by this thread", level, status, reason);
        auto& details = std::get<Value::Object>(receipt.data);
        details["run_id"] = runId;
        details["thread_id"] = actualThread;
        effectiveState_->Record(std::move(receipt));
    }
}
