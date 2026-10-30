#include "Config/EffectiveRuntime.hh"
#include "Config/ConfigSchemaTable.hh"
#include "Source/SourceManager.hh"

#include "Config/ConfigManager.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4Event.hh"
#include "G4GeneralParticleSource.hh"
#include "G4GeneralParticleSourceData.hh"
#include "G4PrimaryParticle.hh"
#include "G4PrimaryVertex.hh"
#include "G4IonTable.hh"
#include "G4ParticleDefinition.hh"
#include "G4ParticleTable.hh"
#include "G4PhysicalVolumeStore.hh"
#include "G4SingleParticleSource.hh"
#include "G4SPSAngDistribution.hh"
#include "G4SPSEneDistribution.hh"
#include "G4SPSPosDistribution.hh"
#include "G4ThreeVector.hh"
#include "G4SystemOfUnits.hh"
#include "G4ios.hh"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

std::vector<std::string> SplitWhitespace(const std::string& text)
{
    std::vector<std::string> tokens;
    std::string current;
    for (char ch : text) {
        if (std::isspace(static_cast<unsigned char>(ch))) {
            if (!current.empty()) {
                tokens.push_back(current);
                current.clear();
            }
        } else {
            current.push_back(ch);
        }
    }
    if (!current.empty()) tokens.push_back(current);
    return tokens;
}

std::vector<double> ParseLengthVec3(const std::string& text)
{
    const auto trimmed = StringUtils::Trim(text);
    if (StringUtils::Contains(trimmed, ",")) {
        const auto values = UnitParser::ParseVectorWithUnit(trimmed);
        if (values.size() != 3) throw std::runtime_error("expected 3 length values: '" + text + "'");
        return values;
    }

    const auto tokens = SplitWhitespace(trimmed);
    if (tokens.size() == 3) {
        return {
            UnitParser::ParseLength(tokens[0]),
            UnitParser::ParseLength(tokens[1]),
            UnitParser::ParseLength(tokens[2])
        };
    }
    if (tokens.size() == 4) {
        return {
            UnitParser::ParseLength(tokens[0] + " " + tokens[3]),
            UnitParser::ParseLength(tokens[1] + " " + tokens[3]),
            UnitParser::ParseLength(tokens[2] + " " + tokens[3])
        };
    }
    if (tokens.size() == 6) {
        return {
            UnitParser::ParseLength(tokens[0] + " " + tokens[1]),
            UnitParser::ParseLength(tokens[2] + " " + tokens[3]),
            UnitParser::ParseLength(tokens[4] + " " + tokens[5])
        };
    }

    throw std::runtime_error("expected vector as 'x,y,z', 'x y z unit', or 'x unit y unit z unit': '" + text + "'");
}

std::vector<double> ParseDoubleVec3(const std::string& text)
{
    const auto values = StringUtils::Contains(text, ",")
        ? UnitParser::ParseVectorDouble(text)
        : UnitParser::ParseVectorDouble(text, ' ');
    if (values.size() != 3) throw std::runtime_error("expected 3 direction values: '" + text + "'");
    return values;
}

std::vector<double> ReadVector3WithUnit(const ConfigManager& config, const std::string& section, const std::string& key)
{
    try {
        return ParseLengthVec3(config.GetString(section, key));
    } catch (const std::exception& error) {
        throw std::runtime_error("SourceManager expected 3 values for [" + section + "]/" + key + ": " + error.what());
    }
}

std::vector<double> ReadVector3Double(const ConfigManager& config, const std::string& section, const std::string& key)
{
    try {
        return ParseDoubleVec3(config.GetString(section, key));
    } catch (const std::exception& error) {
        throw std::runtime_error("SourceManager expected 3 direction values for [" + section + "]/" + key + ": " + error.what());
    }
}

std::vector<double> UnitVector(const std::vector<double>& v, const std::string& what)
{
    if (v.size() != 3) throw std::runtime_error("SourceManager " + what + " needs 3 components");
    const double magnitude = std::hypot(v[0], v[1], v[2]);
    if (!std::isfinite(magnitude) || magnitude <= 0.0) {
        throw std::runtime_error("SourceManager " + what + " must be a finite non-zero vector");
    }
    return {v[0] / magnitude, v[1] / magnitude, v[2] / magnitude};
}

double PositiveLength(const ConfigManager& config, const std::string& section, const std::string& key)
{
    const double value = UnitParser::ParseLength(config.GetString(section, key));
    if (!std::isfinite(value) || value <= 0.0) {
        throw std::runtime_error("SourceManager [" + section + "]/" + key + " must be a finite positive length");
    }
    return value;
}

double PositiveEnergy(const ConfigManager& config, const std::string& section, const std::string& key)
{
    const double value = UnitParser::ParseEnergy(config.GetString(section, key));
    if (!std::isfinite(value) || value <= 0.0) {
        throw std::runtime_error("SourceManager [" + section + "]/" + key + " must be a finite positive energy");
    }
    return value;
}

std::string Lower(const std::string& text)
{
    return StringUtils::ToLower(StringUtils::Trim(text));
}

// Keys accepted in [source] and [source.<name>]; unknown keys in a named
// source section are errors (the legacy [source] keeps the warning-only check).
const std::set<std::string>& SourceKeys()
{
    static const auto names = ConfigSchema::Keys("main_ini", "source.<name>");
    static const std::set<std::string> keys(names.begin(), names.end());
    // phase_space_file / phase_space_recycle are only valid in [source].
    return keys;
}

std::string ResolveRelativeToConfig(const ConfigManager& config, const std::string& path)
{
    std::filesystem::path file = std::filesystem::u8path(path);
    if (file.is_relative()) {
        const std::string main = config.GetMainConfigPath();
        if (!main.empty()) file = std::filesystem::u8path(main).parent_path() / file;
    }
    return file.u8string();
}

// Spectrum file: CSV with a header. histogram: e_low_<unit>,e_high_<unit>,weight
// (contiguous bins, weights per bin); points: energy_<unit>,density (linear
// interpolation between points). <unit> is keV or MeV; '#' starts a comment.
std::vector<std::pair<double, double>> ReadSpectrumFile(const std::string& path, const std::string& type, std::string& sha256)
{
    const auto acceptedInput = input_provenance::ReadFile(path, "spectrum", "source_spectrum_parse");
    std::istringstream input(acceptedInput.bytes);
    std::vector<std::vector<std::string>> rows;
    std::string line;
    std::vector<std::string> header;
    int lineNumber = 0;
    while (std::getline(input, line)) {
        ++lineNumber;
        const auto hash = line.find('#');
        if (hash != std::string::npos) line = line.substr(0, hash);
        line = StringUtils::Trim(line);
        if (line.empty()) continue;
        std::vector<std::string> cells;
        for (const auto& cell : StringUtils::Split(line, ',')) cells.push_back(StringUtils::Trim(cell));
        if (header.empty()) {
            header = cells;
            continue;
        }
        if (cells.size() != header.size()) {
            throw std::runtime_error("SourceManager spectrum_file '" + path + "' line " + std::to_string(lineNumber) +
                                     ": expected " + std::to_string(header.size()) + " columns");
        }
        rows.push_back(cells);
    }
    auto unitOf = [&](const std::string& column, const std::string& prefix) {
        const std::string name = Lower(column);
        if (name == prefix + "_mev") return MeV;
        if (name == prefix + "_kev") return keV;
        throw std::runtime_error("SourceManager spectrum_file '" + path + "': column '" + column + "' must be " +
                                 prefix + "_MeV or " + prefix + "_keV");
    };
    auto number = [&](const std::string& text) {
        const double value = UnitParser::ParseDouble(text);
        if (!std::isfinite(value)) throw std::runtime_error("SourceManager spectrum_file '" + path + "' has a nonfinite value");
        return value;
    };
    std::vector<std::pair<double, double>> points;
    double total = 0.0;
    if (type == "histogram") {
        if (header.size() != 3 || Lower(header[2]) != "weight") {
            throw std::runtime_error("SourceManager histogram spectrum_file '" + path +
                                     "' needs header e_low_MeV,e_high_MeV,weight (or _keV)");
        }
        const double lowUnit = unitOf(header[0], "e_low");
        const double highUnit = unitOf(header[1], "e_high");
        for (const auto& row : rows) {
            const double low = number(row[0]) * lowUnit;
            const double high = number(row[1]) * highUnit;
            const double weight = number(row[2]);
            if (!(high > low) || low < 0.0 || weight < 0.0) {
                throw std::runtime_error("SourceManager histogram spectrum_file '" + path +
                                         "' needs 0 <= e_low < e_high and weight >= 0 in every row");
            }
            if (points.empty()) {
                points.emplace_back(low, 0.0);
            } else if (std::abs(points.back().first - low) > 1e-9 * std::max(1.0, std::abs(low))) {
                throw std::runtime_error("SourceManager histogram spectrum_file '" + path +
                                         "' bins must be contiguous and increasing (e_low = previous e_high)");
            }
            points.emplace_back(high, weight);
            total += weight;
        }
    } else {
        if (header.size() != 2 || Lower(header[1]) != "density") {
            throw std::runtime_error("SourceManager points spectrum_file '" + path +
                                     "' needs header energy_MeV,density (or _keV)");
        }
        const double unit = unitOf(header[0], "energy");
        for (const auto& row : rows) {
            const double energy = number(row[0]) * unit;
            const double density = number(row[1]);
            if (energy < 0.0 || density < 0.0 || (!points.empty() && !(energy > points.back().first))) {
                throw std::runtime_error("SourceManager points spectrum_file '" + path +
                                         "' needs strictly increasing energies >= 0 and density >= 0");
            }
            points.emplace_back(energy, density);
            total += density;
        }
        if (points.size() < 2) {
            throw std::runtime_error("SourceManager points spectrum_file '" + path + "' needs at least 2 points");
        }
    }
    if (points.size() < 2 || !(total > 0.0)) {
        throw std::runtime_error("SourceManager spectrum_file '" + path + "' needs at least one bin and a positive total weight");
    }
    sha256 = acceptedInput.sha256;
    return points;
}

std::string Number(double value)
{
    std::ostringstream out;
    out << value;
    return out.str();
}

}  // namespace

std::string SourceManager::SourceSpec::Describe() const
{
    std::ostringstream out;
    out << "name=" << (name.empty() ? "source" : name) << " intensity=" << intensity;
    if (ion) {
        out << " particle=ion(Z=" << ionZ << ",A=" << ionA << ",Q=" << ionCharge
            << ",E*=" << ionExcitation / keV << "keV)";
    } else {
        out << " particle=" << (particleName.empty() ? "<gps-default>" : particleName);
    }
    out << " energy=" << energyType;
    if (energyType == "mono") out << "(" << monoEnergy / MeV << "MeV)";
    else if (energyType == "gauss") out << "(" << monoEnergy / MeV << "MeV,sigma=" << energySigma / MeV << "MeV)";
    else if (energyType == "histogram" || energyType == "points") out << "(" << spectrum.size() << " points)";
    else out << "(" << energyMin / MeV << "-" << energyMax / MeV << "MeV)";
    out << " position=" << (hasPosition ? positionType + (positionShape.empty() ? "" : "/" + positionShape) : "<gps-default>");
    if (!confineVolume.empty()) out << " confine=" << confineVolume;
    const std::string ang = angular.empty() ? (isotropic ? "isotropic" : (hasDirection ? "fixed" : "<gps-default>"))
                                            : angular;
    out << " angular=" << ang;
    return out.str();
}

