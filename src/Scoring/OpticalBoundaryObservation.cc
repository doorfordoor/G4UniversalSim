#include "Scoring/OpticalBoundaryObservation.hh"

#include "Scoring/NumericChecks.hh"

#include "G4EventManager.hh"
#include "G4Material.hh"
#include "G4OpBoundaryProcess.hh"
#include "G4ParallelWorldProcess.hh"
#include "G4ParticleDefinition.hh"
#include "G4ProcessManager.hh"
#include "G4ProcessVector.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh"
#include "G4SteppingManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4TouchableHandle.hh"
#include "G4Track.hh"
#include "G4TrackingManager.hh"
#include "G4VPhysicalVolume.hh"

#include <stdexcept>
#include <typeinfo>

namespace {

const G4OpBoundaryProcess& ConfirmCurrentBoundary(const G4Step& step)
{
    const auto* track = step.GetTrack();
    const auto* manager = track->GetParticleDefinition()->GetProcessManager();
    const auto* processes = manager ? manager->GetProcessList() : nullptr;
    G4OpBoundaryProcess* boundary = nullptr;
    if (processes) {
        for (std::size_t index = 0; index < processes->size(); ++index) {
            auto* process = dynamic_cast<G4OpBoundaryProcess*>((*processes)[static_cast<G4int>(index)]);
            if (!process) continue;
            if (boundary) throw std::runtime_error("Multiple optical boundary processes in the worker process manager");
            boundary = process;
        }
    }
    if (!boundary || typeid(*boundary) != typeid(G4OpBoundaryProcess) ||
        !manager->GetProcessActivation(boundary)) {
        throw std::runtime_error("No unique active native G4OpBoundaryProcess in the worker process manager");
    }
    auto* eventManager = G4EventManager::GetEventManager();
    const auto* tracking = eventManager ? eventManager->GetTrackingManager() : nullptr;
    auto* stepping = tracking ? tracking->GetSteppingManager() : nullptr;
    const auto* postDoIt = manager->GetPostStepProcessVector(typeDoIt);
    if (!stepping || stepping->GetfStep() != &step || stepping->GetfTrack() != track ||
        stepping->GetfStepStatus() != fGeomBoundary || !postDoIt ||
        stepping->GetfPostStepDoItVector() != postDoIt || stepping->GetfCurrentProcess() != boundary) {
        throw std::runtime_error("Cannot confirm that the native optical boundary process completed this mass-geometry step");
    }
    const auto* selected = stepping->GetfSelectedPostStepDoItVector();
    const auto slots = stepping->GetMAXofPostStepLoops();
    if (selected && slots == postDoIt->size() && slots <= selected->size()) {
        for (std::size_t index = 0; index < slots; ++index) {
            // Geant4 stores GPIL selection in the reverse order of PostStepDoIt.
            if ((*postDoIt)[static_cast<G4int>(index)] == boundary && (*selected)[slots - 1 - index] == Forced)
                return *boundary;
        }
    }
    throw std::runtime_error("Native optical boundary process has no forced PostStepDoIt slot on this step");
}

const char* NativeStatusName(G4OpBoundaryProcessStatus status)
{
    switch (status) {
    case Transmission: return "Transmission";
    case FresnelRefraction: return "FresnelRefraction";
    case FresnelReflection: return "FresnelReflection";
    case TotalInternalReflection: return "TotalInternalReflection";
    case SameMaterial: return "SameMaterial";
    case StepTooSmall: return "StepTooSmall";
    case Detection: return "Detection";
    case Absorption: return "Absorption";
    case NoRINDEX: return "NoRINDEX";
    case Undefined:
    case NotAtBoundary:
        throw std::runtime_error("Native optical boundary status does not describe the current geometry boundary");
    default: return "UnclassifiedNativeStatus";
    }
}

std::string TouchablePath(const G4StepPoint& point)
{
    const auto& touchable = point.GetTouchableHandle();
    if (!touchable || !touchable->GetVolume())
        throw std::runtime_error("Missing mass-geometry optical boundary touchable");
    std::string path;
    for (int depth = touchable->GetHistoryDepth(); depth >= 0; --depth) {
        const auto* volume = touchable->GetVolume(depth);
        if (!volume) throw std::runtime_error("Incomplete mass-geometry optical boundary touchable path");
        path += '/';
        for (char character : volume->GetName()) {
            switch (character) {
            case '%': path += "%25"; break;
            case '#': path += "%23"; break;
            case '/': path += "%2F"; break;
            default: path += character; break;
            }
        }
        path += '#';
        path += std::to_string(touchable->GetCopyNumber(depth));
    }
    return path;
}

std::array<double, 3> Components(const G4ThreeVector& vector, double unit)
{
    return {ScoringNumeric::Finite(vector.x() / unit, "optical boundary vector x"),
            ScoringNumeric::Finite(vector.y() / unit, "optical boundary vector y"),
            ScoringNumeric::Finite(vector.z() / unit, "optical boundary vector z")};
}

}  // namespace

namespace optical_boundary {

std::optional<OpticalBoundaryStepRecord> ObserveStep(const G4Step& step, int runID, int eventID)
{
    if (G4ParallelWorldProcess::GetHyperStep())
        throw std::runtime_error("Optical boundary observations do not support a parallel-world hyperstep");
    const auto* post = step.GetPostStepPoint();
    if (!post || post->GetStepStatus() != fGeomBoundary) return std::nullopt;
    const auto* pre = step.GetPreStepPoint();
    const auto* track = step.GetTrack();
    if (!pre || !pre->GetMaterial() || !post->GetMaterial() ||
        runID < 0 || eventID < 0 || track->GetTrackID() <= 0 || track->GetCurrentStepNumber() <= 0) {
        throw std::runtime_error("Incomplete mass-geometry optical boundary step");
    }
    // In native mass geometry, transportation executes before the boundary
    // process. Requiring that boundary be the worker's last DoIt rejects an
    // earlier kill or a later callback with ambiguous state.
    const auto status = ConfirmCurrentBoundary(step).GetStatus();
    return OpticalBoundaryStepRecord{
        runID, eventID, track->GetTrackID(), track->GetParentID(), track->GetCurrentStepNumber(),
        TouchablePath(*pre), TouchablePath(*post),
        pre->GetMaterial()->GetName(), post->GetMaterial()->GetName(),
        Components(post->GetPosition(), mm),
        ScoringNumeric::Finite(step.GetStepLength() / mm, "optical boundary step length"),
        ScoringNumeric::Finite(pre->GetKineticEnergy() / MeV, "optical boundary pre-step kinetic energy"),
        ScoringNumeric::Finite(post->GetKineticEnergy() / MeV, "optical boundary post-step kinetic energy"),
        Components(pre->GetMomentumDirection(), 1.0), Components(post->GetMomentumDirection(), 1.0),
        Components(pre->GetPolarization(), 1.0), Components(post->GetPolarization(), 1.0),
        static_cast<int>(status), NativeStatusName(status)
    };
}

}  // namespace optical_boundary
