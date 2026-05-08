#pragma once

#include "Biasing/BiasingConfig.hh"

#include <cstddef>
#include <memory>
#include <string>
#include <vector>

class ConfigManager;
class GeometryRegistry;
class BiasingMultiParticleXS;

class BiasingManager {
public:
    BiasingManager();
    ~BiasingManager();

    void Enable(bool enable);
    bool IsEnabled() const;

    void Clear();

    void AddXSBiasRule(const XSBiasRule& rule);
    XSBiasRule& CreateOrGetXSBiasRule(const std::string& particleName);

    void AddXSBiasParticle(const std::string& particleName);
    void AddXSBiasProcess(const std::string& particleName, const std::string& processName);
    void AddXSBiasProcess(const std::string& processName);

    void SetXSBiasFactor(const std::string& particleName, double factor);
    void SetOnlyPrimary(const std::string& particleName, bool onlyPrimary);
    void SetApplyToSecondaries(const std::string& particleName, bool applyToSecondaries);
    void SetMinWeight(const std::string& particleName, double minWeight);
    void SetMaxInteractions(const std::string& particleName, int maxInteractions);

    void AddBiasVolume(const std::string& volumeName);
    void AddBiasVolumeForParticle(const std::string& particleName, const std::string& volumeName);

    bool HasXSBiasRule(const std::string& particleName) const;
    const XSBiasRule& GetXSBiasRule(const std::string& particleName) const;
    XSBiasRule& GetXSBiasRuleMutable(const std::string& particleName);

    const std::vector<XSBiasRule>& GetXSBiasRules() const;
    std::vector<XSBiasRule> GetEnabledXSBiasRules() const;
    std::vector<std::string> GetBiasedParticles() const;
    std::vector<std::string> GetBiasedProcesses(const std::string& particleName) const;
    std::vector<std::string> GetBiasVolumes() const;

    void Validate() const;
    void PrintSummary() const;
    void LoadFromConfig(const ConfigManager& config);

    void AttachOperators(const GeometryRegistry& registry);
    void ClearOperators();
    bool AreOperatorsAttached() const;
    std::size_t GetAttachedOperatorCount() const;

private:
    static std::string NormalizeParticleName(const std::string& particleName);
    static std::string TrimRequired(const std::string& value, const std::string& label);
    static void AddUnique(std::vector<std::string>& values, const std::string& value);

    BiasingConfig config_;

    // Global volumes are interpreted as shared target volumes for all rules by
    // later AttachOperators/BiasingXS code; GetBiasVolumes() returns their union
    // with rule-local volumeNames.
    std::vector<std::string> globalBiasVolumes_;
    std::vector<std::unique_ptr<BiasingMultiParticleXS>> xsOperators_;
    bool operatorsAttached_ = false;
};