SourceManager::SourceManager()
{
}

SourceManager::~SourceManager() = default;

SourceManager::SourceSpec& SourceManager::Current()
{
    return sources_[current_];
}

const SourceManager::SourceSpec& SourceManager::Current() const
{
    return sources_[current_];
}

void SourceManager::RequireSingleSourceForCommand(const char* what) const
{
    if (!loadingNamedSources_ && sources_.size() > 1) {
        throw std::runtime_error(std::string("SourceManager ") + what +
                                 " cannot target one of several [source.<name>] sources; edit the sources in the "
                                 "main INI or use native /gps/source/... commands.");
    }
}

G4GeneralParticleSource* SourceManager::GetGPS()
{
    EnsureGPS();
    ApplyCurrentConfigurationToGPS();
    return gps_.get();
}

const G4GeneralParticleSource* SourceManager::GetGPS() const
{
    EnsureGPS();
    ApplyCurrentConfigurationToGPS();
    return gps_.get();
}

bool SourceManager::HasGPS() const
{
    return gps_ != nullptr;
}

void SourceManager::InitializeAfterPhysicsListRegistered()
{
    GetGPS();
}

void SourceManager::PrepareForRun(long long plannedEvents)
{
    if (phaseSpace_) {
        if (!phaseSpaceRecycle_ && plannedEvents > static_cast<long long>(phaseSpace_->size())) {
            throw std::runtime_error("SourceManager phase-space source has " + std::to_string(phaseSpace_->size()) +
                                     " histories but the run requests " + std::to_string(plannedEvents) +
                                     " events; use beamOn <= " + std::to_string(phaseSpace_->size()) +
                                     " or set [source]/phase_space_recycle = true.");
        }
        // Resolve every particle once on the master; workers only read the map.
        for (const auto& history : *phaseSpace_) {
            for (const PhaseSpaceParticle& p : history) {
                if (phaseSpaceDefinitions_.count(p.pdg)) continue;
                G4ParticleDefinition* definition = G4ParticleTable::GetParticleTable()->FindParticle(p.pdg);
                if (!definition && p.pdg > 1000000000) definition = G4IonTable::GetIonTable()->GetIon(p.pdg);
                if (!definition) {
                    throw std::runtime_error("SourceManager phase-space particle '" + p.particle + "' (pdg " +
                                             std::to_string(p.pdg) + ") is unknown to the physics list");
                }
                phaseSpaceDefinitions_[p.pdg] = definition;
            }
        }
        effective_->Record(effective_config::Receipt(effective_config::FieldPath("source","phase_space_histories"),
            static_cast<std::int64_t>(phaseSpace_->size()), "source_prepare", "SourceManager::PrepareForRun particle table resolution"));
        return;
    }
    GetGPS();
    const auto observePrepared = [&]() {
        ObserveEffectiveRunSource("source_prepare");
    };
    if (deferredApplied_) { observePrepared(); return; } // preserve native changes between runs
    // Volume confinement and ions need the built geometry / ion table; GPS
    // silently drops an unknown confinement volume, so check it here.
    auto* data = G4GeneralParticleSourceData::Instance();
    for (G4int index = 0; index < data->GetSourceVectorSize(); ++index) {
        auto* source = data->GetCurrentSource(index);
        const auto pending = deferredSources_.find(source);
        if (pending == deferredSources_.end()) continue;  // native source, no INI replay
        const auto& overrides = pending->second;
        const SourceSpec& spec = sources_.at(overrides.index);
        if (!overrides.confineOverridden && !spec.confineVolume.empty() &&
            !G4PhysicalVolumeStore::GetInstance()->GetVolume(spec.confineVolume, false)) {
            throw std::runtime_error("SourceManager confine volume '" + spec.confineVolume +
                                     "' is not a physical volume of the built geometry; use a physical volume name "
                                     "(see /AIHL/geometry/listUserVolumes, usually <name>_PV).");
        }
        if (spec.ion && !overrides.particleOverridden) {
            ApplyParticle(spec, *source);
        }
        if (!overrides.confineOverridden && !spec.confineVolume.empty())
            source->GetPosDist()->ConfineSourceToVolume(spec.confineVolume);
        ObserveGPS(overrides.index, *source, "source_prepare");
    }
    deferredSources_.clear();
    deferredApplied_ = true;
    observePrepared();
}

bool SourceManager::HasPendingDeferredConfiguration() const
{
    if (deferredApplied_) return false;
    for (const auto& item : deferredSources_) {
        const auto& pending = item.second;
        const auto& spec = sources_.at(pending.index);
        if ((spec.ion && !pending.particleOverridden) ||
            (!spec.confineVolume.empty() && !pending.confineOverridden)) return true;
    }
    return false;
}

void SourceManager::BeforeNativeGPSCommand(const std::string& command)
{
    if (!HasPendingDeferredConfiguration()) return;
    std::istringstream input(command);
    std::string name;
    input >> name;
    if (command.find('{') != std::string::npos || command.find('}') != std::string::npos ||
        name == "/control/alias" || name == "/control/if" || name == "/control/doif" ||
        name == "/control/strif" || name == "/control/strdoif") {
        throw std::runtime_error("Alias references/dynamic UI dispatch with pending ion/confinement configuration "
                                 "cannot be audited; use literal direct GPS commands or a batch macro without aliases");
    }
    if (name == "/control/execute" || name == "/control/loop" || name == "/control/foreach") {
        throw std::runtime_error("Nested/dynamic UI commands with pending ion/confinement configuration are unsupported; "
                                 "use a batch --macro (static execute is expanded) or initialize and run first");
    }
    if (name.rfind("/gps/", 0) != 0) return;
    if (name == "/gps/source/clear") {
        deferredSources_.clear();
        return;
    }
    if (name == "/gps/source/delete") {
        G4int index = -1;
        input >> index;
        auto* data = G4GeneralParticleSourceData::Instance();
        if (index >= 0 && index < data->GetSourceVectorSize())
            deferredSources_.erase(data->GetCurrentSource(index));
        return;
    }
    const auto found = deferredSources_.find(gps_->GetCurrentSource());
    if (found == deferredSources_.end()) return;
    if (name == "/gps/particle" || name == "/gps/ion" || name == "/gps/ionLvl") {
        found->second.particleOverridden = true;
    } else if (name == "/gps/pos/confine") {
        found->second.confineOverridden = true;
    }
}

void SourceManager::ResetGPS()
{
    deferredSources_.clear();
    configuredGPSSources_.clear();
    nativeGPSIdentityUncertain_ = false;
    phaseSpaceInputs_.clear();
    gps_.reset();
    phaseSpaceFiles_.clear();
    phaseSpace_.reset();
    phaseSpaceParticleCount_ = 0;
    phaseSpaceRecycle_ = false;
    phaseSpaceDefinitions_.clear();
    sources_.assign(1, SourceSpec{});
    current_ = 0;
    presetName_.clear();
    MarkGPSConfigDirty();
    configured_ = false;
}

void SourceManager::LoadFromConfig(const ConfigManager& config)
{
    LoadFromConfigImpl(config);
    effective_->reader = config.GetMainReader();
    effective_->Accept(config.GetMainReader(),ProjectEffectiveConfigFields());
}

void SourceManager::LoadFromConfigImpl(const ConfigManager& config)
{
    std::vector<std::string> named;
    for (const std::string& section : config.GetSections()) {
        if (section.rfind("source.", 0) == 0) named.push_back(section);
    }
    const bool hasLegacy = config.HasSection("source");
    if (!named.empty()) {
        if (hasLegacy) {
            for (const std::string& key : config.GetKeys("source")) {
                if (Lower(key) != "verbose") {
                    throw std::runtime_error(
                        "SourceManager [source]/" + key + " cannot be combined with [source.<name>] sections; "
                        "move it into a named source (only [source]/verbose is global).");
                }
            }
            if (config.HasKey("source", "verbose")) SetVerboseLevel(config.GetInt("source", "verbose", verboseLevel_));
        }
        sources_.clear();
        loadingNamedSources_ = true;
        try {
            for (const std::string& section : named) {
                const std::string name = section.substr(std::string("source.").size());
                if (name.empty() || name.find('.') != std::string::npos) {
                    throw std::runtime_error("SourceManager section [" + section +
                                             "] must be [source.<name>] with a non-empty name without dots");
                }
                for (const std::string& key : config.GetKeys(section)) {
                    if (!SourceKeys().count(Lower(key)) || Lower(key) == "verbose") {
                        throw std::runtime_error("SourceManager unknown key [" + section + "]/" + key);
                    }
                }
                sources_.emplace_back();
                current_ = sources_.size() - 1;
                Current().name = name;
                for (const auto& info : config.GetSectionInfo()) if (info.section == section && !info.originalSection.empty())
                    Current().name = StringUtils::Trim(info.originalSection).substr(std::string("source.").size());
                LoadSection(config, section, true);
            }
        } catch (...) {
            loadingNamedSources_ = false;
            throw;
        }
        loadingNamedSources_ = false;
        current_ = 0;
        MarkGPSConfigDirty();
        configured_ = true;
        return;
    }
    if (!hasLegacy) return;
    if (config.HasKey("source", "phase_space_file")) {
        for (const std::string& key : config.GetKeys("source")) {
            const std::string name = Lower(key);
            if (name != "phase_space_file" && name != "phase_space_recycle" && name != "verbose") {
                throw std::runtime_error("SourceManager [source]/" + key + " cannot be combined with phase_space_file; "
                                         "the phase-space file defines particle, energy, position and direction.");
            }
        }
        if (config.HasKey("source", "verbose")) SetVerboseLevel(config.GetInt("source", "verbose", verboseLevel_));
        phaseSpaceFiles_.clear();
        for (const std::string& part : StringUtils::Split(config.GetString("source", "phase_space_file"), ',')) {
            const std::string file = StringUtils::Trim(part);
            if (!file.empty()) phaseSpaceFiles_.push_back(ResolveRelativeToConfig(config, file));
        }
        phaseSpaceRecycle_ = config.GetBool("source", "phase_space_recycle", false);
        auto histories = std::make_shared<std::vector<std::vector<PhaseSpaceParticle>>>(
            PhaseSpace::ReadHistories(phaseSpaceFiles_, &phaseSpaceInputs_));
        phaseSpaceParticleCount_ = 0;
        for (const auto& history : *histories) phaseSpaceParticleCount_ += history.size();
        phaseSpace_ = std::move(histories);
        phaseSpaceDefinitions_.clear();
        sources_.assign(1, SourceSpec{});  // GPS stays at its defaults and is not used
        configured_ = true;
        return;
    }
    if (config.HasKey("source", "phase_space_recycle")) {
        throw std::runtime_error("SourceManager [source]/phase_space_recycle requires phase_space_file");
    }
    LoadSection(config, "source", false);
}

