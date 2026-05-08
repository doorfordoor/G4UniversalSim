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
{
}

SourceManager::~SourceManager() = default;

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

void SourceManager::ResetGPS()
{
    gps_.reset();
    particleName_.clear();
    monoEnergy_ = 0.0;
    presetName_.clear();
    hasPosition_ = false;
    positionType_.clear();
    positionShape_.clear();
    positionParams_.clear();
    hasDirection_ = false;
    direction_.clear();
    isotropic_ = false;
    MarkGPSConfigDirty();
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
    particleName_ = name;
    MarkGPSConfigDirty();
    if (gps_) ApplyParticleToGPS();
    configured_ = true;
}

std::string SourceManager::GetParticleName() const
{
    return particleName_;
}

void SourceManager::SetMonoEnergy(double energy)
{
    if (energy <= 0.0) throw std::runtime_error("SourceManager::SetMonoEnergy requires energy > 0");
    monoEnergy_ = energy;
    MarkGPSConfigDirty();
    if (gps_) ApplyMonoEnergyToGPS();
    configured_ = true;
}

double SourceManager::GetMonoEnergy() const
{
    return monoEnergy_;
}

void SourceManager::SetPosition(const std::string& type, const std::string& shape, const std::vector<double>& params)
{
    positionType_ = type;
    positionShape_ = shape;
    positionParams_ = params;
    hasPosition_ = true;
    MarkGPSConfigDirty();
    if (gps_) ApplyPositionToGPS();
    configured_ = true;
}

void SourceManager::SetPointPosition(double x, double y, double z)
{
    SetPosition("Point", "", {x, y, z});
}

void SourceManager::SetDirection(double x, double y, double z)
{
    const double mag2 = x * x + y * y + z * z;
    if (mag2 <= 0.0) throw std::runtime_error("SourceManager::SetDirection requires non-zero direction vector");
    const double invMag = 1.0 / std::sqrt(mag2);
    direction_ = {x * invMag, y * invMag, z * invMag};
    hasDirection_ = true;
    isotropic_ = false;
    MarkGPSConfigDirty();
    if (gps_) ApplyAngularDistributionToGPS();
    configured_ = true;
}

void SourceManager::SetIsotropic()
{
    isotropic_ = true;
    hasDirection_ = false;
    direction_.clear();
    MarkGPSConfigDirty();
    if (gps_) ApplyAngularDistributionToGPS();
    configured_ = true;
}

void SourceManager::SetPlaneBeam(double radius, double z, const std::string& direction)
{
    if (radius <= 0.0) throw std::runtime_error("SourceManager::SetPlaneBeam requires radius > 0");
    SetPosition("Plane", "Circle", {0.0, 0.0, z, radius});
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
           << ", gps=" << (gps_ ? "available" : "lazy")
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
    if (!gps_) {
        gps_ = std::make_unique<G4GeneralParticleSource>();
        gpsConfigDirty_ = true;
    }
}

void SourceManager::MarkGPSConfigDirty()
{
    gpsConfigDirty_ = true;
}

void SourceManager::ApplyCurrentConfigurationToGPS() const
{
    if (!gps_ || !gpsConfigDirty_) return;
    ApplyParticleToGPS();
    ApplyMonoEnergyToGPS();
    ApplyPositionToGPS();
    ApplyAngularDistributionToGPS();
    gpsConfigDirty_ = false;
}

void SourceManager::ApplyParticleToGPS() const
{
    if (!gps_ || StringUtils::Trim(particleName_).empty()) return;
    G4ParticleDefinition* particle = G4ParticleTable::GetParticleTable()->FindParticle(particleName_);
    if (!particle) throw std::runtime_error("SourceManager::SetParticle unknown particle: '" + particleName_ + "'");
    gps_->GetCurrentSource()->SetParticleDefinition(particle);
}

void SourceManager::ApplyMonoEnergyToGPS() const
{
    if (!gps_ || monoEnergy_ <= 0.0) return;
    auto* ene = gps_->GetCurrentSource()->GetEneDist();
    ene->SetEnergyDisType("Mono");
    ene->SetMonoEnergy(monoEnergy_);
}

void SourceManager::ApplyPositionToGPS() const
{
    if (!gps_ || !hasPosition_) return;
    auto* pos = gps_->GetCurrentSource()->GetPosDist();
    pos->SetPosDisType(positionType_);
    if (!positionShape_.empty()) pos->SetPosDisShape(positionShape_);
    if (positionParams_.size() >= 3) {
        pos->SetCentreCoords(G4ThreeVector(positionParams_[0], positionParams_[1], positionParams_[2]));
    }
    if (positionParams_.size() >= 4) pos->SetRadius(positionParams_[3]);
}

void SourceManager::ApplyAngularDistributionToGPS() const
{
    if (!gps_) return;
    auto* ang = gps_->GetCurrentSource()->GetAngDist();
    if (isotropic_) {
        ang->SetAngDistType("iso");
        return;
    }
    if (hasDirection_ && direction_.size() == 3) {
        ang->SetAngDistType("beam1d");
        ang->SetParticleMomentumDirection(G4ThreeVector(direction_[0], direction_[1], direction_[2]));
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
