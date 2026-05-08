#pragma once

#include "G4VUserPrimaryGeneratorAction.hh"

#include <memory>

class G4Event;
class G4GeneralParticleSource;
class SourceManager;

class PrimaryGeneratorAction : public G4VUserPrimaryGeneratorAction {
public:
    explicit PrimaryGeneratorAction(SourceManager* sourceManager = nullptr);
    ~PrimaryGeneratorAction() override;

    void GeneratePrimaries(G4Event* event) override;

    void SetSourceManager(SourceManager* sourceManager);
    SourceManager* GetSourceManager();
    const SourceManager* GetSourceManager() const;

    G4GeneralParticleSource* GetGPS();
    const G4GeneralParticleSource* GetGPS() const;

private:
    SourceManager* sourceManager_ = nullptr; // not owned
    std::unique_ptr<G4GeneralParticleSource> ownedGPS_;
};