bool SourceManager::UsesPhaseSpace() const
{
    return phaseSpace_ != nullptr;
}

void SourceManager::GeneratePhaseSpaceEvent(G4Event* event) const
{
    const auto histories = phaseSpace_;
    if (!histories || !event) throw std::runtime_error("SourceManager::GeneratePhaseSpaceEvent without phase-space source");
    const std::size_t index = static_cast<std::size_t>(event->GetEventID()) % histories->size();
    for (const PhaseSpaceParticle& p : (*histories)[index]) {
        const auto found = phaseSpaceDefinitions_.find(p.pdg);
        if (found == phaseSpaceDefinitions_.end()) {
            throw std::runtime_error("SourceManager phase-space particle pdg " + std::to_string(p.pdg) +
                                     " was not prepared for this run");
        }
        auto* vertex = new G4PrimaryVertex(G4ThreeVector(p.x, p.y, p.z), p.time);
        auto* primary = new G4PrimaryParticle(found->second);
        primary->SetKineticEnergy(p.kineticEnergy);
        primary->SetMomentumDirection(G4ThreeVector(p.u, p.v, p.w).unit());
        primary->SetWeight(p.weight);
        vertex->SetPrimary(primary);
        event->AddPrimaryVertex(vertex);
    }
}

std::size_t SourceManager::GetPhaseSpaceHistoryCount() const
{
    return phaseSpace_ ? phaseSpace_->size() : 0;
}

std::size_t SourceManager::GetPhaseSpaceParticleCount() const
{
    return phaseSpaceParticleCount_;
}

const std::vector<std::string>& SourceManager::GetPhaseSpaceFiles() const
{
    return phaseSpaceFiles_;
}

bool SourceManager::IsPhaseSpaceRecycled() const
{
    return phaseSpaceRecycle_;
}

void SourceManager::LoadSection(const ConfigManager& config, const std::string& section, bool namedSource)
{
    if (config.HasKey(section, "preset")) {
        const std::string preset = StringUtils::Trim(config.GetString(section, "preset", ""));
        if (preset.empty()) {
            throw std::runtime_error("SourceManager [" + section + "]/preset must not be empty; "
                                     "remove the key or choose a supported preset.");
        }
        ApplyPreset(preset);
    }
    const bool ionParticle = config.HasKey(section, "particle") &&
                             Lower(config.GetString(section, "particle", "")) == "ion";
    if (config.HasKey(section, "particle")) {
        const std::string particle = StringUtils::Trim(config.GetString(section, "particle", ""));
        if (particle.empty()) {
            throw std::runtime_error("SourceManager [" + section + "]/particle must not be empty; "
                                     "remove the key or specify a particle.");
        }
        if (!ionParticle) SetParticle(particle);
    }
    if (config.HasKey(section, "energy")) {
        const std::string energy = StringUtils::Trim(config.GetString(section, "energy", ""));
        if (energy.empty()) {
            throw std::runtime_error("SourceManager [" + section + "]/energy must not be empty; "
                                     "remove the key or specify a positive energy with units.");
        }
        const double value = UnitParser::ParseEnergy(energy);
        if (ionParticle && value == 0.0) {
            Current().monoEnergy = 0.0;
            Current().restEnergy = true;
            MarkGPSConfigDirty();
        } else {
            SetMonoEnergy(value);
        }
    }
    if (!namedSource && config.HasKey(section, "verbose")) {
        SetVerboseLevel(config.GetInt(section, "verbose", verboseLevel_));
    }

    const bool isotropic = config.GetBool(section, "isotropic", false);
    const bool hasAngular = config.HasKey(section, "angular");
    // These combinations previously completed initialization while silently
    // discarding an explicitly supplied source field.
    if (isotropic && config.HasKey(section, "direction")) {
        throw std::runtime_error(
            "SourceManager [" + section + "]/isotropic=true conflicts with [" + section + "]/direction; "
            "remove direction for isotropic emission or set isotropic=false.");
    }
    if (hasAngular && config.HasKey(section, "isotropic")) {
        throw std::runtime_error("SourceManager [" + section + "]/angular conflicts with isotropic; "
                                 "use angular = isotropic instead.");
    }
    if (config.HasKey(section, "position_type")) {
        const std::string type = Lower(config.GetString(section, "position_type", ""));
        if (type == "point") {
            if (config.HasKey(section, "center") || config.HasKey(section, "radius") ||
                config.HasKey(section, "shape") || config.HasKey(section, "halfx") ||
                config.HasKey(section, "halfy") || config.HasKey(section, "inner_radius")) {
                throw std::runtime_error(
                    "SourceManager [" + section + "]/position_type=point conflicts with plane-only fields; "
                    "remove plane-only fields or use position_type=plane.");
            }
            if (!config.HasKey(section, "position") ||
                StringUtils::Trim(config.GetString(section, "position", "")).empty()) {
                throw std::runtime_error(
                    "SourceManager [" + section + "]/position_type=point requires a non-empty "
                    "[" + section + "]/position; supply x,y,z with length units.");
            }
            const auto pos = ReadVector3WithUnit(config, section, "position");
            SetPointPosition(pos[0], pos[1], pos[2]);
        } else if (type == "plane") {
            if (config.HasKey(section, "position")) {
                throw std::runtime_error(
                    "SourceManager [" + section + "]/position_type=plane conflicts with position; "
                    "use center for the plane origin instead.");
            }
            const std::string shape = Lower(config.GetString(section, "shape", "circle"));
            std::vector<double> center{0.0, 0.0, -1.0 * CLHEP::mm};
            if (config.HasKey(section, "center")) {
                center = ReadVector3WithUnit(config, section, "center");
            }
            const std::string direction = config.GetString(section, "direction", "+z");
            if (shape == "circle") {
                if (config.HasKey(section, "halfx") || config.HasKey(section, "halfy") ||
                    config.HasKey(section, "inner_radius")) {
                    throw std::runtime_error("SourceManager plane circle conflicts with halfx/halfy/inner_radius; remove unused shape fields.");
                }
                const double radius = config.HasKey(section, "radius")
                    ? UnitParser::ParseLength(config.GetString(section, "radius"))
                    : 1.0 * CLHEP::mm;
                SetPlaneBeamAt(radius, center[0], center[1], center[2], direction);
            } else if (shape == "rectangle") {
                if (config.HasKey(section, "radius") || config.HasKey(section, "inner_radius")) {
                    throw std::runtime_error("SourceManager plane rectangle conflicts with radius/inner_radius; use halfx and halfy.");
                }
                if (!config.HasKey(section, "halfx") || !config.HasKey(section, "halfy")) {
                    throw std::runtime_error("SourceManager plane rectangle requires halfx and halfy with length units.");
                }
                const double halfX = UnitParser::ParseLength(config.GetString(section, "halfx"));
                const double halfY = UnitParser::ParseLength(config.GetString(section, "halfy"));
                SetPlaneRectangleAt(halfX, halfY, center[0], center[1], center[2], direction);
            } else if (shape == "annulus" || shape == "ellipse" || shape == "square") {
                SourceSpec& spec = Current();
                spec.advanced = true;
                std::vector<double> params = center;
                if (shape == "annulus") {
                    if (config.HasKey(section, "halfx") || config.HasKey(section, "halfy")) {
                        throw std::runtime_error("SourceManager plane annulus uses radius and inner_radius, not halfx/halfy.");
                    }
                    spec.radius = PositiveLength(config, section, "radius");
                    spec.innerRadius = PositiveLength(config, section, "inner_radius");
                    if (!(spec.innerRadius < spec.radius)) {
                        throw std::runtime_error("SourceManager plane annulus requires inner_radius < radius.");
                    }
                    params.push_back(spec.radius);
                    SetPosition("Plane", "Annulus", params);
                } else {
                    if (config.HasKey(section, "radius") || config.HasKey(section, "inner_radius")) {
                        throw std::runtime_error("SourceManager plane " + shape + " uses halfx/halfy, not radius.");
                    }
                    spec.halfX = PositiveLength(config, section, "halfx");
                    if (shape == "square") {
                        if (config.HasKey(section, "halfy")) {
                            throw std::runtime_error("SourceManager plane square uses halfx only.");
                        }
                        spec.halfY = spec.halfX;
                    } else {
                        spec.halfY = PositiveLength(config, section, "halfy");
                    }
                    params.push_back(spec.halfX);
                    params.push_back(spec.halfY);
                    SetPosition("Plane", shape == "square" ? "Square" : "Ellipse", params);
                }
                const auto d = ParseDirectionVector(NormalizeDirectionToken(direction));
                SetDirection(d[0], d[1], d[2]);
            } else {
                throw std::runtime_error("SourceManager unsupported [" + section + "]/shape='" + shape +
                    "'; supported plane shapes: circle, rectangle, annulus, ellipse or square.");
            }
        } else if (type == "volume" || type == "beam") {
            // Parsed by LoadAdvancedSection below, after the direction.
        } else {
            throw std::runtime_error(
                "SourceManager unsupported [" + section + "]/position_type='" + type +
                "'; supported values: point (requires position), plane (circle/rectangle/annulus/ellipse/square), "
                "volume (sphere/cylinder/box/ellipsoid) or beam (Gaussian spot).");
        }
    } else if (config.HasKey(section, "center") || config.HasKey(section, "radius") ||
               config.HasKey(section, "shape") || config.HasKey(section, "halfx") ||
               config.HasKey(section, "halfy") || config.HasKey(section, "inner_radius")) {
        throw std::runtime_error(
            "SourceManager [" + section + "]/plane shape fields require position_type=plane; "
            "legacy point positions must use position.");
    } else if (config.HasKey(section, "position")) {
        const auto pos = ReadVector3WithUnit(config, section, "position");
        SetPointPosition(pos[0], pos[1], pos[2]);
    }

    if (isotropic) {
        SetIsotropic();
    } else if (config.HasKey(section, "direction")) {
        const std::string direction = StringUtils::Trim(config.GetString(section, "direction"));
        if (direction == "+x" || direction == "-x" || direction == "+y" || direction == "-y" || direction == "+z" || direction == "-z") {
            const auto d = ParseDirectionVector(direction);
            SetDirection(d[0], d[1], d[2]);
        } else {
            const auto d = ReadVector3Double(config, section, "direction");
            SetDirection(d[0], d[1], d[2]);
        }
    } else if (config.HasKey(section, "isotropic") && Current().isotropic) {
        throw std::runtime_error(
            "SourceManager [" + section + "]/isotropic=false cannot disable an isotropic preset "
            "without [" + section + "]/direction; supply a non-zero direction vector "
            "or omit isotropic=false to use the preset.");
    }

    LoadAdvancedSection(config, section, Current());

    if (namedSource) {
        SourceSpec& spec = Current();
        if (!spec.ion && spec.particleName.empty()) {
            throw std::runtime_error("SourceManager [" + section + "] requires particle (or preset).");
        }
        if (spec.energyType == "mono" && !(spec.monoEnergy > 0.0) && !spec.restEnergy) {
            throw std::runtime_error("SourceManager [" + section + "] requires energy or energy_type.");
        }
        if (!spec.hasPosition) {
            throw std::runtime_error("SourceManager [" + section + "] requires position (or position_type).");
        }
        if (!spec.isotropic && !spec.hasDirection && spec.angular.empty()) {
            throw std::runtime_error("SourceManager [" + section + "] requires direction, isotropic or angular.");
        }
    }
    configured_ = true;
}

