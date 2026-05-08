#include "Source/PrimaryGeneratorAction.hh"

#include "Source/SourceManager.hh"

#include "G4Event.hh"
#include "G4Exception.hh"
#include "G4GeneralParticleSource.hh"

#include <memory>
#include <stdexcept>

PrimaryGeneratorAction::PrimaryGeneratorAction(SourceManager* sourceManager)
    : sourceManager_(sourceManager),
      ownedGPS_(std::make_unique<G4GeneralParticleSource>())
{
}

PrimaryGeneratorAction::~PrimaryGeneratorAction() = default;

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event)
{
    if (!event) {
        throw std::runtime_error(
            "PrimaryGeneratorAction::GeneratePrimaries failed: G4Event is null");
    }

    auto* gps = GetGPS();
    if (!gps) {
        throw std::runtime_error(
            "PrimaryGeneratorAction::GeneratePrimaries failed: G4GeneralParticleSource is null");
    }

    gps->GeneratePrimaryVertex(event);
}

void PrimaryGeneratorAction::SetSourceManager(SourceManager* sourceManager)
{
    sourceManager_ = sourceManager;
}

SourceManager* PrimaryGeneratorAction::GetSourceManager()
{
    return sourceManager_;
}

const SourceManager* PrimaryGeneratorAction::GetSourceManager() const
{
    return sourceManager_;
}

G4GeneralParticleSource* PrimaryGeneratorAction::GetGPS()
{
    if (sourceManager_) {
        return sourceManager_->GetGPS();
    }
    return ownedGPS_.get();
}

const G4GeneralParticleSource* PrimaryGeneratorAction::GetGPS() const
{
    if (sourceManager_) {
        return sourceManager_->GetGPS();
    }
    return ownedGPS_.get();
}
