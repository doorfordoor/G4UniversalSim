#pragma once

#include "Biasing/BiasingConfig.hh"
#include "Config/EffectiveConfigSupport.hh"
#include "G4Cache.hh"

#include <cstddef>
#include <memory>
#include <map>
#include <mutex>
#include <set>
#include <string>
#include <vector>

class ConfigManager;
class GeometryRegistry;
class BiasingMultiParticleXS;
class G4LogicalVolume;

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
    std::size_t GetCommandFailureCount() const;
    const std::string& GetLastCommandFailure() const;
    void RecordCommandFailure(const std::string& message);
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
    std::vector<effective_config::Field> ExportEffectiveConfigFields() const;
    effective_config::Value ExportEffectiveConfigEvidence() const;
    void ConfirmEffectiveConfigMutation(const std::string&, effective_config::Origin);
    void ConfirmEffectiveConfigDerived(const std::string& reason, effective_config::Origin);
    static std::string EffectiveRuleIdentity(const std::string& particle, const std::string& process);

    void AttachOperators(const GeometryRegistry& registry);
    void ClearOperators();
    bool AreOperatorsAttached() const;
    std::size_t GetAttachedOperatorCount() const;
    void ValidateActiveProcessRules();
    std::size_t GetMatchedProcessRuleCount() const;

    struct WorkerEvidence {
        int runId = -1;
        int threadId = -1;
        std::size_t operators = 0;
        std::size_t matchedRules = 0;
        bool tlsVerified = false;
        bool endRunCompleted = false;
        unsigned long long proposals = 0;
        unsigned long long applied = 0;
        std::string failure;
    };
    // Only constructs worker-owned state. Never mutates master operators/config.
    // Initialization failures are latched, then rejected at BeginThreadRun.
    void ConstructThreadOperators(const GeometryRegistry& registry) const;
    void BeginThreadRun(int runId) const;
    void EndThreadRun(int runId) const;
    std::vector<WorkerEvidence> GetWorkerEvidence() const;

private:
    static std::string NormalizeParticleName(const std::string& particleName);
    static std::string ProcessRuleKey(const std::string& particleName, const std::string& processName);
    static std::string TrimRequired(const std::string& value, const std::string& label);
    static void AddUnique(std::vector<std::string>& values, const std::string& value);

    std::vector<XSProcessBiasRule> BuildExpandedProcessRules(bool warnLegacy) const;
    void WarnLegacySyntax(const std::string& detail) const;

    std::vector<effective_config::Field> BuildEffectiveConfigFields() const;
    void AcceptEffectiveConfig(const IniReader&);
    void RecordEffectiveWorkerEvidence(const WorkerEvidence&, const std::string& stage) const;
    std::shared_ptr<effective_config::ConsumerState> effectiveState_ = std::make_shared<effective_config::ConsumerState>();
    std::map<std::string, std::vector<std::string>> effectiveRuleSections_;
    BiasingConfig config_;

    // Global volumes are interpreted as shared target volumes for all rules by
    // later AttachOperators/BiasingXS code; GetBiasVolumes() returns their union
    // with rule-local volumeNames.
    std::vector<std::string> globalBiasVolumes_;
    std::vector<std::unique_ptr<BiasingMultiParticleXS>> xsOperators_;
    struct Attachment {
        G4LogicalVolume* logical = nullptr;
        std::vector<XSProcessBiasRule> rules;
    };
    struct ThreadState;
    std::vector<Attachment> attachmentPlan_; // frozen before worker creation
    mutable G4Cache<ThreadState*> threadState_;
    mutable std::mutex evidenceMutex_;
    mutable std::map<std::pair<int, int>, WorkerEvidence> workerEvidence_;
    mutable std::string firstConstructionFailure_;
    bool operatorsAttached_ = false;
    bool interactiveSessionMode_ = false;
    std::size_t interactiveRejectCount_ = 0;
    std::string lastInteractiveReject_;
    std::size_t commandFailureCount_ = 0;
    std::string lastCommandFailure_;
    std::size_t matchedProcessRuleCount_ = 0;
    mutable bool legacyWarningEmitted_ = false;
    mutable std::set<std::string> legacyDetailWarnings_;
};