void SourceManager::LoadAdvancedSection(const ConfigManager& config, const std::string& section, SourceSpec& spec)
{
    auto has = [&](const char* key) { return config.HasKey(section, key); };
    auto reject = [&](std::initializer_list<const char*> keys, const std::string& why) {
        for (const char* key : keys) {
            if (has(key)) throw std::runtime_error("SourceManager [" + section + "]/" + key + " " + why);
        }
    };

    // --- intensity ---------------------------------------------------------
    if (has("intensity")) {
        if (spec.name.empty()) {
            throw std::runtime_error("SourceManager [" + section + "]/intensity is only valid in [source.<name>] sections");
        }
        spec.intensity = UnitParser::ParseDouble(config.GetString(section, "intensity"));
        if (!std::isfinite(spec.intensity) || spec.intensity <= 0.0) {
            throw std::runtime_error("SourceManager [" + section + "]/intensity must be a finite positive number");
        }
    }

    // --- ion -----------------------------------------------------------------
    const bool ionParticle = has("particle") && Lower(config.GetString(section, "particle")) == "ion";
    if (ionParticle != has("ion")) {
        throw std::runtime_error("SourceManager [" + section + "]: particle = ion and ion = Z A [charge [excitation]] "
                                 "must be given together");
    }
    if (ionParticle) {
        const auto tokens = SplitWhitespace(config.GetString(section, "ion"));
        if (tokens.size() < 2 || tokens.size() > 4) {
            throw std::runtime_error("SourceManager [" + section + "]/ion must be 'Z A [charge [excitation energy]]'");
        }
        spec.ion = true;
        spec.advanced = true;
        spec.particleName = "ion";
        spec.ionZ = static_cast<int>(UnitParser::ParseDouble(tokens[0]));
        spec.ionA = static_cast<int>(UnitParser::ParseDouble(tokens[1]));
        if (std::to_string(spec.ionZ) != tokens[0] || std::to_string(spec.ionA) != tokens[1] ||
            spec.ionZ < 1 || spec.ionA < spec.ionZ || spec.ionA > 300) {
            throw std::runtime_error("SourceManager [" + section + "]/ion needs integers 1 <= Z <= A <= 300");
        }
        spec.ionCharge = tokens.size() >= 3 ? UnitParser::ParseDouble(tokens[2]) : spec.ionZ;
        spec.ionExcitation = tokens.size() == 4 ? UnitParser::ParseEnergy(tokens[3]) : 0.0;
        if (!std::isfinite(spec.ionCharge) || !std::isfinite(spec.ionExcitation) || spec.ionExcitation < 0.0) {
            throw std::runtime_error("SourceManager [" + section + "]/ion has an invalid charge or excitation energy");
        }
        if (!has("energy") && !has("energy_type")) {
            throw std::runtime_error("SourceManager [" + section + "] ion source requires energy (0 keV for decay at rest)");
        }
        MarkGPSConfigDirty();
    }

    // --- energy --------------------------------------------------------------
    if (has("energy_type")) {
        const std::string type = Lower(config.GetString(section, "energy_type"));
        spec.advanced = spec.advanced || type != "mono";
        if (type == "mono") {
            reject({"energy_sigma", "energy_min", "energy_max", "alpha", "ezero", "spectrum_file"},
                   "is not used by energy_type = mono");
            if (!has("energy")) throw std::runtime_error("SourceManager [" + section + "] energy_type = mono requires energy");
        } else if (type == "gauss") {
            reject({"energy_min", "energy_max", "alpha", "ezero", "spectrum_file"}, "is not used by energy_type = gauss");
            if (!has("energy") || !has("energy_sigma")) {
                throw std::runtime_error("SourceManager [" + section + "] energy_type = gauss requires energy (mean) and energy_sigma");
            }
            spec.energySigma = PositiveEnergy(config, section, "energy_sigma");
        } else if (type == "uniform" || type == "power" || type == "exp") {
            reject({"energy", "energy_sigma", "spectrum_file"}, "is not used by energy_type = " + type);
            if (!has("energy_min") || !has("energy_max")) {
                throw std::runtime_error("SourceManager [" + section + "] energy_type = " + type + " requires energy_min and energy_max");
            }
            spec.energyMin = UnitParser::ParseEnergy(config.GetString(section, "energy_min"));
            spec.energyMax = PositiveEnergy(config, section, "energy_max");
            if (!std::isfinite(spec.energyMin) || spec.energyMin < 0.0 || !(spec.energyMax > spec.energyMin)) {
                throw std::runtime_error("SourceManager [" + section + "] requires 0 <= energy_min < energy_max");
            }
            if (type == "uniform") reject({"alpha", "ezero"}, "is not used by energy_type = uniform");
            if (type == "power") {
                reject({"ezero"}, "is not used by energy_type = power");
                if (!has("alpha")) throw std::runtime_error("SourceManager [" + section + "] energy_type = power requires alpha (dN/dE ~ E^alpha)");
                spec.alpha = UnitParser::ParseDouble(config.GetString(section, "alpha"));
                if (!std::isfinite(spec.alpha)) throw std::runtime_error("SourceManager [" + section + "]/alpha must be finite");
                if (spec.energyMin <= 0.0) throw std::runtime_error("SourceManager [" + section + "] energy_type = power requires energy_min > 0");
            }
            if (type == "exp") {
                reject({"alpha"}, "is not used by energy_type = exp");
                if (!has("ezero")) throw std::runtime_error("SourceManager [" + section + "] energy_type = exp requires ezero (dN/dE ~ exp(-E/ezero))");
                spec.ezero = PositiveEnergy(config, section, "ezero");
            }
        } else if (type == "histogram" || type == "points") {
            reject({"energy", "energy_sigma", "energy_min", "energy_max", "alpha", "ezero"},
                   "is not used by energy_type = " + type + " (the spectrum comes from spectrum_file)");
            if (!has("spectrum_file")) {
                throw std::runtime_error("SourceManager [" + section + "] energy_type = " + type + " requires spectrum_file");
            }
            spec.spectrumFile = ResolveRelativeToConfig(config, StringUtils::Trim(config.GetString(section, "spectrum_file")));
            spec.spectrum = ReadSpectrumFile(spec.spectrumFile, type, spec.spectrumSha256);
        } else {
            throw std::runtime_error("SourceManager unsupported [" + section + "]/energy_type='" + type +
                                     "'; supported: mono, gauss, uniform, power, exp, histogram, points");
        }
        spec.energyType = type;
        MarkGPSConfigDirty();
    } else {
        reject({"energy_sigma", "energy_min", "energy_max", "alpha", "ezero", "spectrum_file"},
               "requires energy_type (gauss, uniform, power, exp, histogram or points)");
    }

    // --- volume / beam positions --------------------------------------------
    const std::string positionType = has("position_type") ? Lower(config.GetString(section, "position_type")) : "";
    if (positionType == "volume" || positionType == "beam") {
        spec.advanced = true;
        reject({"position"}, "is not used by position_type = " + positionType + "; use center");
        std::vector<double> params{0.0, 0.0, 0.0};
        if (has("center")) params = ReadVector3WithUnit(config, section, "center");
        const std::string shape = Lower(config.GetString(section, "shape", positionType == "beam" ? "circle" : ""));
        if (positionType == "volume") {
            reject({"beam_sigma", "beam_sigma_x", "beam_sigma_y"}, "is only used by position_type = beam");
            if (shape == "sphere") {
                reject({"halfx", "halfy", "halfz", "inner_radius"}, "is not used by a sphere (use radius)");
                spec.radius = PositiveLength(config, section, "radius");
                spec.positionShape = "Sphere";
            } else if (shape == "cylinder") {
                reject({"halfx", "halfy", "inner_radius"}, "is not used by a cylinder (use radius and halfz)");
                spec.radius = PositiveLength(config, section, "radius");
                spec.halfZ = PositiveLength(config, section, "halfz");
                spec.positionShape = "Cylinder";
            } else if (shape == "box" || shape == "ellipsoid") {
                reject({"radius", "inner_radius"}, "is not used by a " + shape + " (use halfx, halfy, halfz)");
                spec.halfX = PositiveLength(config, section, "halfx");
                spec.halfY = PositiveLength(config, section, "halfy");
                spec.halfZ = PositiveLength(config, section, "halfz");
                spec.positionShape = shape == "box" ? "Para" : "Ellipsoid";
            } else {
                throw std::runtime_error("SourceManager [" + section + "] position_type = volume requires shape = "
                                         "sphere, cylinder, box or ellipsoid");
            }
            spec.positionType = "Volume";
        } else {
            reject({"radius", "inner_radius", "halfx", "halfy", "halfz"}, "is not used by position_type = beam");
            if (shape == "circle") {
                reject({"beam_sigma_x", "beam_sigma_y"}, "is used by shape = ellipse");
                spec.beamSigmaR = PositiveLength(config, section, "beam_sigma");
                spec.positionShape = "Circle";
            } else if (shape == "ellipse") {
                reject({"beam_sigma"}, "is used by shape = circle");
                spec.beamSigmaX = PositiveLength(config, section, "beam_sigma_x");
                spec.beamSigmaY = PositiveLength(config, section, "beam_sigma_y");
                spec.positionShape = "Ellipse";
            } else {
                throw std::runtime_error("SourceManager [" + section + "] position_type = beam requires shape = circle or ellipse");
            }
            spec.positionType = "Beam";
        }
        spec.positionParams = params;
        spec.hasPosition = true;
        MarkGPSConfigDirty();
    } else {
        reject({"halfz", "beam_sigma", "beam_sigma_x", "beam_sigma_y"},
               "requires position_type = volume or beam");
    }

    if (has("rot1") || has("rot2")) {
        if (!has("rot1") || !has("rot2")) {
            throw std::runtime_error("SourceManager [" + section + "] rot1 and rot2 must be given together");
        }
        if (spec.positionType != "Plane" && spec.positionType != "Volume" && spec.positionType != "Beam") {
            throw std::runtime_error("SourceManager [" + section + "] rot1/rot2 require a plane, volume or beam position");
        }
        spec.rot1 = UnitVector(ReadVector3Double(config, section, "rot1"), "[" + section + "]/rot1");
        spec.rot2 = UnitVector(ReadVector3Double(config, section, "rot2"), "[" + section + "]/rot2");
        const double dot = spec.rot1[0] * spec.rot2[0] + spec.rot1[1] * spec.rot2[1] + spec.rot1[2] * spec.rot2[2];
        if (std::abs(dot) > 1.0 - 1e-9) {
            throw std::runtime_error("SourceManager [" + section + "] rot1 and rot2 must not be parallel");
        }
        spec.hasRotation = true;
        spec.advanced = true;
        MarkGPSConfigDirty();
    }
    if (has("confine")) {
        spec.confineVolume = StringUtils::Trim(config.GetString(section, "confine"));
        if (spec.confineVolume.empty()) throw std::runtime_error("SourceManager [" + section + "]/confine must name a physical volume");
        if (spec.positionType != "Volume") {
            throw std::runtime_error("SourceManager [" + section + "]/confine requires position_type = volume "
                                     "(the sampling shape must enclose the confining volume)");
        }
        spec.advanced = true;
    }

    // --- angular -------------------------------------------------------------
    if (has("angular")) {
        const std::string angular = Lower(config.GetString(section, "angular"));
        spec.advanced = spec.advanced || angular != "fixed";
        const bool thetaKeys = has("min_theta") || has("max_theta");
        if (angular == "fixed") {
            reject({"min_theta", "max_theta", "angular_sigma", "angular_sigma_x", "angular_sigma_y", "focus"},
                   "is not used by angular = fixed");
            if (!spec.hasDirection) throw std::runtime_error("SourceManager [" + section + "] angular = fixed requires direction");
        } else if (angular == "isotropic" || angular == "cos") {
            reject({"angular_sigma", "angular_sigma_x", "angular_sigma_y", "focus"},
                   "is not used by angular = " + angular);
            if (angular == "cos" && !spec.hasDirection) {
                throw std::runtime_error("SourceManager [" + section + "] angular = cos requires direction (the axis of the cosine law)");
            }
            if (thetaKeys && !spec.hasDirection) {
                throw std::runtime_error("SourceManager [" + section + "] min_theta/max_theta require direction (the cone axis)");
            }
            if (angular == "isotropic" && !thetaKeys && has("direction")) {
                throw std::runtime_error("SourceManager [" + section + "] angular = isotropic without min_theta/max_theta "
                                         "conflicts with direction; remove direction or give a cone with max_theta");
            }
            spec.minTheta = has("min_theta") ? UnitParser::ParseAngle(config.GetString(section, "min_theta")) : 0.0;
            spec.maxTheta = has("max_theta") ? UnitParser::ParseAngle(config.GetString(section, "max_theta"))
                                             : (angular == "cos" ? 90.0 * deg : 180.0 * deg);
            const double limit = angular == "cos" ? 90.0 * deg : 180.0 * deg;
            if (!(spec.minTheta >= 0.0) || !(spec.maxTheta > spec.minTheta) || spec.maxTheta > limit + 1e-12) {
                throw std::runtime_error("SourceManager [" + section + "] requires 0 <= min_theta < max_theta <= " +
                                         (angular == "cos" ? std::string("90 deg") : std::string("180 deg")));
            }
            spec.hasThetaRange = thetaKeys;
        } else if (angular == "beam1d" || angular == "beam2d") {
            reject({"min_theta", "max_theta", "focus"}, "is not used by angular = " + angular);
            if (!spec.hasDirection) throw std::runtime_error("SourceManager [" + section + "] angular = " + angular + " requires direction");
            if (angular == "beam1d") {
                reject({"angular_sigma_x", "angular_sigma_y"}, "is used by angular = beam2d");
                spec.angularSigma = UnitParser::ParseAngle(config.GetString(section, "angular_sigma"));
                if (!(spec.angularSigma > 0.0)) throw std::runtime_error("SourceManager [" + section + "]/angular_sigma must be > 0");
            } else {
                reject({"angular_sigma"}, "is used by angular = beam1d");
                spec.angularSigmaX = UnitParser::ParseAngle(config.GetString(section, "angular_sigma_x"));
                spec.angularSigmaY = UnitParser::ParseAngle(config.GetString(section, "angular_sigma_y"));
                if (!(spec.angularSigmaX > 0.0) || !(spec.angularSigmaY > 0.0)) {
                    throw std::runtime_error("SourceManager [" + section + "] angular_sigma_x/y must be > 0");
                }
            }
        } else if (angular == "focused") {
            reject({"min_theta", "max_theta", "angular_sigma", "angular_sigma_x", "angular_sigma_y", "direction"},
                   "is not used by angular = focused");
            if (!has("focus")) throw std::runtime_error("SourceManager [" + section + "] angular = focused requires focus = x,y,z");
            spec.focus = ReadVector3WithUnit(config, section, "focus");
        } else {
            throw std::runtime_error("SourceManager unsupported [" + section + "]/angular='" + angular +
                                     "'; supported: fixed, isotropic, cos, beam1d, beam2d, focused");
        }
        spec.angular = angular;
        spec.isotropic = false;
        if (angular == "focused") {
            spec.hasDirection = false;
            spec.direction.clear();
        }
        MarkGPSConfigDirty();
    } else {
        reject({"min_theta", "max_theta", "angular_sigma", "angular_sigma_x", "angular_sigma_y", "focus"},
               "requires angular (isotropic, cos, beam1d, beam2d or focused)");
    }
}

