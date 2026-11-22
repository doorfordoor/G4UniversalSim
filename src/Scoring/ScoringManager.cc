#include "Scoring/ScoringManager.hh"
#ifdef G4USIM_WITH_NATIVE_AT_REST_OBSERVER
#include "Scoring/NativeClockEvent.hh"
#endif

#include "Config/ConfigManager.hh"
#include "Geometry/GeometryRegistry.hh"
#include "Hits/SensitiveDetector.hh"
#include "G4Material.hh"
#include "G4PhantomParameterisation.hh"
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
#include "Scoring/OpticalBoundaryObservation.hh"
#include "Scoring/NumericChecks.hh"
#include "Scoring/ThreadLocalScoringContext.hh"
#include "G4SystemOfUnits.hh"
#include "G4Threading.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"
#include "G4EmProcessSubType.hh"
#include "G4Event.hh"
#include "G4IonTable.hh"
#include "G4NistManager.hh"
#include "G4NucleiProperties.hh"
#include "G4ParticleDefinition.hh"
#include "G4ParticleTable.hh"
#include "G4PhysicalVolumeStore.hh"
#include "G4RunManager.hh"
#include "G4TransportationManager.hh"
#include "G4Navigator.hh"
#include "G4PVPlacement.hh"
#include "G4Step.hh"
#include "G4Track.hh"
#include "G4VProcess.hh"

#include <algorithm>
#include <charconv>
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
// A phase-space selector is a name filter, not a request to construct a
// particle. A ground-state ion may be known to Geant4 but absent from the
// particle dictionary until GPS/replay (or transport) first needs it.
bool IsKnownPhaseSpaceGroundStateIon(const std::string& name)
{
    const auto massStart = name.find_first_of("0123456789");
    if (massStart == std::string::npos || massStart == 0 || name.size() - massStart > 3) return false;

    int mass = 0;
    const auto end = name.data() + name.size();
    const auto parsed = std::from_chars(name.data() + massStart, end, mass);
    if (parsed.ec != std::errc{} || parsed.ptr != end) return false;

    const int atomicNumber = G4NistManager::Instance()->GetZ(name.substr(0, massStart));
    // Despite the SDK method name, this is membership in its AME mass table.
    // Do not use a mass estimate as evidence that a name is known.
    if (atomicNumber <= 0 || mass < atomicNumber || !G4NucleiProperties::IsInStableTable(mass, atomicNumber))
        return false;

    auto* ions = G4IonTable::GetIonTable();
    // The existing definition takes precedence, including light nuclei whose
    // actual names are proton, deuteron, triton, He3 and alpha.
    if (const auto* existing = ions->FindIon(atomicNumber, mass, 0.0))
        return existing->GetParticleName() == name;
    return ions->GetIonName(atomicNumber, mass, 0) == name;
}

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
const std::string kSelectionPrefix = "scoring.selection.";
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
        if (IsVolumeFilterSection(info.section) || IsVolumeSpectrumSection(info.section) ||
            info.section.rfind(kSelectionPrefix, 0) == 0) return true;
    }
    return false;
}

