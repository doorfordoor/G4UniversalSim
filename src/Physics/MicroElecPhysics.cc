#include "Physics/MicroElecPhysics.hh"

#include "Physics/ElectronCapture.hh"

#include "G4Electron.hh"
#include "G4EmParameters.hh"
#include "G4Exception.hh"
#include "G4Gamma.hh"
#include "G4GenericIon.hh"
#include "G4ParticleDefinition.hh"
#include "G4Positron.hh"
#include "G4ProcessManager.hh"
#include "G4Proton.hh"
#include "G4RegionStore.hh"
#include "G4SystemOfUnits.hh"
#include "G4ios.hh"

#include <stdexcept>

MicroElecPhysics::MicroElecPhysics(G4int verbose,
                                   const G4String& regionName,
                                   const G4String& name)
    : G4VPhysicsConstructor(name),
      regionName_(regionName),
      verboseLevel_(verbose)
{
}

MicroElecPhysics::~MicroElecPhysics() = default;

void MicroElecPhysics::ConstructParticle()
{
    G4Gamma::GammaDefinition();
    G4Electron::ElectronDefinition();
    G4Positron::PositronDefinition();
    G4Proton::ProtonDefinition();
    G4GenericIon::GenericIonDefinition();
}

void MicroElecPhysics::ConstructProcess()
{
    ConfigureAtomicDeexcitation();
    WarnIfRegionMissing();

    G4Exception(
        "MicroElecPhysics::ConstructProcess",
        "AIHL_MICROELEC_001",
        JustWarning,
        "Portable MicroElecPhysics extension is active, but no Geant4 MicroElec/DNA EM models are globally installed. Existing reference/manual EM physics is preserved; only atomic deexcitation and optional ElectronCapture are configured.");

    if (electronCaptureEnabled_) {
        RegisterElectronCaptureProcess();
    }
}

void MicroElecPhysics::SetRegionName(const G4String& regionName)
{
    regionName_ = regionName;
}

const G4String& MicroElecPhysics::GetRegionName() const
{
    return regionName_;
}

void MicroElecPhysics::SetVerboseLevel(G4int verbose)
{
    if (verbose < 0) {
        throw std::runtime_error("MicroElecPhysics::SetVerboseLevel requires verbose >= 0");
    }
    verboseLevel_ = verbose;
}

G4int MicroElecPhysics::GetVerboseLevel() const
{
    return verboseLevel_;
}

void MicroElecPhysics::EnableElectronCapture(bool enable)
{
    electronCaptureEnabled_ = enable;
}

bool MicroElecPhysics::IsElectronCaptureEnabled() const
{
    return electronCaptureEnabled_;
}

void MicroElecPhysics::SetElectronCaptureThreshold(G4double energy)
{
    if (energy <= 0.0) {
        throw std::runtime_error("MicroElecPhysics::SetElectronCaptureThreshold requires energy > 0");
    }
    electronCaptureThreshold_ = energy;
}

G4double MicroElecPhysics::GetElectronCaptureThreshold() const
{
    return electronCaptureThreshold_;
}

void MicroElecPhysics::ConfigureAtomicDeexcitation() const
{
    auto* parameters = G4EmParameters::Instance();
    if (!parameters) {
        G4Exception("MicroElecPhysics::ConfigureAtomicDeexcitation",
                    "AIHL_MICROELEC_002",
                    JustWarning,
                    "G4EmParameters::Instance returned null; atomic deexcitation parameters were not changed.");
        return;
    }

    parameters->SetFluo(true);
    parameters->SetAuger(true);
    parameters->SetPixe(true);
}

void MicroElecPhysics::RegisterElectronCaptureProcess() const
{
    auto* electron = G4Electron::ElectronDefinition();
    if (!electron) {
        G4Exception("MicroElecPhysics::RegisterElectronCaptureProcess",
                    "AIHL_MICROELEC_003",
                    JustWarning,
                    "Electron definition is not available; ElectronCapture was not registered.");
        return;
    }

    auto* processManager = electron->GetProcessManager();
    if (!processManager) {
        G4Exception("MicroElecPhysics::RegisterElectronCaptureProcess",
                    "AIHL_MICROELEC_004",
                    JustWarning,
                    "Electron process manager is null; ElectronCapture was not registered.");
        return;
    }

    auto* capture = new ElectronCapture("AIHL_eCapture", electronCaptureThreshold_, regionName_);
    processManager->AddDiscreteProcess(capture);

    if (verboseLevel_ > 0) {
        G4cout << "[MicroElecPhysics] Registered ElectronCapture for region='"
               << (regionName_.empty() ? G4String("<all>") : regionName_)
               << "', threshold=" << electronCaptureThreshold_ / eV << " eV" << G4endl;
    }
}

void MicroElecPhysics::WarnIfRegionMissing() const
{
    if (regionName_.empty()) {
        return;
    }

    auto* store = G4RegionStore::GetInstance();
    if (!store) {
        return;
    }

    if (!store->GetRegion(regionName_, false)) {
        const G4String message =
            "Requested MicroElec region '" + regionName_ +
            "' does not exist at physics construction time. This is non-fatal; ElectronCapture will only act if a matching region exists during tracking.";
        G4Exception("MicroElecPhysics::WarnIfRegionMissing",
                    "AIHL_MICROELEC_005",
                    JustWarning,
                    message.c_str());
    }
}