void SourceManager::ApplyPreset(const std::string& presetName)
{
    const std::string preset = StringUtils::ToLower(StringUtils::Trim(presetName));
    if (preset.empty()) throw std::runtime_error("SourceManager::ApplyPreset requires non-empty presetName");
    RequireSingleSourceForCommand("preset");

    if (preset == "mono_proton" || preset == "proton_beam") {
        SetParticle("proton");
        SetMonoEnergy(10.0 * CLHEP::MeV);
        SetPointPosition(0.0, 0.0, -1.0 * CLHEP::mm);
        SetDirection(0.0, 0.0, 1.0);
    } else if (preset == "neutron_beam") {
        SetParticle("neutron");
        SetMonoEnergy(1.0 * CLHEP::MeV);
        SetPointPosition(0.0, 0.0, -1.0 * CLHEP::mm);
        SetDirection(0.0, 0.0, 1.0);
    } else if (preset == "gamma_beam") {
        SetParticle("gamma");
        SetMonoEnergy(1.0 * CLHEP::MeV);
        SetPointPosition(0.0, 0.0, -1.0 * CLHEP::mm);
        SetDirection(0.0, 0.0, 1.0);
    } else if (preset == "isotropic_neutron") {
        SetParticle("neutron");
        SetMonoEnergy(1.0 * CLHEP::MeV);
        SetPointPosition(0.0, 0.0, 0.0);
        SetIsotropic();
    } else if (preset == "plane_proton_beam") {
        SetParticle("proton");
        SetMonoEnergy(10.0 * CLHEP::MeV);
        SetPlaneBeam(1.0 * CLHEP::mm, -1.0 * CLHEP::mm, "+z");
    } else {
        throw std::runtime_error("Unsupported source preset: '" + presetName + "'");
    }

    presetName_ = preset;
    Current().preset = preset;
    configured_ = true;
}

void SourceManager::SetParticle(const std::string& particleName)
{
    const std::string name = StringUtils::Trim(particleName);
    if (name.empty()) throw std::runtime_error("SourceManager::SetParticle requires non-empty particleName");
    RequireSingleSourceForCommand("particle");
    Current().particleName = name;
    Current().ion = false;
    // Once GPS exists, update only the field explicitly changed. Replaying the
    // complete cached configuration would overwrite unrelated native /gps/*
    // settings (for example /gps/ene/mono after a particle-only update).
    if (gps_) ApplyParticleToGPS();
    else MarkGPSConfigDirty();
    configured_ = true;
}

std::string SourceManager::GetParticleName() const
{
    return Current().particleName;
}

void SourceManager::SetMonoEnergy(double energy)
{
    if (!std::isfinite(energy) || energy <= 0.0)
        throw std::runtime_error("SourceManager::SetMonoEnergy requires finite energy > 0");
    RequireSingleSourceForCommand("energy");
    Current().monoEnergy = energy;
    Current().restEnergy = false;
    Current().energyType = "mono";
    if (gps_) ApplyMonoEnergyToGPS();
    else MarkGPSConfigDirty();
    configured_ = true;
}

double SourceManager::GetMonoEnergy() const
{
    return Current().monoEnergy;
}

void SourceManager::SetPosition(const std::string& type, const std::string& shape, const std::vector<double>& params)
{
    for (double value : params) {
        if (!std::isfinite(value))
            throw std::runtime_error("SourceManager::SetPosition requires finite position parameters");
    }
    RequireSingleSourceForCommand("position");
    SourceSpec& spec = Current();
    spec.positionType = type;
    spec.positionShape = shape;
    spec.positionParams = params;
    spec.hasPosition = true;
    if (gps_) ApplyPositionToGPS();
    else MarkGPSConfigDirty();
    configured_ = true;
}

void SourceManager::SetPointPosition(double x, double y, double z)
{
    SetPosition("Point", "", {x, y, z});
}

void SourceManager::SetDirection(double x, double y, double z)
{
    if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z))
        throw std::runtime_error("SourceManager::SetDirection requires finite direction components");
    const double magnitude = std::hypot(x, y, z);
    if (!std::isfinite(magnitude) || magnitude <= 0.0)
        throw std::runtime_error("SourceManager::SetDirection requires a finite non-zero direction vector");
    RequireSingleSourceForCommand("direction");
    const double invMag = 1.0 / magnitude;
    SourceSpec& spec = Current();
    spec.direction = {x * invMag, y * invMag, z * invMag};
    spec.hasDirection = true;
    spec.isotropic = false;
    if (!loadingNamedSources_ && !spec.angular.empty() && spec.angular != "fixed") spec.angular.clear();
    if (gps_) ApplyAngularDistributionToGPS();
    else MarkGPSConfigDirty();
    configured_ = true;
}

void SourceManager::SetIsotropic()
{
    RequireSingleSourceForCommand("isotropic");
    SourceSpec& spec = Current();
    spec.isotropic = true;
    spec.hasDirection = false;
    spec.direction.clear();
    spec.angular.clear();
    spec.hasThetaRange = false;
    spec.minTheta = 0.0;
    spec.maxTheta = 180.0 * deg;
    if (gps_) ApplyAngularDistributionToGPS();
    else MarkGPSConfigDirty();
    configured_ = true;
}

void SourceManager::SetPlaneBeam(double radius, double z, const std::string& direction)
{
    SetPlaneBeamAt(radius, 0.0, 0.0, z, direction);
}

