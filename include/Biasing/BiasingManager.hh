#pragma once

#include "Biasing/BiasingConfig.hh"

#include <cstddef>
#include <memory>
#include <set>
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
    void SetInteractiveSessionMode(bool interactive);
    bool IsInteractiveSessionMode() const;
    // A rejected mutation in an interactive session used to be a JustWarning:
    // the command was silently ignored, the session continued and the process
    // still exited 0. Record every rejection so main.cc can stop the session
    // and fail the process instead.
    void RecordInteractiveReject(const std::string& command, const std::string& message);
    std::size_t GetInteractiveRejectCount() const;
    const std::string& GetLastInteractiveReject() const;

    void Clear();

    void AddXSProcessBiasRule(const XSProcessBiasRule& rule);
    XSProcessBiasRule& CreateOrGetXSProcessBiasRule(
        const std::string& particleName,
        const std::string& processName);
    bool HasXSProcessBiasRule(
        const std::string& particleName,
        const std::string& processName) const;
    const XSProcessBiasRule& GetXSProcessBiasRule(
        const std::string& particleName,
        const std::string& processName) const;
    XSProcessBiasRule& GetXSProcessBiasRuleMutable(
        const std::string& particleName,
        const std::string& processName);
    const std::vector<XSProcessBiasRule>& GetXSProcessBiasRules() const;
    std::vector<XSProcessBiasRule> GetEnabledXSProcessBiasRules() const;

    void SetXSProcessBiasFactor(
        const std::string& particleName,
        const std::string& processName,
        double factor);
    void AddXSProcessBiasVolume(
        const std::string& particleName,
        const std::string& processName,
        const std::string& volumeName);
    void SetXSProcessOnlyPrimary(
        const std::string& particleName,
        const std::string& processName,
        bool onlyPrimary);
    void SetXSProcessApplyToSecondaries(
        const std::string& particleName,
        const std::string& processName,
        bool applyToSecondaries);
    void SetXSProcessMinWeight(
        const std::string& particleName,
        const std::string& processName,
        double minWeight);
    void SetXSProcessMaxInteractions(
        const std::string& particleName,
        const std::string& processName,
        int maxInteractions);

    // Legacy particle-level API retained for old macro/config compatibility.
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
    void ValidateActiveProcessRules();
    std::size_t GetMatchedProcessRuleCount() const;

private:
    static std::string NormalizeParticleName(const std::string& particleName);
    static std::string ProcessRuleKey(const std::string& particleName, const std::string& processName);
    static std::string TrimRequired(const std::string& value, const std::string& label);
    static void AddUnique(std::vector<std::string>& values, const std::string& value);

    std::vector<XSProcessBiasRule> BuildExpandedProcessRules(bool warnLegacy) const;
    void WarnLegacySyntax(const std::string& detail) const;

    BiasingConfig config_;

    // Global volumes are interpreted as shared target volumes for all rules by
    // later AttachOperators/BiasingXS code; GetBiasVolumes() returns their union
    // with rule-local volumeNames.
    std::vector<std::string> globalBiasVolumes_;
    std::vector<std::unique_ptr<BiasingMultiParticleXS>> xsOperators_;
    bool operatorsAttached_ = false;
    bool interactiveSessionMode_ = false;
    std::size_t interactiveRejectCount_ = 0;
    std::string lastInteractiveReject_;
    std::size_t matchedProcessRuleCount_ = 0;
    mutable bool legacyWarningEmitted_ = false;
    mutable std::set<std::string> legacyDetailWarnings_;
};
