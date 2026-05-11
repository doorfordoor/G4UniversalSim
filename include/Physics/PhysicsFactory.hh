#pragma once

#include <memory>
#include <map>
#include <string>
#include <vector>

class G4VModularPhysicsList;
class G4VPhysicsConstructor;
class PhysicsManager;

enum class PhysicsCategory {
    EM,
    Hadronic,
    Elastic,
    Ion,
    Decay,
    Stopping,
    Optical,
    Biasing,
    Other,
    Unknown
};

class PhysicsFactory {
public:
    static std::string NormalizeOptionName(const std::string& option);
    static PhysicsCategory Classify(const std::string& canonicalName);
    static bool IsKnownOption(const std::string& option);

    static std::unique_ptr<G4VPhysicsConstructor>
    CreatePhysicsConstructor(const std::string& option);
    static std::unique_ptr<G4VPhysicsConstructor>
    CreateMicroElecPhysics(const PhysicsManager& manager);
    static std::unique_ptr<G4VPhysicsConstructor>
    CreateGenericBiasingPhysics(const std::vector<std::string>& particleNames);
    static std::unique_ptr<G4VPhysicsConstructor>
    CreateGenericBiasingPhysics(const std::map<std::string, std::vector<std::string>>& particleProcesses);

    static std::vector<std::string> AvailableAliases();

    static bool IsKnownReferenceList(const std::string& referenceName);
    static std::vector<std::string> AvailableReferenceLists();
    static std::vector<std::string> AvailableReferenceListsEM();

    static std::unique_ptr<G4VModularPhysicsList>
    CreateReferencePhysicsList(const std::string& referenceName);

    static void RegisterExtraModule(G4VModularPhysicsList* list,
                                    const std::string& option);
    static void RegisterExtraModules(G4VModularPhysicsList* list,
                                     const std::vector<std::string>& options);
    static void RegisterGenericBiasingPhysics(
        G4VModularPhysicsList* list,
        const std::map<std::string, std::vector<std::string>>& particleProcesses);

    static std::string StripEMSuffix(const std::string& referenceName);
    static std::string ApplyEMSuffixToReference(const std::string& baseReference,
                                                const std::string& emOption);
    static std::string NormalizeEMOptionForReference(const std::string& emOption);

    static void ApplyCuts(G4VModularPhysicsList* list,
                          double defaultCut,
                          const std::map<std::string, double>& particleCuts);
};
