#include "Source/SourceManager.hh"

#include "Config/ConfigManager.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4GeneralParticleSource.hh"
#include "G4ParticleDefinition.hh"
#include "G4ParticleTable.hh"
#include "G4SingleParticleSource.hh"
#include "G4SPSAngDistribution.hh"
#include "G4SPSEneDistribution.hh"
#include "G4SPSPosDistribution.hh"
#include "G4ThreeVector.hh"
#include "G4SystemOfUnits.hh"
#include "G4ios.hh"

#include <cctype>
#include <cmath>
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

}  // namespace

SourceManager::SourceManager()
    : gps_(std::make_unique<G4GeneralParticleSource>())
{
}

SourceManager::~SourceManager() = default;

G4GeneralParticleSource* SourceManager::GetGPS()
{
    EnsureGPS();
    return gps_.get();
}

const G4GeneralParticleSource* SourceManager::GetGPS() const
{
    EnsureGPS();
    return gps_.get();
}

void SourceManager::ResetGPS()
{
    gps_ = std::make_unique<G4GeneralParticleSource>();
    particleName_.clear();
    monoEnergy_ = 0.0;
    presetName_.clear();
    configured_ = false;
}

void SourceManager::LoadFromConfig(const ConfigManager& config)
{
    if (!config.HasSection("source")) return;

    if (config.HasKey("source", "preset")) {
        const std::string preset = StringUtils::Trim(config.GetString("source", "preset", ""));
        if (!preset.empty()) ApplyPreset(preset);
    }
    if (config.HasKey("source", "particle")) {
        const std::string particle = StringUtils::Trim(config.GetString("source", "particle", ""));
        if (!particle.empty()) SetParticle(particle);
    }
    if (config.HasKey("source", "energy")) {
        const std::string energy = StringUtils::Trim(config.GetString("source", "energy", ""));
        if (!energy.empty()) SetMonoEnergy(UnitParser::ParseEnergy(energy));
    }
    if (config.HasKey("source", "verbose")) {
        SetVerboseLevel(config.GetInt("source", "verbose", verboseLevel_));
    }

    const bool isotropic = config.GetBool("source", "isotropic", false);
    if (config.HasKey("source", "position_type")) {
        const std::string type = StringUtils::ToLower(StringUtils::Trim(config.GetString("source", "position_type", "")));
        if (type == "point" && config.HasKey("source", "position")) {
            const auto pos = ReadVector3WithUnit(config, "source", "position");
            SetPointPosition(pos[0], pos[1], pos[2]);
        } else if (type == "plane") {
            const double radius = config.HasKey("source", "radius")
                ? UnitParser::ParseLength(config.GetString("source", "radius"))
                : 1.0 * CLHEP::mm;
            double z = -1.0 * CLHEP::mm;
            if (config.HasKey("source", "center")) {
                const auto center = ReadVector3WithUnit(config, "source", "center");
                z = center[2];
            }
            SetPlaneBeam(radius, z, config.GetString("source", "direction", "+z"));
        }
    } else if (config.HasKey("source", "position")) {
        const auto pos = ReadVector3WithUnit(config, "source", "position");
        SetPointPosition(pos[0], pos[1], pos[2]);
    }

    if (isotropic) {
        SetIsotropic();
    } else if (config.HasKey("source", "direction")) {
        const std::string direction = StringUtils::Trim(config.GetString("source", "direction"));
        if (direction == "+x" || direction == "-x" || direction == "+y" || direction == "-y" || direction == "+z" || direction == "-z") {
            const auto d = ParseDirectionVector(direction);
            SetDirection(d[0], d[1], d[2]);
        } else {
            const auto d = ReadVector3Double(config, "source", "direction");
            SetDirection(d[0], d[1], d[2]);
        }
    }

    configured_ = true;
}

void SourceManager::ApplyPreset(const std::string& presetName)
{
    const std::string preset = StringUtils::ToLower(StringUtils::Trim(presetName));
    if (preset.empty()) throw std::runtime_error("SourceManager::ApplyPreset requires non-empty presetName");

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
    configured_ = true;
}

void SourceManager::SetParticle(const std::string& particleName)
{
    const std::string name = StringUtils::Trim(particleName);
    if (name.empty()) throw std::runtime_error("SourceManager::SetParticle requires non-empty particleName");
    G4ParticleDefinition* particle = G4ParticleTable::GetParticleTable()->FindParticle(name);
    if (!particle) throw std::runtime_error("SourceManager::SetParticle unknown particle: '" + name + "'");
    GetGPS()->GetCurrentSource()->SetParticleDefinition(particle);
    particleName_ = name;
    configured_ = true;
}

std::string SourceManager::GetParticleName() const
{
    return particleName_;
}

void SourceManager::SetMonoEnergy(double energy)
{
    if (energy <= 0.0) throw std::runtime_error("SourceManager::SetMonoEnergy requires energy > 0");
    auto* ene = GetGPS()->GetCurrentSource()->GetEneDist();
    ene->SetEnergyDisType("Mono");
    ene->SetMonoEnergy(energy);
    monoEnergy_ = energy;
    configured_ = true;
}

double SourceManager::GetMonoEnergy() const
{
    return monoEnergy_;
}

void SourceManager::SetPosition(const std::string& type, const std::string& shape, const std::vector<double>& params)
{
    auto* pos = GetGPS()->GetCurrentSource()->GetPosDist();
    pos->SetPosDisType(type);
    if (!shape.empty()) pos->SetPosDisShape(shape);
    if (params.size() >= 3) pos->SetCentreCoords(G4ThreeVector(params[0], params[1], params[2]));
    if (params.size() >= 4) pos->SetRadius(params[3]);
    configured_ = true;
}

void SourceManager::SetPointPosition(double x, double y, double z)
{
    auto* pos = GetGPS()->GetCurrentSource()->GetPosDist();
    pos->SetPosDisType("Point");
    pos->SetCentreCoords(G4ThreeVector(x, y, z));
    configured_ = true;
}

void SourceManager::SetDirection(double x, double y, double z)
{
    G4ThreeVector direction(x, y, z);
    if (direction.mag2() <= 0.0) throw std::runtime_error("SourceManager::SetDirection requires non-zero direction vector");
    direction = direction.unit();
    auto* ang = GetGPS()->GetCurrentSource()->GetAngDist();
    ang->SetAngDistType("beam1d");
    ang->SetParticleMomentumDirection(direction);
    configured_ = true;
}

void SourceManager::SetIsotropic()
{
    GetGPS()->GetCurrentSource()->GetAngDist()->SetAngDistType("iso");
    configured_ = true;
}

void SourceManager::SetPlaneBeam(double radius, double z, const std::string& direction)
{
    if (radius <= 0.0) throw std::runtime_error("SourceManager::SetPlaneBeam requires radius > 0");
    auto* pos = GetGPS()->GetCurrentSource()->GetPosDist();
    pos->SetPosDisType("Plane");
    pos->SetPosDisShape("Circle");
    pos->SetRadius(radius);
    pos->SetCentreCoords(G4ThreeVector(0.0, 0.0, z));
    const auto d = ParseDirectionVector(NormalizeDirectionToken(direction));
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
           << ", particle=" << (particleName_.empty() ? "<gps-default>" : particleName_)
           << ", monoEnergy=" << monoEnergy_
           << ", preset=" << (presetName_.empty() ? "<none>" : presetName_)
           << ", verbose=" << verboseLevel_
           << ", gps=" << (gps_ ? "available" : "null")
           << G4endl;
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

void SourceManager::EnsureGPS() const
{
    if (!gps_) gps_ = std::make_unique<G4GeneralParticleSource>();
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