void SourceManager::SetPlaneBeamAt(double radius, double x, double y, double z,
                                   const std::string& direction)
{
    if (!std::isfinite(radius) || radius <= 0.0)
        throw std::runtime_error("SourceManager::SetPlaneBeam requires finite radius > 0");
    const auto d = ParseDirectionVector(NormalizeDirectionToken(direction));
    SetPosition("Plane", "Circle", {x, y, z, radius});
    SetDirection(d[0], d[1], d[2]);
    configured_ = true;
}

void SourceManager::SetPlaneRectangleAt(double halfX, double halfY, double x, double y, double z,
                                         const std::string& direction)
{
    if (!std::isfinite(halfX) || !std::isfinite(halfY) || halfX <= 0.0 || halfY <= 0.0)
        throw std::runtime_error("SourceManager::SetPlaneRectangleAt requires finite halfx and halfy > 0");
    const auto d = ParseDirectionVector(NormalizeDirectionToken(direction));
    SetPosition("Plane", "Rectangle", {x, y, z, halfX, halfY});
    SetDirection(d[0], d[1], d[2]);
    configured_ = true;
}

void SourceManager::SetVerboseLevel(int level)
{
    if (level < 0) throw std::runtime_error("SourceManager::SetVerboseLevel requires level >= 0");
    verboseLevel_ = level;
}

int SourceManager::GetVerboseLevel() const
{
    return verboseLevel_;
}

void SourceManager::PrintSummary() const
{
    G4cout << "[SourceManager] configured=" << (configured_ ? "true" : "false")
           << ", particle=" << (Current().particleName.empty() ? "<gps-default>" : Current().particleName)
           << ", monoEnergy=" << Current().monoEnergy
           << ", preset=" << (presetName_.empty() ? "<none>" : presetName_)
           << ", verbose=" << verboseLevel_
           << ", gps=" << (gps_ ? "available" : "lazy")
           << ", sources=" << sources_.size()
           << G4endl;
    for (const auto& spec : sources_) G4cout << "[SourceManager]   " << spec.Describe() << G4endl;
    G4cout << "[SourceManager] Geant4 native /gps/... commands remain available for advanced source tuning." << G4endl;
}

bool SourceManager::IsConfigured() const
{
    return configured_;
}

const std::string& SourceManager::GetPresetName() const
{
    return presetName_;
}

std::size_t SourceManager::GetSourceCount() const
{
    return sources_.size();
}

const std::vector<SourceManager::SourceSpec>& SourceManager::GetSources() const
{
    return sources_;
}

void SourceManager::EnsureGPS() const
{
    if (!gps_) {
        gps_ = std::make_unique<G4GeneralParticleSource>();
        gpsConfigDirty_ = true;
    }
}

void SourceManager::MarkGPSConfigDirty()
{
    gpsConfigDirty_ = true;
}

G4SingleParticleSource* SourceManager::CurrentGPSSource() const
{
    if (!gps_) return nullptr;
    if (sources_.size() > 1) gps_->SetCurrentSourceto(static_cast<G4int>(current_));
    return gps_->GetCurrentSource();
}

void SourceManager::ApplyCurrentConfigurationToGPS() const
{
    if (!gps_ || !gpsConfigDirty_) return;
    deferredSources_.clear();
    configuredGPSSources_.clear();
    if (sources_.size() > 1) {
        // One GPS source per [source.<name>]; GPS picks one per event with
        // probability intensity / sum(intensity).
        gps_->ClearAll();
        for (std::size_t index = 0; index < sources_.size(); ++index) {
            const auto& spec = sources_[index];
            gps_->AddaSource(spec.intensity);
            ApplySpec(spec, *gps_->GetCurrentSource());
            configuredGPSSources_[gps_->GetCurrentSource()] = index;
            ObserveGPS(index, *gps_->GetCurrentSource(), "gps_apply");
            if (spec.ion || !spec.confineVolume.empty()) deferredSources_[gps_->GetCurrentSource()].index = index;
        }
        gps_->SetCurrentSourceto(0);
    } else {
        ApplySpec(sources_.front(), *gps_->GetCurrentSource());
        configuredGPSSources_[gps_->GetCurrentSource()] = 0;
        ObserveGPS(0, *gps_->GetCurrentSource(), "gps_apply");
        if (sources_.front().ion || !sources_.front().confineVolume.empty())
            deferredSources_[gps_->GetCurrentSource()].index = 0;
    }
    gpsConfigDirty_ = false;
    deferredApplied_ = false;
}

void SourceManager::ApplySpec(const SourceSpec& spec, G4SingleParticleSource& source)
{
    if (!spec.ion) ApplyParticle(spec, source);  // ions are created in PrepareForRun
    ApplyEnergy(spec, source);
    ApplyPosition(spec, source);
    ApplyAngular(spec, source);
}

void SourceManager::ApplyParticleToGPS() const
{
    if (auto* source = CurrentGPSSource()) ApplyParticle(Current(), *source);
}

void SourceManager::ApplyMonoEnergyToGPS() const
{
    if (auto* source = CurrentGPSSource()) ApplyEnergy(Current(), *source);
}

void SourceManager::ApplyPositionToGPS() const
{
    if (auto* source = CurrentGPSSource()) ApplyPosition(Current(), *source);
}

void SourceManager::ApplyAngularDistributionToGPS() const
{
    if (auto* source = CurrentGPSSource()) ApplyAngular(Current(), *source);
}

void SourceManager::ApplyParticle(const SourceSpec& spec, G4SingleParticleSource& source)
{
    if (spec.ion) {
        G4ParticleDefinition* ion = G4IonTable::GetIonTable()->GetIon(spec.ionZ, spec.ionA, spec.ionExcitation);
        if (!ion) {
            throw std::runtime_error("SourceManager cannot create ion Z=" + std::to_string(spec.ionZ) +
                                     " A=" + std::to_string(spec.ionA) + " E*=" + Number(spec.ionExcitation / keV) +
                                     " keV (is G4GenericIon in the physics list?)");
        }
        source.SetParticleDefinition(ion);
        source.SetParticleCharge(spec.ionCharge * eplus);
        return;
    }
    if (StringUtils::Trim(spec.particleName).empty() || spec.particleName == "ion") return;
    G4ParticleDefinition* particle = G4ParticleTable::GetParticleTable()->FindParticle(spec.particleName);
    if (!particle) throw std::runtime_error("SourceManager::SetParticle unknown particle: '" + spec.particleName + "'");
    source.SetParticleDefinition(particle);
}

void SourceManager::ApplyEnergy(const SourceSpec& spec, G4SingleParticleSource& source)
{
    auto* ene = source.GetEneDist();
    const std::string& type = spec.energyType;
    if (type == "mono") {
        if (spec.monoEnergy <= 0.0 && !spec.restEnergy) return;
        ene->SetEnergyDisType("Mono");
        ene->SetMonoEnergy(spec.monoEnergy);
    } else if (type == "gauss") {
        ene->SetEnergyDisType("Gauss");
        ene->SetMonoEnergy(spec.monoEnergy);
        ene->SetBeamSigmaInE(spec.energySigma);
    } else if (type == "uniform") {
        ene->SetEnergyDisType("Lin");
        ene->SetEmin(spec.energyMin);
        ene->SetEmax(spec.energyMax);
        ene->SetGradient(0.0);
        ene->SetInterCept(1.0);
    } else if (type == "power") {
        ene->SetEnergyDisType("Pow");
        ene->SetEmin(spec.energyMin);
        ene->SetEmax(spec.energyMax);
        ene->SetAlpha(spec.alpha);
    } else if (type == "exp") {
        ene->SetEnergyDisType("Exp");
        ene->SetEmin(spec.energyMin);
        ene->SetEmax(spec.energyMax);
        ene->SetEzero(spec.ezero);
    } else if (type == "histogram") {
        // GPS "User" histogram: first point = lower edge (weight ignored),
        // each further point = (upper edge, bin weight).
        ene->SetEnergyDisType("User");
        ene->ReSetHist("energy");
        for (const auto& point : spec.spectrum) ene->UserEnergyHisto(G4ThreeVector(point.first, point.second, 0.0));
    } else if (type == "points") {
        ene->SetEnergyDisType("Arb");
        ene->ReSetHist("arb");
        for (const auto& point : spec.spectrum) ene->ArbEnergyHisto(G4ThreeVector(point.first, point.second, 0.0));
        ene->ArbInterpolate("Lin");
    }
}

void SourceManager::ApplyPosition(const SourceSpec& spec, G4SingleParticleSource& source)
{
    if (!spec.hasPosition) return;
    auto* pos = source.GetPosDist();
    pos->SetPosDisType(spec.positionType);
    if (!spec.positionShape.empty()) pos->SetPosDisShape(spec.positionShape);
    const auto& p = spec.positionParams;
    if (p.size() >= 3) pos->SetCentreCoords(G4ThreeVector(p[0], p[1], p[2]));
    const std::string& shape = spec.positionShape;
    if (spec.positionType == "Plane") {
        if (shape == "Rectangle" && p.size() == 5) {
            pos->SetHalfX(p[3]);
            pos->SetHalfY(p[4]);
        } else if (shape == "Circle" && p.size() >= 4) {
            pos->SetRadius(p[3]);
        } else if (shape == "Annulus") {
            pos->SetRadius(spec.radius);
            pos->SetRadius0(spec.innerRadius);
        } else if (shape == "Ellipse" || shape == "Square") {
            pos->SetHalfX(spec.halfX);
            pos->SetHalfY(spec.halfY);
        }
    } else if (spec.positionType == "Volume") {
        pos->SetRadius(spec.radius);
        pos->SetHalfX(spec.halfX);
        pos->SetHalfY(spec.halfY);
        pos->SetHalfZ(spec.halfZ);
        if (shape == "Para") {
            pos->SetParAlpha(0.0);
            pos->SetParTheta(0.0);
            pos->SetParPhi(0.0);
        }
    } else if (spec.positionType == "Beam") {
        // GPS Beam/Circle truncates the Gaussian at the shape radius; a round
        // spot is therefore an untruncated Beam/Ellipse with equal sigmas.
        const bool round = shape == "Circle";
        pos->SetPosDisShape("Ellipse");
        pos->SetBeamSigmaInX(round ? spec.beamSigmaR : spec.beamSigmaX);
        pos->SetBeamSigmaInY(round ? spec.beamSigmaR : spec.beamSigmaY);
    }
    if (spec.hasRotation) {
        pos->SetPosRot1(G4ThreeVector(spec.rot1[0], spec.rot1[1], spec.rot1[2]));
        pos->SetPosRot2(G4ThreeVector(spec.rot2[0], spec.rot2[1], spec.rot2[2]));
    }
}

