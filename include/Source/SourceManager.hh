#pragma once

#include <memory>
#include <string>
#include <vector>

class ConfigManager;
class G4GeneralParticleSource;

class SourceManager {
public:
    SourceManager();
    ~SourceManager();

    G4GeneralParticleSource* GetGPS();
    const G4GeneralParticleSource* GetGPS() const;
    bool HasGPS() const;
    void InitializeAfterPhysicsListRegistered();

    void ResetGPS();
    void LoadFromConfig(const ConfigManager& config);
    void ApplyPreset(const std::string& presetName);

    void SetParticle(const std::string& particleName);
    std::string GetParticleName() const;

    void SetMonoEnergy(double energy);
    double GetMonoEnergy() const;

    void SetPosition(const std::string& type, const std::string& shape, const std::vector<double>& params);
    void SetPointPosition(double x, double y, double z);
    void SetDirection(double x, double y, double z);
    void SetIsotropic();
    void SetPlaneBeam(double radius, double z, const std::string& direction = "-z");

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

    void PrintSummary() const;
    bool IsConfigured() const;

    const std::string& GetPresetName() const;

private:
    void EnsureGPS() const;
    void MarkGPSConfigDirty();
    void ApplyCurrentConfigurationToGPS() const;
    void ApplyParticleToGPS() const;
    void ApplyMonoEnergyToGPS() const;
    void ApplyPositionToGPS() const;
    void ApplyAngularDistributionToGPS() const;
    static std::vector<double> ParseDirectionVector(const std::string& text);
    static std::string NormalizeDirectionToken(const std::string& direction);

    mutable std::unique_ptr<G4GeneralParticleSource> gps_;
    mutable bool gpsConfigDirty_ = true;
    std::string particleName_;
    double monoEnergy_ = 0.0;
    std::string presetName_;
    int verboseLevel_ = 0;
    bool configured_ = false;
    bool hasPosition_ = false;
    std::string positionType_;
    std::string positionShape_;
    std::vector<double> positionParams_;
    bool hasDirection_ = false;
    std::vector<double> direction_;
    bool isotropic_ = false;
};
