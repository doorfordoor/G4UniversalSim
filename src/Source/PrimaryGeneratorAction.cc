#include "Source/PrimaryGeneratorAction.hh"

#include "Source/SourceManager.hh"

#include "G4Event.hh"
#include "G4Exception.hh"
#include "G4GeneralParticleSource.hh"
#include "G4PrimaryVertex.hh"
#include "G4PrimaryParticle.hh"
#include "G4ParticleDefinition.hh"
#include "G4RunManager.hh"
#include "G4Run.hh"
#include "G4Threading.hh"
#include "G4SystemOfUnits.hh"

#include <memory>
#include <cstdlib>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <stdexcept>

namespace {
// Test-only observation after generation, before transport. Never substitute
// sensitive-hit coordinates for a primary vertex. The caller owns a fresh path;
// this diagnostic is not a production output/manifest or a physics benchmark.
void ObserveTestPrimaries(const G4Event& event)
{
    const char* path = std::getenv("G4USIM_TEST_PRIMARY_VERTICES");
    if (!path || !*path) return;
    std::ostringstream line;
    line << std::setprecision(17);
    const auto* run = G4RunManager::GetRunManager()->GetCurrentRun();
    for (int v = 0; v < event.GetNumberOfPrimaryVertex(); ++v) {
        const auto* vertex = event.GetPrimaryVertex(v);
        for (const auto* primary = vertex->GetPrimary(); primary; primary = primary->GetNext()) {
            const auto direction = primary->GetMomentumDirection();
            line << "{\"run\":" << (run ? run->GetRunID() : -1)
                 << ",\"thread\":" << G4Threading::G4GetThreadId()
                 << ",\"event\":" << event.GetEventID() << ",\"vertex\":" << v
                 << ",\"vertex_count\":" << event.GetNumberOfPrimaryVertex()
                 << ",\"pdg\":" << primary->GetPDGcode()
                 << ",\"x_mm\":" << vertex->GetX0()/CLHEP::mm
                 << ",\"y_mm\":" << vertex->GetY0()/CLHEP::mm
                 << ",\"z_mm\":" << vertex->GetZ0()/CLHEP::mm
                 << ",\"energy_MeV\":" << primary->GetKineticEnergy()/CLHEP::MeV
                 << ",\"u\":" << direction.x() << ",\"v\":" << direction.y() << ",\"w\":" << direction.z()
                 << ",\"primary_weight\":" << primary->GetWeight()
                 << ",\"vertex_weight\":" << vertex->GetWeight()
                 << ",\"charge_eplus\":" << primary->GetCharge()/CLHEP::eplus << "}\n";
        }
    }
    static std::mutex mutex;
    std::lock_guard<std::mutex> lock(mutex);
    std::ofstream stream(std::filesystem::u8path(path), std::ios::app | std::ios::binary);
    if (!stream) throw std::runtime_error("Cannot open G4USIM_TEST_PRIMARY_VERTICES diagnostic");
    stream << line.str();
    stream.close();
    if (!stream) throw std::runtime_error("Cannot write G4USIM_TEST_PRIMARY_VERTICES diagnostic");
}
} // namespace

PrimaryGeneratorAction::PrimaryGeneratorAction(SourceManager* sourceManager)
    : sourceManager_(sourceManager)
{
}

PrimaryGeneratorAction::~PrimaryGeneratorAction() = default;

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event)
{
    if (!event) {
        throw std::runtime_error(
            "PrimaryGeneratorAction::GeneratePrimaries failed: G4Event is null");
    }

    if (sourceManager_ && sourceManager_->UsesPhaseSpace()) {
        sourceManager_->GeneratePhaseSpaceEvent(event);
        ObserveTestPrimaries(*event);
        return;
    }

    auto* gps = GetGPS();
    if (!gps) {
        throw std::runtime_error(
            "PrimaryGeneratorAction::GeneratePrimaries failed: G4GeneralParticleSource is null");
    }

    gps->GeneratePrimaryVertex(event);
    ObserveTestPrimaries(*event);
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
    if (!ownedGPS_) {
        ownedGPS_ = std::make_unique<G4GeneralParticleSource>();
    }
    return ownedGPS_.get();
}

const G4GeneralParticleSource* PrimaryGeneratorAction::GetGPS() const
{
    if (sourceManager_) {
        return sourceManager_->GetGPS();
    }
    if (!ownedGPS_) {
        ownedGPS_ = std::make_unique<G4GeneralParticleSource>();
    }
    return ownedGPS_.get();
}
