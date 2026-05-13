#include "Physics/PhysicsList.hh"

#include "Biasing/BiasingManager.hh"
#include "Physics/PhysicsFactory.hh"
#include "Physics/PhysicsManager.hh"

#include "G4GenericBiasingPhysics.hh"
#include "G4Exception.hh"
#include "G4SystemOfUnits.hh"
#include "G4VPhysicsConstructor.hh"

#include <stdexcept>
#include <map>
#include <vector>

namespace {

std::map<std::string, std::vector<std::string>> BuildBiasParticleProcessMap(
    const BiasingManager* biasingManager)
{
    std::map<std::string, std::vector<std::string>> particleProcesses;
    if (!biasingManager) return particleProcesses;

    for (const std::string& particle : biasingManager->GetBiasedParticles()) {
        if (!particle.empty()) {
            particleProcesses[particle] = biasingManager->GetBiasedProcesses(particle);
        }
    }
    return particleProcesses;
}

} // namespace

PhysicsList::PhysicsList(PhysicsManager* manager)
    : manager_(manager)
{
    SetVerboseLevel(manager_ ? manager_->GetVerboseLevel() : 0);
}

PhysicsList::~PhysicsList() = default;

void PhysicsList::SetPhysicsManager(PhysicsManager* manager)
{
    manager_ = manager;
    configured_ = false;
}

PhysicsManager* PhysicsList::GetPhysicsManager()
{
    return manager_;
}

const PhysicsManager* PhysicsList::GetPhysicsManager() const
{
    return manager_;
}

void PhysicsList::ConstructParticle()
{
    ConfigureFromManager();
    G4VModularPhysicsList::ConstructParticle();
}

void PhysicsList::ConstructProcess()
{
    ConfigureFromManager();
    G4VModularPhysicsList::ConstructProcess();
}

void PhysicsList::SetCuts()
{
    const double defaultCut = manager_ ? manager_->GetDefaultCut() : 1.0 * CLHEP::mm;
    SetDefaultCutValue(defaultCut);
    SetCutsWithDefault();

    if (manager_) {
        for (const auto& item : manager_->GetParticleCuts()) {
            SetParticleCut(item.first, item.second);
        }
        // Region-specific cuts may already be applied by VolumeBuilder-created
        // G4Region/G4ProductionCuts. PhysicsManager keeps a copy for later
        // policy unification and diagnostics.
    }
}

void PhysicsList::ConfigureFromManager()
{
    if (configured_) return;
    if (manager_ && manager_->HasReferenceList()) {
        throw std::runtime_error(
            "PhysicsList manual wrapper cannot configure reference mode; use PhysicsFactory::CreateReferencePhysicsList through SimulationManager.");
    }
    if (manager_) manager_->Validate();

    ConfigureEMPhysics();
    ConfigureExtraPhysicsModules();
    ConfigureBiasingPhysics();
    configured_ = true;
}

void PhysicsList::ConfigureEMPhysics()
{
    const auto option = manager_ ? manager_->GetEMOption()
                                 : std::string("G4EmStandardPhysics_option4");
    auto physics = PhysicsFactory::CreatePhysicsConstructor(option);
    RegisterPhysics(physics.release());
}

void PhysicsList::ConfigureExtraPhysicsModules()
{
    const std::vector<std::string> modules =
        manager_ ? manager_->GetPhysicsModules()
                 : std::vector<std::string>{"G4DecayPhysics"};

    bool microElecRegistered = false;
    for (const auto& module : modules) {
        if (PhysicsFactory::Classify(module) == PhysicsCategory::EM) continue;
        if (PhysicsFactory::Classify(module) == PhysicsCategory::Biasing) continue;
        auto physics = (PhysicsFactory::NormalizeOptionName(module) == "MicroElecPhysics" && manager_)
            ? PhysicsFactory::CreateMicroElecPhysics(*manager_)
            : PhysicsFactory::CreatePhysicsConstructor(module);
        if (PhysicsFactory::NormalizeOptionName(module) == "MicroElecPhysics") {
            microElecRegistered = true;
        }
        RegisterPhysics(physics.release());
    }

    if (manager_ && manager_->IsMicroElecEnabled() && !microElecRegistered) {
        auto physics = PhysicsFactory::CreateMicroElecPhysics(*manager_);
        RegisterPhysics(physics.release());
    }
}

void PhysicsList::ConfigureBiasingPhysics()
{
    const bool explicitEnabled = manager_ && manager_->IsBiasingPhysicsEnabled();
    const auto* biasingManager = manager_ ? manager_->GetBiasingManager() : nullptr;
    const bool managerEnabled = biasingManager && biasingManager->IsEnabled();
    if (!explicitEnabled && !managerEnabled) return;

    const auto particleProcesses = BuildBiasParticleProcessMap(biasingManager);
    if (particleProcesses.empty()) {
        G4Exception(
            "PhysicsList::ConfigureBiasingPhysics",
            "AIHLPhysicsBiasing001",
            JustWarning,
            "Biasing physics was requested, but no biased particles are configured. G4GenericBiasingPhysics was not registered.");
        return;
    }

    auto biasing = PhysicsFactory::CreateGenericBiasingPhysics(particleProcesses);
    RegisterPhysics(biasing.release());
}

void PhysicsList::SetDefaultCutValue(double cut)
{
    if (cut <= 0.0) {
        throw std::runtime_error("PhysicsList::SetDefaultCutValue failed: cut must be > 0");
    }
    G4VUserPhysicsList::SetDefaultCutValue(cut);
}

void PhysicsList::SetParticleCut(const std::string& particleName, double cut)
{
    if (cut <= 0.0) {
        throw std::runtime_error("PhysicsList::SetParticleCut failed for particle '" +
                                 particleName + "': cut must be > 0");
    }
    SetCutValue(cut, particleName);
}