void ValidateOrdinaryPlacement(const std::string& selection, const std::string& path)
{
    const auto parts = StringUtils::Split(path.substr(1), '/', false);
    auto* current = G4TransportationManager::GetTransportationManager()->GetNavigatorForTracking()->GetWorldVolume();
    auto fail = [&](const std::string& why) {
        throw std::runtime_error("[scoring.selection." + selection + "] " + path + ": " + why);
    };
    for (size_t depth = 0; depth < parts.size(); ++depth) {
        const auto& part = parts[depth];
        const auto hash = part.rfind('#');
        if (hash == std::string::npos || hash == 0) fail("expected physical name#copy number");
        const auto name = part.substr(0, hash);
        if (depth > 0) {
            auto* mother = current->GetLogicalVolume();
            current = nullptr;
            for (size_t index = 0; index < mother->GetNoDaughters(); ++index) {
                auto* child = mother->GetDaughter(index);
                if (child->GetName() != name) continue;
                if (child->IsReplicated() || child->IsParameterised())
                    fail("replica and parameterised placement selection is unsupported");
                if (part != name + "#" + std::to_string(child->GetCopyNo())) continue;
                if (!dynamic_cast<const G4PVPlacement*>(child)) fail("unsupported physical placement type");
                if (current) fail("ambiguous ordinary daughter");
                current = child;
            }
        }
        if (!current || part != std::string(current->GetName()) + "#" + std::to_string(current->GetCopyNo()))
            fail("unmatched physical placement " + part);
    }
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
    clone->geometryRegistry_ = geometryRegistry_;
    clone->scorerFactories_ = scorerFactories_;
    clone->scorerFactories_.Freeze();
    clone->letParticleLocation_ = letParticleLocation_;
    clone->phaseParticleLocation_ = phaseParticleLocation_;
    clone->effectiveState_ = effectiveState_->Clone();
    clone->enabled_ = enabled_;
    clone->hitOutputEnabled_ = hitOutputEnabled_;
    clone->hitVolumePathEnabled_ = hitVolumePathEnabled_;
    clone->eventEdepOutputEnabled_ = eventEdepOutputEnabled_;
    clone->opticalPhotonCountsEnabled_ = opticalPhotonCountsEnabled_;
    clone->opticalBoundaryObservationsEnabled_ = opticalBoundaryObservationsEnabled_;
    clone->clockLibraryHash_ = clockLibraryHash_;
    clone->activationObservationsEnabled_ = activationObservationsEnabled_;
    clone->activationObservationSchemaVersion_ = activationObservationSchemaVersion_;
    clone->edepScoringEnabled_ = edepScoringEnabled_;
    clone->letScoringEnabled_ = letScoringEnabled_;
    clone->letParticles_ = letParticles_;
    clone->doseScoringEnabled_ = doseScoringEnabled_;
    clone->fluenceScoringEnabled_ = fluenceScoringEnabled_;
    clone->displacementScoringEnabled_ = displacementScoringEnabled_;
    clone->nielTables_ = nielTables_;
    clone->nielNamesPending_ = nielNamesPending_;
    clone->nielPendingLocations_ = nielPendingLocations_;
    clone->namedPlacementPaths_ = namedPlacementPaths_;
    clone->filterSpecs_ = filterSpecs_;
    clone->spectrumSpecs_ = spectrumSpecs_;
    clone->autoCreateDefaultScorers_ = autoCreateDefaultScorers_;
    clone->namedH1_ = namedH1_;
    clone->namedH2_ = namedH2_;
    clone->eventNtuples_ = eventNtuples_;
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
    namedPlacementPaths_.clear();
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
    voxelEvent_.clear();
    voxelSteps_.clear();
    voxelEventID_ = -1;
    voxelCompletedEvents_.clear();
    if (IsVoxelScoringRequested()) {
        try {
            for (const auto& [leaf, binding] : geometryRegistry_->GetVoxelScoringBindings()) {
                const auto* sd = dynamic_cast<const SensitiveDetector*>(leaf->GetLogicalVolume()->GetSensitiveDetector());
                if (!sd || !sd->isActive() || !sd->IsScoringEnabled()) {
                    throw std::runtime_error("voxel grid '" + binding.gridId + "' has no active worker SensitiveDetector binding");
                }
            }
        } catch (const std::exception& error) {
            if (outputManager_) outputManager_->RecordOutputFailure("voxel_sd_binding", error.what(), runID);
            throw;
        }
    }
    enteredScorerRun_ = runID;
    scorerRunReady_ = false;
    // Test-only deterministic fault in the real Geant4 worker run callback.
    if (InjectBeginScoringFailure(runID, outputManager_)) {
        throw std::runtime_error("Injected ScoringManager::BeginRun failure");
    }
    if (activationObservationsEnabled_) {
        try {
            if (!enabled_) throw std::runtime_error("[scoring]/activation_observations requires [scoring]/enabled = true");
            activationDecayThresholdSeconds_ = activation_observation::ValidateRun();
        } catch (const std::exception& error) {
            if (outputManager_) outputManager_->RecordOutputFailure("activation_observations_begin_run", error.what(), runID);
            throw;
        }
    }
    // The particle table exists by now, so an unresolvable [scoring.displacement] key can be
    // rejected before the first event instead of leaving the DDD silently at zero.
    ValidateLegacyParticleSelectors();
    ResolvePendingNielNames();
    scorerFactories_.Freeze();
    currentRunID_ = runID;
    if ((!namedH1_.empty() || !namedH2_.empty() || !eventNtuples_.empty()) && (!enabled_ || !outputManager_ || !outputManager_->WritesCsv()))
        throw std::runtime_error("named histogram requires enabled scoring and CSV output at run start");
    for (auto& histogram : namedH1_) histogram.Reset();
    for (auto& histogram : namedH2_) histogram.Reset();
#ifdef G4USIM_WITH_NATIVE_AT_REST_OBSERVER
    if (!clockLibraryHash_.empty())
        clockEvent_ = std::make_unique<activation_observation::ClockEvent>(clockLibraryHash_);
#endif
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
#ifdef G4USIM_WITH_NATIVE_AT_REST_OBSERVER
    if (clockEvent_ && clockEvent_->active) {
        clockEvent_->Discard();
        ReportScoringFailure("native_clock_end_run", "missing native event closure");
    }
#endif
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

bool ScoringManager::IsOpticalPhotonCountingEnabled() const
{
    return enabled_ && opticalPhotonCountsEnabled_;
}

void ScoringManager::CountOpticalSecondaries(const G4Step& step)
{
    if (!IsOpticalPhotonCountingEnabled() ||
        (outputManager_ && outputManager_->HasOutputFailure())) return;
    try {
        // Geant4 has accepted these secondaries for this step. The cumulative
        // secondary list would count earlier births again on subsequent steps.
        const auto* secondaries = step.GetSecondaryInCurrentStep();
        for (const auto* secondary : *secondaries) {
            // Read the track's definition. OpticalPhoton() can register a
            // new particle if the active physics list has no optical module.
            if (secondary->GetParticleDefinition()->GetParticleName() != "opticalphoton") continue;
            const auto* creator = secondary->GetCreatorProcess();
            const int subtype = creator && creator->GetProcessType() == fElectromagnetic
                ? creator->GetProcessSubType() : -1;
            auto& count = subtype == fScintillation ? opticalPhotonCounts_.scintillation
                : subtype == fCerenkov ? opticalPhotonCounts_.cerenkov
                : opticalPhotonCounts_.other;
            if (count == std::numeric_limits<std::uint64_t>::max())
                throw std::overflow_error("Optical secondary count overflow");
            ++count;
        }
    } catch (const std::exception& error) {
        ReportScoringFailure("optical_photon_counts_accumulate", error.what());
    } catch (...) {
        ReportScoringFailure("optical_photon_counts_accumulate", "unknown exception");
    }
}

bool ScoringManager::IsOpticalBoundaryObservationEnabled() const
{
    return enabled_ && opticalBoundaryObservationsEnabled_;
}

void ScoringManager::ObserveOpticalBoundary(const G4Step& step)
{
    if (!IsOpticalBoundaryObservationEnabled() ||
        step.GetTrack()->GetParticleDefinition()->GetParticleName() != "opticalphoton" ||
        (outputManager_ && outputManager_->HasOutputFailure())) return;
    try {
        if (auto record = optical_boundary::ObserveStep(step, currentRunID_, currentEventID_))
            opticalBoundarySteps_.push_back(std::move(*record));
    } catch (const std::exception& error) {
        ReportScoringFailure("optical_boundary_observation", error.what());
    } catch (...) {
        ReportScoringFailure("optical_boundary_observation", "unknown exception");
    }
}

bool ScoringManager::IsActivationObservationEnabled() const
{
    return enabled_ && activationObservationsEnabled_;
}

void ScoringManager::ObserveActivation(const G4Step& step)
{
    if (!IsActivationObservationEnabled() || (outputManager_ && outputManager_->HasOutputFailure())) return;
    try {
#ifdef G4USIM_WITH_NATIVE_AT_REST_OBSERVER
        if (clockEvent_) clockEvent_->Observe(step);
#endif
        activationEvent_.ObserveStep(step, currentRunID_, currentEventID_, activationObservationSchemaVersion_);
    } catch (const std::exception& error) {
        ReportScoringFailure("activation_observation", error.what());
    } catch (...) {
        ReportScoringFailure("activation_observation", "unknown exception");
    }
}

void ScoringManager::ObserveActivationStackedTrack(const G4Track& track)
{
    if (!IsActivationObservationEnabled()) return;
    try {
        activationEvent_.ObserveStackedTrack(track, activationObservationSchemaVersion_ >= 2);
    } catch (const std::exception& error) {
        ReportScoringFailure("activation_observation_stack", error.what());
    } catch (...) {
        ReportScoringFailure("activation_observation_stack", "unknown exception");
    }
}

void ScoringManager::ClearPendingActivationBirths() noexcept
{
    if (IsActivationObservationEnabled()) activationEvent_.ClearPendingBirths();
}

void ScoringManager::BeginEvent(int eventID)
{
    if (outputManager_ && outputManager_->HasOutputFailure()) return;
    try {
#ifdef G4USIM_WITH_NATIVE_AT_REST_OBSERVER
        if (clockEvent_) clockEvent_->Begin(currentRunID_, eventID);
#endif
        if (IsVoxelScoringRequested()) {
            if (voxelEventID_ >= 0 || eventID < 0 ||
                (!voxelCompletedEvents_.empty() && eventID <= *voxelCompletedEvents_.rbegin())) {
                throw std::runtime_error("invalid or duplicate voxel event begin");
            }
            voxelEvent_.clear();
            voxelSteps_.clear();
            voxelEventID_ = eventID;
        }
        currentEventID_ = eventID;
        opticalPhotonCounts_ = {currentRunID_, eventID};
        opticalBoundarySteps_.clear();
        activationEvent_.Clear();
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

void ScoringManager::EndEvent(int eventID, bool aborted, const G4Event* nativeEvent)
{
#ifdef G4USIM_WITH_NATIVE_AT_REST_OBSERVER
    if (clockEvent_) {
        try {
            if (!outputManager_) throw std::runtime_error("missing clock output");
            if (outputManager_->HasOutputFailure()) { clockEvent_->Discard(); return; }
            if (aborted || !nativeEvent || nativeEvent->IsAborted() ||
                nativeEvent->GetEventID() != eventID || currentEventID_ != eventID)
                throw std::runtime_error("aborted or mismatched native clock event");
            clockEvent_->Stage(*nativeEvent, currentRunID_, eventID);
        } catch (const std::exception& e) {
            clockEvent_->Discard(); ReportScoringFailure("native_clock_event", e.what()); return;
        } catch (...) {
            clockEvent_->Discard(); ReportScoringFailure("native_clock_event", "unknown exception"); return;
        }
    }
#endif
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

        const EventEdepRecord record{currentRunID_, currentEventID_, currentEventRawEdep_, currentEventWeightedEdep_};
        if (enabled_ && eventEdepOutputEnabled_ && outputManager_ &&
            !outputManager_->HasOutputFailure()) {
            try {
                outputManager_->WriteEventEdep(record);
            } catch (const std::exception& error) {
                outputManager_->RecordOutputFailure("event_edep_write", error.what());
                if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
            }
        }
        if (IsOpticalPhotonCountingEnabled() && !aborted && outputManager_ &&
            !outputManager_->HasOutputFailure()) {
            try {
                outputManager_->WriteOpticalPhotonCounts(opticalPhotonCounts_);
            } catch (const std::exception& error) {
                ReportScoringFailure("optical_photon_counts_write", error.what());
            }
        }
        if (!aborted && !opticalBoundarySteps_.empty() && outputManager_ &&
            !outputManager_->HasOutputFailure()) {
            try {
                outputManager_->WriteOpticalBoundarySteps(opticalBoundarySteps_);
            } catch (const std::exception& error) {
                ReportScoringFailure("optical_boundary_steps_write", error.what());
            }
        }
        opticalBoundarySteps_.clear();
        if (!aborted && IsActivationObservationEnabled() && outputManager_ &&
            !outputManager_->HasOutputFailure()) {
            try {
                if (activationObservationSchemaVersion_ == 3) {
                    if (!nativeEvent || eventID != currentEventID_ ||
                        nativeEvent->GetEventID() != eventID || nativeEvent->IsAborted())
                        throw std::runtime_error("activation event primary summary requires the current native event");
                    activationEvent_.AppendCompletedEventPrimaries(*nativeEvent, currentRunID_);
                }
                outputManager_->WriteActivationObservations(activationEvent_.Records(),
                                                           activationObservationSchemaVersion_);
            } catch (const std::exception& error) {
                ReportScoringFailure("activation_observations_write", error.what());
            }
        }
#ifdef G4USIM_WITH_NATIVE_AT_REST_OBSERVER
        if (clockEvent_ && !outputManager_->HasOutputFailure())
            clockEvent_->Publish(*outputManager_, currentRunID_, eventID);
#endif
        activationEvent_.Clear();
        if (IsVoxelScoringRequested() && outputManager_ && !outputManager_->HasOutputFailure()) {
            try {
                if (aborted || !nativeEvent || nativeEvent->IsAborted() || nativeEvent->GetEventID() != eventID
                    || voxelEventID_ != eventID || currentEventID_ != eventID
                    || voxelCompletedEvents_.count(eventID)) {
                    throw std::runtime_error("aborted, missing or duplicate voxel event closure");
                }
                outputManager_->WriteVoxelEvent(eventID, voxelEvent_);
                voxelCompletedEvents_.insert(eventID);
                voxelEventID_ = -1;
                voxelEvent_.clear();
                voxelSteps_.clear();
            } catch (const std::exception& error) {
                ReportScoringFailure("voxel_event_write", error.what());
            }
        }
        if ((!namedH1_.empty() || !namedH2_.empty() || !eventNtuples_.empty()) && !aborted && !outputManager_->HasOutputFailure()) {
            if (!enabled_ || !nativeEvent || nativeEvent->IsAborted() || nativeEvent->GetEventID() != eventID ||
                eventID != currentEventID_) throw std::runtime_error("invalid named histogram event closure");
            for (auto& histogram : namedH1_) histogram.FillUnitAtEdges(currentEventRawEdep_ / MeV);
            for (auto& histogram : namedH2_) histogram.Fill(currentEventRawEdep_ / MeV, currentEventWeightedEdep_ / MeV);
            if (!eventNtuples_.empty()) outputManager_->WriteEventNtuples(eventNtuples_, record);
        }
    } catch (const std::exception& error) {
        ReportScoringFailure("scoring_end_event", error.what());
    } catch (...) {
        ReportScoringFailure("scoring_end_event", "unknown exception");
    }
}

void ScoringManager::ConfigureNamedHistograms(const ConfigManager& config)
{
    const std::string h1 = "analysis.h1.";
    const std::string h2 = "analysis.h2.";
    const std::string ntuple = "analysis.ntuple.";
    eventNtuples_.clear();
    namedH2_.clear();
    int totalCells = 0;
    namedH1_.clear();
    int totalBins = 0;
    for (const auto& duplicate : config.GetMainReader().GetDuplicates()) {
        if (duplicate.section.rfind(h1, 0) == 0 || duplicate.section.rfind(h2, 0) == 0 || duplicate.section.rfind(ntuple, 0) == 0)
            throw std::runtime_error("duplicate [" + duplicate.section + "] " + duplicate.key);
    }
    for (const auto& info : config.GetSectionInfo()) {
        if (info.section == "analysis.h1" || info.section == "analysis.h2" || info.section == "analysis.ntuple")
            throw std::runtime_error(info.section + " requires a name");
        const bool twoDimensional = info.section.rfind(h2, 0) == 0;
        const bool eventTable = info.section.rfind(ntuple, 0) == 0;
        if (!eventTable && !twoDimensional && info.section.rfind(h1, 0) != 0) continue;
        const auto name = info.originalSection.substr(eventTable ? ntuple.size() : h1.size());
        const auto fail = [&](const std::string& reason) {
            throw std::runtime_error(VolumeSectionLocation(config, info) + ": " + reason);
        };
        if (name.empty() || name.size() > 32 || name.front() < 'a' || name.front() > 'z' ||
            name.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_") != std::string::npos)
            fail("invalid histogram name");
        if (!config.HasSection("scoring") || !config.GetBool("scoring", "enabled", enabled_) ||
            !outputManager_ || !outputManager_->WritesCsv()) fail("requires enabled scoring and CSV output");
        if (eventTable) {
            if (eventNtuples_.size() >= 16) fail("too many event ntuples");
            for (const auto& key : config.GetKeys(info.section))
                if (key != "source" && key != "columns") fail("unknown key " + key);
            if (config.GetString(info.section, "source") != "event_edep") fail("unsupported ntuple source");
            auto columns = StringUtils::Split(config.GetString(info.section, "columns"), ',', false);
            if (columns.empty() || columns.size() > 2) fail("select one or two energy columns");
            for (auto& column : columns) {
                column = StringUtils::Trim(column);
                if (!NamedEventNtuple::IsEnergyColumn(column)) fail("unsupported ntuple column " + column);
            }
            if (columns.size() == 2 && columns.front() == columns.back()) fail("duplicate ntuple column");
            eventNtuples_.push_back({name, std::move(columns)});
            continue;
        }
        static const std::set<std::string> oneKeys{"quantity", "bins", "min_mev", "max_mev"};
        static const std::set<std::string> twoKeys{"x_quantity", "x_bins", "x_min_mev", "x_max_mev",
                                                   "y_quantity", "y_bins", "y_min_mev", "y_max_mev"};
        const auto& keys = twoDimensional ? twoKeys : oneKeys;
        for (const auto& key : config.GetKeys(info.section))
            if (!keys.count(key)) fail("unknown key " + key);
        const auto axis = [&](const std::string& prefix, const char* quantity) {
            if (config.GetString(info.section, prefix + "quantity") != quantity)
                throw std::runtime_error("unsupported " + prefix + "quantity");
            return EqualHistogramAxis{config.GetInt(info.section, prefix + "bins"),
                                      config.GetDouble(info.section, prefix + "min_mev"),
                                      config.GetDouble(info.section, prefix + "max_mev")};
        };
        try {
            if (twoDimensional) {
                const auto x = axis("x_", "event_edep_raw");
                const auto y = axis("y_", "event_edep_weighted");
                if (namedH2_.size() >= 16 || x.bins < 1 || y.bins < 1 || x.bins > 65534 || y.bins > 65534 ||
                    x.bins + 2 > (65536 - totalCells) / (y.bins + 2))
                    throw std::runtime_error("histogram cell budget exceeded");
                x.ValidateEdges();
                y.ValidateEdges();
                namedH2_.emplace_back(name, x, y);
                totalCells += (x.bins + 2) * (y.bins + 2);
            } else {
                const auto x = axis("", "event_edep_raw");
                if (namedH1_.size() >= 16 || x.bins < 1 || x.bins > 65536 - totalBins)
                    throw std::runtime_error("histogram budget exceeded");
                x.ValidateEdges();
                namedH1_.emplace_back(name, x.bins, x.low, x.high);
                totalBins += x.bins;
            }
        } catch (const std::exception& error) {
            fail(error.what());
        }
    }
}

bool ScoringManager::IsVoxelScoringRequested() const
{
    return geometryRegistry_ && geometryRegistry_->HasVoxelScoring();
}

bool ScoringManager::ScoreVoxelStep(const G4Step& step)
{
    if (!IsVoxelScoringRequested()) return false;
    const auto* pre = step.GetPreStepPoint();
    if (!pre) return false;
    const auto* binding = geometryRegistry_->FindVoxelScoring(pre->GetPhysicalVolume());
    const auto* track = step.GetTrack();
    const bool optical = track && track->GetParticleDefinition()->GetParticleName() == "opticalphoton";
    if (!binding) {
        const auto* post = step.GetPostStepPoint();
        if (!optical || !post || !geometryRegistry_->FindVoxelScoring(post->GetPhysicalVolume())) return false;
        ReportScoringFailure("voxel_sd_step", "voxel SD excludes optical dispatch to the post-step leaf");
        return true;
    }
    if (!outputManager_ || outputManager_->HasOutputFailure()) return true;
    try {
        if (G4Threading::G4GetThreadId() >= 0 && AIHL::GetCurrentThreadScoringManager() != this) {
            throw std::runtime_error("voxel SD requires the active worker scoring manager");
        }
        const auto* manager = G4RunManager::GetRunManager();
        const auto* event = manager ? manager->GetCurrentEvent() : nullptr;
        if (!enabled_ || !event || event->IsAborted() || event->GetEventID() != voxelEventID_
            || voxelEventID_ < 0 || voxelEventID_ != currentEventID_) {
            throw std::runtime_error("voxel hit outside an open scoring event");
        }
        const auto* touch = pre->GetTouchable();
        const auto* material = pre->GetMaterial();
        if (!touch || touch->GetHistoryDepth() < 1 || touch->GetVolume(1) != binding->container) {
            throw std::runtime_error("voxel step has no matching pre-step container touchable");
        }
        const int cell = touch->GetCopyNumber();
        if (cell < 0 || static_cast<std::size_t>(cell) >= binding->parameterisation->GetNoVoxels()
            || !material || material != binding->parameterisation->GetMaterial(static_cast<std::size_t>(cell))) {
            throw std::runtime_error("voxel step has invalid copy number or actual material");
        }
        if (!track || optical) {
            throw std::runtime_error("voxel SD ordinary-EM slice excludes optical InvokeSD dispatch");
        }
        const double energy = step.GetTotalEnergyDeposit();
        const double weight = pre->GetWeight();
        if (!std::isfinite(energy) || energy < 0 || !std::isfinite(weight) || weight < 0) {
            throw std::runtime_error("voxel step has invalid deposit or pre-step weight");
        }
        if (energy == 0) return true;
        if (track->GetTrackID() <= 0 || track->GetCurrentStepNumber() <= 0
            || !voxelSteps_.emplace(track->GetTrackID(), track->GetCurrentStepNumber()).second) {
            throw std::runtime_error("voxel step has invalid or duplicate native track/step identity");
        }
        const auto& dims = binding->shape;
        const std::array<int, 3> index{cell % dims[0], cell / dims[0] % dims[1], cell / (dims[0] * dims[1])};
        auto& record = voxelEvent_.try_emplace({binding->gridId, cell},
            VoxelEdepRecord{index, material->GetName(), 0, 0, 0}).first->second;
        if (record.material != material->GetName()) throw std::runtime_error("voxel material changed during event");
        const double raw = record.rawEdep + energy;
        const double weighted = record.weightedEdep + energy * weight;
        if (!std::isfinite(raw) || !std::isfinite(weighted) ||
            record.steps == std::numeric_limits<std::uint64_t>::max()) {
            throw std::runtime_error("voxel event accumulation overflow");
        }
        record.rawEdep = raw;
        record.weightedEdep = weighted;
        ++record.steps;
    } catch (const std::exception& error) {
        ReportScoringFailure("voxel_sd_step", error.what());
    } catch (...) {
        ReportScoringFailure("voxel_sd_step", "unknown exception");
    }
    // A bound leaf never falls through to the ordinary hit/scorer path.
    return true;
}

void ScoringManager::FinishVoxelShard(int eventsProcessed)
{
    if (!IsVoxelScoringRequested()) return;
    if (!outputManager_ || voxelEventID_ >= 0 || eventsProcessed < 0 ||
        voxelCompletedEvents_.size() != static_cast<std::size_t>(eventsProcessed)) {
        throw std::runtime_error("voxel worker did not close its completed events");
    }
    outputManager_->FinishVoxelShard(currentRunID_, voxelCompletedEvents_);
}

void ScoringManager::WriteVoxelRoiMass(OutputManager& output, int runId) const
{
    if (IsVoxelScoringRequested()) output.WriteVoxelRoiMass(runId, *geometryRegistry_);
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
    ConfigureNamedHistograms(config);
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
    hitVolumePathEnabled_ = config.GetBool("scoring", "hit_volume_path", false);
    EnableEventEdepOutput(config.GetBool("scoring", "event_edep", eventEdepOutputEnabled_));
    opticalPhotonCountsEnabled_ = config.GetBool("scoring", "optical_photon_counts", false);
    opticalBoundaryObservationsEnabled_ = config.GetBool("scoring", "optical_boundary_observations", false);
    activationObservationsEnabled_ = config.GetBool("scoring", "activation_observations", false);
    activationObservationSchemaVersion_ = config.GetInt("scoring", "activation_observation_schema_version", 1);
    if (activationObservationSchemaVersion_ < 1 || activationObservationSchemaVersion_ > 3)
        throw std::runtime_error("[scoring]/activation_observation_schema_version must be 1, 2 or 3");
    if (activationObservationSchemaVersion_ > 1 && !activationObservationsEnabled_)
        throw std::runtime_error("[scoring]/activation_observation_schema_version requires activation_observations = true");
    clockLibraryHash_ = config.GetString("scoring", "native_at_rest_engineering_library_sha256", "");
    if (!clockLibraryHash_.empty()) {
#ifndef G4USIM_WITH_NATIVE_AT_REST_OBSERVER
        throw std::runtime_error("native AtRest engineering feature absent from this build");
#else
        if (!activationObservationsEnabled_ || activationObservationSchemaVersion_ != 3 ||
            clockLibraryHash_.size() != 64 ||
            clockLibraryHash_.find_first_not_of("0123456789abcdef") != std::string::npos)
            throw std::runtime_error("native AtRest engineering requires activation V3 and a lowercase SHA-256");
#endif
    }
    if (activationObservationsEnabled_ && !enabled_)
        throw std::runtime_error("[scoring]/activation_observations requires [scoring]/enabled = true");
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
    namedPlacementPaths_.clear();
    filterSpecs_.clear();
    spectrumSpecs_.clear();
    const std::set<std::string> filterScorers{"dose", "fluence", "let", "displacement"};
    const std::set<std::string> spectrumScorers{"dose", "fluence", "displacement"};
    const std::set<std::string> filterKeys{"particles", "energy_min", "energy_max"};
    const std::set<std::string> spectrumKeys{"bins", "min", "max"};
    std::vector<std::string> spectrumSections;
    for (const auto& duplicate : config.GetMainReader().GetDuplicates()) {
        if (duplicate.section.rfind(kSelectionPrefix, 0) == 0 ||
            (duplicate.section == "scoring.filter.dose" && duplicate.key == "selection")) {
            throw std::runtime_error("Repeated placement selection declaration at line " +
                                     std::to_string(duplicate.lineNumber));
        }
    }
    for (const auto& info : config.GetSectionInfo()) {
        if (info.section.rfind(kSelectionPrefix, 0) != 0) continue;
        const auto name = info.section.substr(kSelectionPrefix.size());
        RejectUnknownVolumeKeys(config, info, {"physical_path"});
        const auto path = config.GetString(info.section, "physical_path", "");
        if (name.empty() || name.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_-") != std::string::npos ||
            path.empty() || path.front() != '/' || path.back() == '/' || path.find("//") != std::string::npos) {
            throw std::runtime_error(VolumeSectionLocation(config, info) +
                                     " requires a named selection with an absolute physical_path");
        }
        namedPlacementPaths_.emplace(name, path);
    }

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
            auto allowedKeys = filterKeys;
            if (scorer == "dose") allowedKeys.insert("selection");
            RejectUnknownVolumeKeys(config, info, allowedKeys);
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
            if (config.HasKey(info.section, "selection")) {
                cfg.selection = StringUtils::ToLower(config.GetString(info.section, "selection"));
                const auto item = namedPlacementPaths_.find(cfg.selection);
                if (item == namedPlacementPaths_.end())
                    throw std::runtime_error(location + ": unknown placement selection '" + cfg.selection + "'");
                cfg.physicalPath = item->second;
            }
            if (!hasParticles && !hasMin && !hasMax && cfg.physicalPath.empty()) {
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
                             const std::string& location, bool phaseSpace) {
        if (particles.empty()) return; // existing all semantics
        auto* table = G4ParticleTable::GetParticleTable();
        for (const auto& token : particles) {
            if (table->entries() == 0)
                throw std::runtime_error("[" + section + "]/particles at " + location +
                    " cannot validate token '" + token + "': Geant4 particle table is not ready");
            if (!table->FindParticle(token) && !(phaseSpace && IsKnownPhaseSpaceGroundStateIon(token)))
                throw std::runtime_error("[" + section + "]/particles at " + location +
                    " lists unknown Geant4 particle '" + token + "'");
        }
    };
    validate(letParticles_, "scoring.let", letParticleLocation_, false);
    validate(phaseSpaceParticles_, "phase_space", phaseParticleLocation_, true);
}

void ScoringManager::ValidateVolumeConfigsForRun()
{
    ValidateLegacyParticleSelectors();
    if (!HasVolumeConfig()) return;
    for (const auto& item : namedPlacementPaths_) ValidateOrdinaryPlacement(item.first, item.second);
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
        if (!spec.config.physicalPath.empty()) {
            observed["selection"] = spec.config.selection;
            observed["physical_path"] = spec.config.physicalPath;
        }
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
