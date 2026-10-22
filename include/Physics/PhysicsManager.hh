#pragma once

#include "Physics/RegionPhysics.hh"

#include <map>
#include <string>
#include <vector>

class BiasingManager;
class ConfigManager;

class PhysicsManager {
public:
    PhysicsManager();
    ~PhysicsManager();

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

    void SetEMOption(const std::string& option);
    std::string GetEMOption() const;

    void SetReferenceList(const std::string& referenceName);
    const std::string& GetReferenceList() const;
    bool HasReferenceList() const;
    void ClearReferenceList();

    void SetBaseReferenceList(const std::string& baseName);
    const std::string& GetBaseReferenceList() const;

    void SetRequestedEMOption(const std::string& option);
    const std::string& GetRequestedEMOption() const;

    bool IsReferenceMode() const;
    bool IsManualMode() const;

    void AddExtraModule(const std::string& option);
    void RemoveExtraModule(const std::string& option);
    void ClearExtraModules();
    bool HasExtraModule(const std::string& option) const;
    std::vector<std::string> GetExtraModules() const;

    void SetReferenceEMOption(const std::string& emOption);
    std::string BuildReferenceNameWithEM(const std::string& baseReference,
                                         const std::string& emOption) const;

    void AddPhysicsModule(const std::string& option);
    void RemovePhysicsModule(const std::string& option);
    void ClearPhysicsModules();

    void AddHadronicOption(const std::string& option);
    void AddOtherOption(const std::string& option);

    bool HasPhysicsModule(const std::string& option) const;
    std::vector<std::string> GetPhysicsModules() const;

    void SetDefaultCut(double cut);
    double GetDefaultCut() const;

    void SetParticleCut(const std::string& particleName, double cut);
    bool HasParticleCut(const std::string& particleName) const;
    double GetParticleCut(const std::string& particleName) const;
    const std::map<std::string, double>& GetParticleCuts() const;

    void SetRegionCut(const std::string& regionName,
                      const std::string& particleName,
                      double cut);
    bool HasRegionCuts() const;
    const std::map<std::string, std::map<std::string, double>>& GetRegionCuts() const;

    // Roadmap A6: production cuts, step limits and user special cuts per
    // G4Region; applied by GeometryManager after the world is built.
    void SetRegionPhysics(const std::string& regionName, const RegionPhysicsSettings& settings);
    const std::map<std::string, RegionPhysicsSettings>& GetRegionPhysics() const;
    bool NeedsStepLimiter() const;

    // Roadmap A6: radioactive decay. enabled registers G4RadioactiveDecayPhysics
    // unless the list already has it; the time threshold (Geant4 >= 11.2
    // default 1 year) decides which long-lived nuclides still decay.
    void EnableRadioactiveDecay(bool enable);
    bool IsRadioactiveDecayEnabled() const;
    void SetRadioactiveDecayTimeThreshold(double time);
    bool HasRadioactiveDecayTimeThreshold() const;
    double GetRadioactiveDecayTimeThreshold() const;

    void SetBiasingManager(BiasingManager* biasingManager);
    BiasingManager* GetBiasingManager();
    const BiasingManager* GetBiasingManager() const;

    void EnableBiasingPhysics(bool enable);
    bool IsBiasingPhysicsEnabled() const;

    void EnableMicroElec(bool enable);
    bool IsMicroElecEnabled() const;

    void SetMicroElecRegion(const std::string& regionName);
    const std::string& GetMicroElecRegion() const;

    void EnableElectronCapture(bool enable);
    bool IsElectronCaptureEnabled() const;

    void SetElectronCaptureThreshold(double threshold);
    double GetElectronCaptureThreshold() const;

    void LoadFromConfig(const ConfigManager& config);

    void Validate() const;
    void PrintSummary() const;

private:
    static std::string NormalizeParticleName(const std::string& particleName);
    static void AddUnique(std::vector<std::string>& values, const std::string& value);

    int verboseLevel_ = 0;
    std::string emOption_ = "G4EmStandardPhysics_option4";
    std::vector<std::string> modules_;
    std::string referenceListName_;
    std::string baseReferenceListName_;
    std::string requestedEMOption_;
    std::vector<std::string> extraModules_;
    double defaultCut_ = 1.0; // initialized to 1 mm in .cc constructor
    std::map<std::string, double> particleCuts_;
    std::map<std::string, std::map<std::string, double>> regionCuts_;
    std::map<std::string, RegionPhysicsSettings> regionPhysics_;
    bool radioactiveDecayEnabled_ = false;
    double radioactiveDecayTimeThreshold_ = -1.0;  // < 0: Geant4 default
    BiasingManager* biasingManager_ = nullptr; // not owned
    bool biasingPhysicsEnabled_ = false;
    bool microElecEnabled_ = false;
    std::string microElecRegionName_ = "SV";
    bool electronCaptureEnabled_ = false;
    double electronCaptureThreshold_ = 16.7; // initialized to 16.7 eV in .cc constructor
};