void SourceManager::ApplyAngular(const SourceSpec& spec, G4SingleParticleSource& source)
{
    auto* ang = source.GetAngDist();
    const std::string& angular = spec.angular;
    if (angular.empty() || angular == "fixed") {
        if (spec.isotropic) {
            ang->SetAngDistType("iso");
            ang->SetMinTheta(0.0);
            ang->SetMaxTheta(180.0 * deg);
            ang->SetMinPhi(0.0);
            ang->SetMaxPhi(360.0 * deg);
            return;
        }
        if (spec.hasDirection && spec.direction.size() == 3) {
            // beam1d samples a Gaussian around its own -Z axis and does not
            // consume SetParticleMomentumDirection. Planar uses that explicit
            // unit vector, as required by the fixed-direction source contract.
            ang->SetAngDistType("planar");
            ang->SetParticleMomentumDirection(G4ThreeVector(spec.direction[0], spec.direction[1], spec.direction[2]));
        }
        return;
    }
    if (angular == "focused") {
        ang->SetAngDistType("focused");
        ang->SetFocusPoint(G4ThreeVector(spec.focus[0], spec.focus[1], spec.focus[2]));
        return;
    }
    if (spec.hasDirection) {
        // GPS emits iso/cos/beam momenta around -z' of the angular reference
        // frame (x', y', z' = x' x y'). Choose z' = -direction and x' = the
        // global x axis projected perpendicular to it (global y if parallel),
        // so beam2d angular_sigma_x acts along x for a beam along z.
        const G4ThreeVector d = G4ThreeVector(spec.direction[0], spec.direction[1], spec.direction[2]).unit();
        const G4ThreeVector zPrime = -d;
        G4ThreeVector xPrime = G4ThreeVector(1.0, 0.0, 0.0) - d * d.x();
        if (xPrime.mag() < 1e-6) xPrime = G4ThreeVector(0.0, 1.0, 0.0) - d * d.y();
        xPrime = xPrime.unit();
        const G4ThreeVector yPrime = zPrime.cross(xPrime).unit();
        ang->DefineAngRefAxes("angref1", xPrime);
        ang->DefineAngRefAxes("angref2", yPrime);
    }
    if (angular == "isotropic" || angular == "cos") {
        ang->SetAngDistType(angular == "cos" ? "cos" : "iso");
        ang->SetMinTheta(spec.minTheta);
        ang->SetMaxTheta(spec.maxTheta);
    } else if (angular == "beam1d") {
        ang->SetAngDistType("beam1d");
        ang->SetBeamSigmaInAngR(spec.angularSigma);
    } else if (angular == "beam2d") {
        ang->SetAngDistType("beam2d");
        ang->SetBeamSigmaInAngX(spec.angularSigmaX);
        ang->SetBeamSigmaInAngY(spec.angularSigmaY);
    }
}

std::vector<double> SourceManager::ParseDirectionVector(const std::string& text)
{
    const std::string value = NormalizeDirectionToken(text);
    if (value == "+x") return {1.0, 0.0, 0.0};
    if (value == "-x") return {-1.0, 0.0, 0.0};
    if (value == "+y") return {0.0, 1.0, 0.0};
    if (value == "-y") return {0.0, -1.0, 0.0};
    if (value == "+z") return {0.0, 0.0, 1.0};
    if (value == "-z") return {0.0, 0.0, -1.0};
    const auto values = ParseDoubleVec3(text);
    if (values.size() != 3) throw std::runtime_error("SourceManager expected direction vector with 3 values: '" + text + "'");
    return values;
}

std::string SourceManager::NormalizeDirectionToken(const std::string& direction)
{
    return StringUtils::ToLower(StringUtils::Trim(direction));
}


