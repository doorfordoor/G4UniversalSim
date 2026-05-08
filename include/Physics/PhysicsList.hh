#pragma once

#include "G4VModularPhysicsList.hh"

#include <string>

class PhysicsManager;

class PhysicsList : public G4VModularPhysicsList {
public:
    explicit PhysicsList(PhysicsManager* manager = nullptr);
    ~PhysicsList() override;

    void SetPhysicsManager(PhysicsManager* manager);
    PhysicsManager* GetPhysicsManager();
    const PhysicsManager* GetPhysicsManager() const;

    void ConstructParticle() override;
    void ConstructProcess() override;
    void SetCuts() override;

    void ConfigureFromManager();
    void ConfigureEMPhysics();
    void ConfigureExtraPhysicsModules();
    void ConfigureBiasingPhysics();

    void SetDefaultCutValue(double cut);
    void SetParticleCut(const std::string& particleName, double cut);

private:
    PhysicsManager* manager_ = nullptr; // not owned
    bool configured_ = false;
};