std::vector<effective_config::Field> SourceManager::ProjectEffectiveConfigFields() const
{
    using namespace effective_config;
    std::vector<Field> result;
    const auto addGlobal=[&](const char* key,Value value,std::initializer_list<const char*> keys){
        result.push_back(effective_->Make(FieldPath("source",key),std::move(value),"","source",keys));
    };
    addGlobal("mode",phaseSpace_?"phase_space":(sources_.size()>1?"named":"single"),{});
    addGlobal("verbose",verboseLevel_,{"verbose"});
    if(phaseSpace_) {
        addGlobal("phase_space_files",List(phaseSpaceFiles_),{"phase_space_file"});
        addGlobal("phase_space_recycle",phaseSpaceRecycle_,{"phase_space_recycle"});
        addGlobal("phase_space_histories",static_cast<std::int64_t>(phaseSpace_->size()),{"phase_space_file"});
        addGlobal("phase_space_particles",static_cast<std::int64_t>(phaseSpaceParticleCount_),{"phase_space_file"});
        Value::Array inputs;
        for(const auto& input:phaseSpaceInputs_)inputs.emplace_back(Value::Object{{"path",input.path},{"sha256",input.sha256}});
        addGlobal("phase_space_inputs",inputs,{"phase_space_file"});
        for(auto& field:result) if(field.path.rfind("/source/phase_space_",0)==0)
            for(const auto& input:phaseSpaceInputs_) {
                Origin origin; origin.kind="phase_space_file";origin.file=input.path;
                origin.input_sha256=input.sha256;origin.disposition="derived";
                field.origins.push_back(std::move(origin));
            }
        return result;
    }
    for(const auto& spec:sources_) {
        const std::string section=spec.name.empty()?"source":"source."+StringUtils::ToLower(spec.name);
        const auto path=[&](const char* key){return spec.name.empty()?FieldPath("source",key):ObjectFieldPath("source",spec.name,key);};
        const auto add=[&](const char* key,Value value,const char* unit,std::initializer_list<const char*> keys,bool presetAffected=false){
            Field f=effective_->Make(path(key),std::move(value),unit,section,keys);
            if(presetAffected && !spec.preset.empty()) {
                std::vector<Origin> chain{f.origins.front()};chain.front().disposition="shadowed";
                for(const auto& d:effective_->reader.GetDeclarations())if(d.normalizedSection==section && d.normalizedKey=="preset") {
                    Origin o;o.kind="main_ini";o.file=effective_->reader.GetFilename();o.line=d.lineNumber;
                    o.section=d.originalSection;o.key=d.originalKey;o.raw=d.value;o.input_sha256=effective_->reader.GetInputSha256();o.disposition="shadowed";chain.push_back(o);
                }
                Origin preset;preset.kind="preset";preset.raw=spec.preset;preset.disposition=f.origins.size()>1?"shadowed":"derived";chain.push_back(preset);
                chain.insert(chain.end(),f.origins.begin()+1,f.origins.end());f.origins=std::move(chain);
                if(!f.requested_known){f.requested=spec.preset;f.requested_known=true;}
            }
            if(!spec.spectrumFile.empty() && (std::string(key)=="spectrum" || std::string(key)=="spectrum_file" || std::string(key)=="spectrum_sha256")) {
                Origin input;input.kind="spectrum_file";input.file=spec.spectrumFile;
                input.input_sha256=spec.spectrumSha256;input.disposition="derived";
                f.origins.push_back(std::move(input));
            }
            result.push_back(std::move(f));
        };
        add("intensity",spec.intensity,"",{"intensity"});
        if(!spec.preset.empty())add("preset",spec.preset,"",{"preset"});
        if(!spec.particleName.empty() || spec.ion)add("particle",spec.ion?"ion":spec.particleName,"",{"particle"},true);
        if(spec.ion){add("ion_z",spec.ionZ,"",{"ion"});add("ion_a",spec.ionA,"",{"ion"});
            add("ion_charge",spec.ionCharge,"eplus",{"ion"});add("ion_excitation",spec.ionExcitation/CLHEP::MeV,"MeV",{"ion"});
            add("rest_energy",spec.restEnergy,"",{"energy"});}
        // A zero GPS-default mono cache is not a known configured energy.
        if(spec.monoEnergy>0 || spec.restEnergy || spec.energyType!="mono") {
            add("energy_type",spec.energyType,"",{"energy_type"},true);
            if(spec.energyType=="mono" || spec.energyType=="gauss")add("energy",spec.monoEnergy/CLHEP::MeV,"MeV",{"energy"},true);
            if(spec.energyType=="gauss")add("energy_sigma",spec.energySigma/CLHEP::MeV,"MeV",{"energy_sigma"});
            if(spec.energyType=="uniform" || spec.energyType=="power" || spec.energyType=="exp") {
                add("energy_min",spec.energyMin/CLHEP::MeV,"MeV",{"energy_min"});add("energy_max",spec.energyMax/CLHEP::MeV,"MeV",{"energy_max"});
                if(spec.energyType=="power")add("alpha",spec.alpha,"",{"alpha"});
                if(spec.energyType=="exp")add("ezero",spec.ezero/CLHEP::MeV,"MeV",{"ezero"});
            }
            if(spec.energyType=="points" || spec.energyType=="histogram") {
                add("spectrum_file",spec.spectrumFile,"",{"spectrum_file"});add("spectrum_sha256",spec.spectrumSha256,"",{"spectrum_file"});
                Value::Array points;for(const auto& point:spec.spectrum)points.emplace_back(Value::Array{point.first/CLHEP::MeV,point.second});
                add("spectrum",points,"MeV,density_or_bin_weight",{"spectrum_file"});
            }
        }
        add("has_position",spec.hasPosition,"",{"position_type","position","center"},true);
        if(spec.hasPosition) {
            add("position_type",spec.positionType,"",{"position_type","position"},true);
            if(!spec.positionShape.empty())add("shape",spec.positionShape,"",{"shape"},true);
            if(spec.positionParams.size()>=3)add("center",Numbers({spec.positionParams[0],spec.positionParams[1],spec.positionParams[2]},CLHEP::mm),"mm",{"position","center"},true);
            const auto& shape=spec.positionShape;
            if(spec.positionType=="Plane" && shape=="Circle" && spec.positionParams.size()>3)add("radius",spec.positionParams[3]/CLHEP::mm,"mm",{"radius"},true);
            if(shape=="Annulus" || (spec.positionType=="Volume" && (shape=="Sphere" || shape=="Cylinder")))add("radius",spec.radius/CLHEP::mm,"mm",{"radius"});
            if(shape=="Annulus")add("inner_radius",spec.innerRadius/CLHEP::mm,"mm",{"inner_radius"});
            if(spec.positionType=="Plane" && shape=="Rectangle" && spec.positionParams.size()>4) {
                add("halfx",spec.positionParams[3]/CLHEP::mm,"mm",{"halfx"});add("halfy",spec.positionParams[4]/CLHEP::mm,"mm",{"halfy"});
            } else if(shape=="Ellipse" || shape=="Square" || (spec.positionType=="Volume" && shape!="Sphere" && shape!="Cylinder")) {
                add("halfx",spec.halfX/CLHEP::mm,"mm",{"halfx"});add("halfy",spec.halfY/CLHEP::mm,"mm",shape=="Square"?std::initializer_list<const char*>{"halfx"}:std::initializer_list<const char*>{"halfy"});
            }
            if(spec.positionType=="Volume" && shape!="Sphere")add("halfz",spec.halfZ/CLHEP::mm,"mm",{"halfz"});
            if(spec.positionType=="Beam") {
                if(shape=="Circle")add("beam_sigma",spec.beamSigmaR/CLHEP::mm,"mm",{"beam_sigma"});
                else {add("beam_sigma_x",spec.beamSigmaX/CLHEP::mm,"mm",{"beam_sigma_x"});add("beam_sigma_y",spec.beamSigmaY/CLHEP::mm,"mm",{"beam_sigma_y"});}
            }
            add("has_rotation",spec.hasRotation,"",{"rot1","rot2"});
            if(spec.hasRotation){add("rot1",Numbers(spec.rot1),"",{"rot1"});add("rot2",Numbers(spec.rot2),"",{"rot2"});}
            if(!spec.confineVolume.empty())add("confine",spec.confineVolume,"",{"confine"});
        }
        add("has_direction",spec.hasDirection,"",{"direction"},true);
        if(spec.hasDirection)add("direction",Numbers(spec.direction),"",{"direction"},true);
        if(!spec.angular.empty() || spec.isotropic || spec.hasDirection) {
            add("angular",spec.angular.empty()?(spec.isotropic?"isotropic":"fixed"):spec.angular,"",{"isotropic","direction","angular"},true);
            add("has_theta_range",spec.hasThetaRange,"",{"min_theta","max_theta"});
            if(spec.angular=="isotropic" || spec.angular=="cos") {add("min_theta",spec.minTheta/CLHEP::deg,"deg",{"min_theta"});add("max_theta",spec.maxTheta/CLHEP::deg,"deg",{"max_theta"});}
            if(spec.angular=="beam1d")add("angular_sigma",spec.angularSigma/CLHEP::deg,"deg",{"angular_sigma"});
            if(spec.angular=="beam2d"){add("angular_sigma_x",spec.angularSigmaX/CLHEP::deg,"deg",{"angular_sigma_x"});add("angular_sigma_y",spec.angularSigmaY/CLHEP::deg,"deg",{"angular_sigma_y"});}
            if(spec.angular=="focused")add("focus",Numbers(spec.focus,CLHEP::mm),"mm",{"focus"});
        }
    }
    return result;
}
std::vector<effective_config::Field> SourceManager::ExportEffectiveConfigFields() const
{ return effective_->accepted?effective_->fields:ProjectEffectiveConfigFields(); }
effective_config::Value SourceManager::ExportEffectiveConfigEvidence() const { return effective_->Evidence(); }
void SourceManager::ConfirmEffectiveConfigMutation(const std::string& command,const effective_config::Origin& origin)
{
    const bool native=command.rfind("/gps/",0)==0;
    if (native) nativeGPSIdentityUncertain_ = true;
    auto projected=ProjectEffectiveConfigFields();std::vector<std::string> targets;
    const auto name=StringUtils::ToLower(command.substr(0,command.find_first_of(" \t")));
    for(const auto& f:projected){const auto key=f.path.substr(f.path.find_last_of('/')+1);
        const bool all=name.find("preset")!=std::string::npos || name.find("reset")!=std::string::npos;
        const bool energy=name.find("energy")!=std::string::npos && (key=="energy" || key=="energy_type");
        const bool particle=name.find("particle")!=std::string::npos && (key=="particle" || key.rfind("ion_",0)==0);
        const bool direction=(name.find("direction")!=std::string::npos || name.find("isotropic")!=std::string::npos) &&
            (key=="angular" || key=="direction" || key=="has_direction" || key=="has_theta_range");
        const bool position=name.find("point")!=std::string::npos || name.find("plane")!=std::string::npos;
        if(all || energy || particle || direction || (position && (key=="center" || key=="position_type" || key=="shape" || key=="has_position" || key=="radius" || key=="halfx" || key=="halfy" || key=="direction" || key=="angular")))targets.push_back(f.path);
    }
    effective_->Confirm(std::move(projected),command,origin,native && !phaseSpace_,targets);
    if(native)effective_->Record(effective_config::Receipt(effective_config::FieldPath("source","mode"),"native_gps_unmapped","native_command",command,"none","unknown","GPS mutation is not represented by Manager cached values"));
}
void SourceManager::ObserveGPS(std::size_t index,const G4SingleParticleSource& source,const std::string& stage) const
{
    using namespace effective_config;
    if(nativeGPSIdentityUncertain_) return;
    const auto identity=configuredGPSSources_.find(&source);
    if(identity==configuredGPSSources_.end() || identity->second!=index) return;
    const auto& spec=sources_.at(index);
    const auto path=[&](const char* key){return spec.name.empty()?FieldPath("source",key):ObjectFieldPath("source",spec.name,key);};
    const bool unknown=std::any_of(effective_->fields.begin(),effective_->fields.end(),[](const Field& f){return f.application_status==ApplicationStatus::Unknown;});
    const auto record=[&](const char* key,Value value){
        if(std::none_of(effective_->fields.begin(),effective_->fields.end(),[&](const Field& f){return f.path==path(key);}))return;
        effective_->Record(Receipt(path(key),std::move(value),stage,"SourceManager actual GPS readback",
        "kernel_constructed",unknown?"unknown":"applied",unknown?"Native GPS mutation: observed GPS value is independent of Manager configuration":""));};
    if(source.GetParticleDefinition() && (!spec.ion || stage=="source_prepare"))record("particle",source.GetParticleDefinition()->GetParticleName());
    const std::map<std::string,std::string> energyTypes{{"Mono","mono"},{"Gauss","gauss"},{"Lin","uniform"},{"Pow","power"},{"Exp","exp"},{"Arb","points"},{"User","histogram"}};
    const auto energyType=energyTypes.find(source.GetEneDist()->GetEnergyDisType());
    record("energy_type",energyType==energyTypes.end()?std::string(source.GetEneDist()->GetEnergyDisType()):energyType->second);
    const auto nativeEnergy=source.GetEneDist()->GetEnergyDisType();
    if(nativeEnergy=="Mono" || nativeEnergy=="Gauss")record("energy",source.GetEneDist()->GetMonoEnergy()/CLHEP::MeV);
    if(nativeEnergy=="Gauss")record("energy_sigma",source.GetEneDist()->GetSE()/CLHEP::MeV);
    if(nativeEnergy=="Lin" || nativeEnergy=="Pow" || nativeEnergy=="Exp") {
        record("energy_min",source.GetEneDist()->GetEmin()/CLHEP::MeV);
        record("energy_max",source.GetEneDist()->GetEmax()/CLHEP::MeV);
        if(nativeEnergy=="Pow")record("alpha",source.GetEneDist()->Getalpha());
        if(nativeEnergy=="Exp")record("ezero",source.GetEneDist()->GetEzero()/CLHEP::MeV);
    }
    if(spec.hasPosition){record("position_type",source.GetPosDist()->GetPosDisType());
        const auto* position=source.GetPosDist();
        const auto& center=position->GetCentreCoords();record("center",Value::Array{center.x()/CLHEP::mm,center.y()/CLHEP::mm,center.z()/CLHEP::mm});
        // Beam/Circle is intentionally implemented as native Beam/Ellipse;
        // keep that raw readback separate rather than forging a shape match.
        if(spec.positionType!="Beam")record("shape",position->GetPosDisShape());
        for(const auto& field:effective_->fields) if(field.path==path("radius"))record("radius",position->GetRadius()/CLHEP::mm);
        for(const auto& field:effective_->fields) if(field.path==path("inner_radius"))record("inner_radius",position->GetRadius0()/CLHEP::mm);
        for(const auto& field:effective_->fields) if(field.path==path("halfx"))record("halfx",position->GetHalfX()/CLHEP::mm);
        for(const auto& field:effective_->fields) if(field.path==path("halfy"))record("halfy",position->GetHalfY()/CLHEP::mm);
        for(const auto& field:effective_->fields) if(field.path==path("halfz"))record("halfz",position->GetHalfZ()/CLHEP::mm);
        if(position->GetConfined())record("confine",position->GetConfineVolume());
    }
    const auto angular=source.GetAngDist()->GetDistType();
    static const std::map<std::string,std::string> angularTypes{{"planar","fixed"},{"iso","isotropic"},{"cos","cos"},{"beam1d","beam1d"},{"beam2d","beam2d"},{"focused","focused"}};
    const auto foundAngular=angularTypes.find(angular);
    if(foundAngular!=angularTypes.end())record("angular",foundAngular->second);
    if(angular=="iso" || angular=="cos") {
        record("min_theta",source.GetAngDist()->GetMinTheta()/CLHEP::deg);
        record("max_theta",source.GetAngDist()->GetMaxTheta()/CLHEP::deg);
    }
    if(angular=="planar" && spec.hasDirection) {
        const auto direction=source.GetAngDist()->GetDirection();
        record("direction",Value::Array{direction.x(),direction.y(),direction.z()});
    }
}

void SourceManager::ObserveEffectiveRunSource(const std::string& stage) const
{
    if (phaseSpace_ || !gps_) return;
    auto* actual=G4GeneralParticleSourceData::Instance();
    const int count=actual->GetSourceVectorSize();
    bool mapped=!nativeGPSIdentityUncertain_ && count==static_cast<int>(sources_.size());
    for(int i=0;i<count && mapped;++i) {
        const auto found=configuredGPSSources_.find(actual->GetCurrentSource(i));
        mapped=found!=configuredGPSSources_.end() && found->second<sources_.size();
    }
    if(!mapped) {
        using namespace effective_config;
        Value::Array inventory;
        for(int i=0;i<count;++i) {
            const auto* source=actual->GetCurrentSource(i);
            Value::Object entry{{"native_index",i},{"intensity",actual->GetIntensity(i)},
                {"energy_type",source->GetEneDist()->GetEnergyDisType()},
                {"position_type",source->GetPosDist()->GetPosDisType()}};
            if(source->GetParticleDefinition())entry["particle"]=source->GetParticleDefinition()->GetParticleName();
            if(source->GetEneDist()->GetEnergyDisType()=="Mono")entry["energy_MeV"]=source->GetEneDist()->GetMonoEnergy()/CLHEP::MeV;
            inventory.emplace_back(std::move(entry));
        }
        auto receipt=Receipt("/source/mode","native_gps_unmapped",stage,
            "Actual GPS inventory independent of configured source identities","none","unknown",
            "Native GPS mutations invalidate INI identity attribution even when source counts are unchanged");
        std::get<Value::Object>(receipt.data)["native_inventory"]=std::move(inventory);
        effective_->Record(std::move(receipt));
        return;
    }
    effective_->Record(effective_config::Receipt("/source/mode",count>1?"named":"single",stage,"Actual identity-mapped GPS source inventory"));
    for(int i=0;i<count;++i) {
        const auto* source=actual->GetCurrentSource(i);
        const auto index=configuredGPSSources_.at(source);
        ObserveGPS(index,*source,stage);
        using namespace effective_config;
        const auto& spec=sources_.at(index);
        const auto path=spec.name.empty()?FieldPath("source","intensity"):ObjectFieldPath("source",spec.name,"intensity");
        effective_->Record(Receipt(path,actual->GetIntensity(i),stage,"Actual GPS source intensity readback"));
    }
}
