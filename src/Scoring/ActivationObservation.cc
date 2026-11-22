#include "Scoring/ActivationObservation.hh"
#include "Scoring/NumericChecks.hh"

#include "G4CoupledTransportation.hh"
#include "G4Event.hh"
#include "G4HadronicInteraction.hh"
#include "G4HadronicProcess.hh"
#include "G4HadronicProcessType.hh"
#include "G4Ions.hh"
#include "G4Isotope.hh"
#include "G4Nucleus.hh"
#include "G4ParticleTable.hh"
#include "G4PrimaryParticle.hh"
#include "G4PrimaryVertex.hh"
#include "G4ProcessManager.hh"
#include "G4RadioactiveDecay.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh"
#include "G4SystemOfUnits.hh"
#include "G4Track.hh"
#include "G4Transportation.hh"
#include "G4VTouchable.hh"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace {

constexpr int kNeutronPdg = 2112;

const G4Ions* NuclearIon(const G4Track& track)
{
    const auto* particle = track.GetParticleDefinition();
    // The native neutron definition also derives from G4Ions.
    return particle->GetPDGEncoding() == kNeutronPdg ? nullptr : dynamic_cast<const G4Ions*>(particle);
}

void RequireAnalogue(const G4RadioactiveDecay& process)
{
    // Geant4 exposes a non-const readback accessor.
    if (!const_cast<G4RadioactiveDecay&>(process).IsAnalogueMonteCarlo())
        throw std::runtime_error("activation observations require analogue radioactive decay");
}

int ValidateProcesses(const G4ParticleDefinition& particle, double& thresholdSeconds)
{
    auto* manager = particle.GetProcessManager();
    int count = 0;
    if (!manager) return count;
    for (int i = 0; i < manager->GetProcessListLength(); ++i) {
        if (!manager->GetProcessActivation(i)) continue;
        auto* process = dynamic_cast<const G4RadioactiveDecay*>((*manager->GetProcessList())[i]);
        if (!process) continue;
        RequireAnalogue(*process);
        thresholdSeconds = ScoringNumeric::Finite(process->GetThresholdForVeryLongDecayTime() / second,
                                                  "activation radioactive decay threshold");
        if (thresholdSeconds <= 0)
            throw std::runtime_error("activation observations require a positive actual decay threshold");
        ++count;
    }
    return count;
}

ActivationObservationRecord MakeRecord(const G4Track& track, int runID, int eventID,
                                       int stepID, const char* kind, const G4VProcess* process,
                                       const G4ThreeVector& position, double time, double weight)
{
    ActivationObservationRecord record;
    record.runID = runID;
    record.eventID = eventID;
    record.trackID = track.GetTrackID() > 0 ? track.GetTrackID() : -1;
    record.parentID = track.GetParentID();
    record.stepID = stepID;
    record.kind = kind;
    record.process = process ? process->GetProcessName() : "";
    record.particle = track.GetParticleDefinition()->GetParticleName();
    if (const auto* ion = NuclearIon(track)) {
        record.atomicNumber = ion->GetAtomicNumber();
        record.massNumber = ion->GetAtomicMass();
        record.isomer = ion->GetIsomerLevel();
        record.excitationKeV = ScoringNumeric::Finite(ion->GetExcitationEnergy() / keV, "activation excitation energy");
        if (record.atomicNumber <= 0 || record.massNumber < record.atomicNumber ||
            record.isomer < 0 || record.excitationKeV < 0)
            throw std::runtime_error("invalid nuclear identity in activation observation");
    }
    record.timeSeconds = ScoringNumeric::Finite(time / second, "activation global time");
    record.weight = ScoringNumeric::Finite(weight, "activation track weight");
    for (int axis = 0; axis < 3; ++axis)
        record.positionMm[axis] = ScoringNumeric::Finite(position[axis] / mm, "activation position");
    if (record.timeSeconds < 0 || record.weight < 0)
        throw std::runtime_error("negative global time or weight in activation observation");
    return record;
}

bool SameTime(double a, double b)
{
    return std::abs(a - b) <= 8 * std::numeric_limits<double>::epsilon() * std::max(std::abs(a), std::abs(b));
}

const char* StepStatusName(G4StepStatus status)
{
    switch (status) {
    case fWorldBoundary: return "fWorldBoundary";
    case fGeomBoundary: return "fGeomBoundary";
    case fAtRestDoItProc: return "fAtRestDoItProc";
    case fAlongStepDoItProc: return "fAlongStepDoItProc";
    case fPostStepDoItProc: return "fPostStepDoItProc";
    case fUserDefinedLimit: return "fUserDefinedLimit";
    case fExclusivelyForcedProc: return "fExclusivelyForcedProc";
    case fUndefined: return "fUndefined";
    }
    throw std::runtime_error("unrecognized native activation step status");
}

const char* TrackStatusName(G4TrackStatus status)
{
    switch (status) {
    case fAlive: return "fAlive";
    case fStopButAlive: return "fStopButAlive";
    case fStopAndKill: return "fStopAndKill";
    case fKillTrackAndSecondaries: return "fKillTrackAndSecondaries";
    case fSuspend: return "fSuspend";
    case fSuspendAndWait: return "fSuspendAndWait";
    case fPostponeToNextEvent: return "fPostponeToNextEvent";
    }
    throw std::runtime_error("unrecognized native activation track status");
}

void SetClockAndEnergy(ActivationObservationRecord& row, double properTime, double kineticEnergy)
{
    row.properTimeSeconds = ScoringNumeric::Finite(properTime / second, "activation proper time");
    row.kineticEnergyKeV = ScoringNumeric::Finite(kineticEnergy / keV, "activation kinetic energy");
    if (*row.properTimeSeconds < 0 || *row.kineticEnergyKeV < 0)
        throw std::runtime_error("negative proper time or kinetic energy in activation observation");
}

void SetStepEvidence(ActivationObservationRecord& row, const G4Step& step)
{
    const auto& pre = *step.GetPreStepPoint();
    const auto& post = *step.GetPostStepPoint();
    SetClockAndEnergy(row, post.GetProperTime(), post.GetKineticEnergy());
    row.preGlobalTimeSeconds = ScoringNumeric::Finite(pre.GetGlobalTime() / second, "activation pre-step global time");
    row.preProperTimeSeconds = ScoringNumeric::Finite(pre.GetProperTime() / second, "activation pre-step proper time");
    row.preKineticEnergyKeV = ScoringNumeric::Finite(pre.GetKineticEnergy() / keV, "activation pre-step kinetic energy");
    if (*row.preGlobalTimeSeconds < 0 || *row.preProperTimeSeconds < 0 || *row.preKineticEnergyKeV < 0)
        throw std::runtime_error("negative pre-step clock or kinetic energy in activation observation");
    row.postStepStatus = StepStatusName(post.GetStepStatus());
    row.postTrackStatus = TrackStatusName(step.GetTrack()->GetTrackStatus());
}

bool SameCreatorModel(const G4Track& track, const ActivationObservationRecord& birth)
{
    return !birth.creatorModelID || (track.GetCreatorModelID() == *birth.creatorModelID &&
                                    track.GetCreatorModelName() == birth.creatorModelName);
}

const char* TouchableState(const G4VTouchable* touchable)
{
    if (!touchable) return "unavailable";
    return touchable->GetVolume() ? "located" : "null_volume";
}

void SetEndpointEvidence(ActivationObservationRecord& record, const G4Step& step)
{
    const auto* post = step.GetPostStepPoint()->GetTouchable();
    const auto* next = step.GetTrack()->GetNextTouchable();
    const auto* process = step.GetPostStepPoint()->GetProcessDefinedStep();
    record.preMassTouchable = TouchableState(step.GetPreStepPoint()->GetTouchable());
    record.postMassTouchable = TouchableState(post);
    record.trackNextMassTouchable = TouchableState(next);
    record.postTouchableMatchesNext = post && post == next;
    if (dynamic_cast<const G4CoupledTransportation*>(process)) record.endpointTransport = "coupled";
    else if (dynamic_cast<const G4Transportation*>(process)) record.endpointTransport = "standard";
    else record.endpointTransport = "other";
}

void SetCaptureEvidence(ActivationObservationRecord& record, const G4Step& step,
                        const G4HadronicProcess& capture, int creatorMatches)
{
    record.captureCreatorMatches = creatorMatches;
    record.capturePreWeight = ScoringNumeric::Finite(step.GetPreStepPoint()->GetWeight(), "activation capture pre-weight");
    if (*record.capturePreWeight < 0) throw std::runtime_error("negative activation capture pre-weight");
    record.postStepStatus = StepStatusName(step.GetPostStepPoint()->GetStepStatus());
    record.postTrackStatus = TrackStatusName(step.GetTrack()->GetTrackStatus());
    record.captureTargetObservation = "unresolved";
    if (creatorMatches == 0 || step.GetPostStepPoint()->GetStepStatus() != fPostStepDoItProc ||
        step.GetTrack()->GetTrackStatus() != fStopAndKill) return;

    record.captureTargetObservation = "native_getters";
    if (const auto* model = capture.GetHadronicInteraction()) record.captureModel = model->GetModelName();
    if (const auto* nucleus = capture.GetTargetNucleus()) {
        record.captureTargetNucleusZ = nucleus->GetZ_asInt();
        record.captureTargetNucleusA = nucleus->GetA_asInt();
    }
    // This public accessor has no const overload. It only reads the stored isotope.
    if (const auto* isotope = const_cast<G4HadronicProcess&>(capture).GetTargetIsotope()) {
        record.captureTargetIsotopeZ = isotope->GetZ();
        record.captureTargetIsotopeA = isotope->GetN();
    }
}

}  // namespace

namespace activation_observation {

double ValidateRun()
{
    double threshold = 0;
    auto* particles = G4ParticleTable::GetParticleTable();
    const auto* genericIon = particles->FindParticle("GenericIon");
    if (!genericIon || ValidateProcesses(*genericIon, threshold) != 1)
        throw std::runtime_error("activation observations require exactly one active G4RadioactiveDecay on GenericIon");
    double tritonThreshold = 0;
    const auto* triton = particles->FindParticle("triton");
    if (triton && ValidateProcesses(*triton, tritonThreshold) > 1)
        throw std::runtime_error("activation observations found multiple G4RadioactiveDecay processes on triton");
    return threshold;
}

void Event::ObserveStep(const G4Step& step, int runID, int eventID, int schemaVersion)
{
    const bool extended = schemaVersion >= 2;
    const bool nativeEvidence = schemaVersion >= 3;
    const auto& track = *step.GetTrack();
    const int parentID = track.GetTrackID();
    const auto* ion = NuclearIon(track);
    const int stepID = track.GetCurrentStepNumber();
    const auto* pre = step.GetPreStepPoint();
    const auto* post = step.GetPostStepPoint();
    const auto* process = post->GetProcessDefinedStep();
    const auto* decay = dynamic_cast<const G4RadioactiveDecay*>(process);
    const bool neutron = track.GetParticleDefinition()->GetPDGEncoding() == kNeutronPdg;
    const auto* hadronic = neutron ? dynamic_cast<const G4HadronicProcess*>(process) : nullptr;
    const bool capture = hadronic && process->GetProcessType() == fHadronic && process->GetProcessSubType() == fCapture;
    if (nativeEvidence && neutron && track.GetParentID() == 0 && stepID == 1) {
        auto row = MakeRecord(track, runID, eventID, stepID, "primary_neutron_first_step",
                              track.GetCreatorProcess(), pre->GetPosition(), pre->GetGlobalTime(), pre->GetWeight());
        SetClockAndEnergy(row, pre->GetProperTime(), pre->GetKineticEnergy());
        records_.push_back(std::move(row));
    }
    if (ion && stepID == 1) {
        const auto birth = stackedBirths_.find(track.GetTrackID());
        if (track.GetParentID() == 0 || birth != stackedBirths_.end()) {
            auto row = MakeRecord(track, runID, eventID, stepID,
                                  birth == stackedBirths_.end() ? "primary_first_step" : "secondary_first_step",
                                  track.GetCreatorProcess(), pre->GetPosition(), pre->GetGlobalTime(), pre->GetWeight());
            if (birth != stackedBirths_.end()) {
                const auto& source = records_.at(birth->second.rowIndex);
                row.originStepID = source.originStepID;
                row.secondaryOrdinal = source.secondaryOrdinal;
                if (extended && track.GetCreatorProcess() != birth->second.creator)
                    throw std::runtime_error("activation first-step creator process differs from its recorded birth");
                if (extended && source.creatorModelID) {
                    if (!SameCreatorModel(track, source))
                        throw std::runtime_error("activation first-step creator model differs from its recorded birth");
                    row.creatorModelID = track.GetCreatorModelID();
                    row.creatorModelName = track.GetCreatorModelName();
                }
                stackedBirths_.erase(birth);
            }
            if (extended) {
                SetClockAndEnergy(row, pre->GetProperTime(), pre->GetKineticEnergy());
                if (!nuclearLineage_.emplace(parentID, records_.size()).second)
                    throw std::runtime_error("activation nuclear track has multiple first steps");
            }
            records_.push_back(std::move(row));
        }
    }
    const auto lineage = nuclearLineage_.find(parentID);
    if (extended && ion && !decay && lineage != nuclearLineage_.end() &&
        (track.GetTrackStatus() == fStopAndKill || track.GetTrackStatus() == fKillTrackAndSecondaries)) {
        auto endpoint = MakeRecord(track, runID, eventID, stepID, "nuclear_endpoint",
                                   process, post->GetPosition(), post->GetGlobalTime(), post->GetWeight());
        const auto& first = records_.at(lineage->second);
        endpoint.originStepID = first.originStepID;
        endpoint.secondaryOrdinal = first.secondaryOrdinal;
        SetStepEvidence(endpoint, step);
        if (nativeEvidence) SetEndpointEvidence(endpoint, step);
        records_.push_back(std::move(endpoint));
    }
    if (!capture && !decay) return;
    if (decay) {
        RequireAnalogue(*decay);
        if (!ion) throw std::runtime_error("radioactive decay parent has no G4Ions identity");
    }

    const auto* children = step.GetSecondaryInCurrentStep();
    const std::size_t childCount = children ? children->size() : 0;
    if (childCount > static_cast<std::size_t>(std::numeric_limits<int>::max()))
        throw std::runtime_error("activation secondary count exceeds integer range");
    const double parentTime = post->GetGlobalTime();
    const auto parentRow = records_.size();
    auto mother = MakeRecord(track, runID, eventID, stepID, capture ? "neutron_capture" : "rdm_no_creator_secondary",
                             process, post->GetPosition(), parentTime, post->GetWeight());
    if (extended && decay) {
        SetStepEvidence(mother, step);
        if (nativeEvidence) SetEndpointEvidence(mother, step);
        mother.stepSecondaryCount = static_cast<int>(childCount);
        if (lineage != nuclearLineage_.end()) {
            const auto& first = records_.at(lineage->second);
            mother.originStepID = first.originStepID;
            mother.secondaryOrdinal = first.secondaryOrdinal;
        }
    }
    records_.push_back(std::move(mother));
    int excludedSecondaries = 0;
    int decaySecondaries = 0;
    int captureCreatorMatches = 0;
    for (std::size_t i = 0; i < childCount; ++i) {
        const auto* childPointer = (*children)[i];
        if (!childPointer)
            throw std::runtime_error("activation current-step secondary has no native track");
        const auto& child = *childPointer;
        const auto* creator = child.GetCreatorProcess();
        const bool sameCreator = creator == process;
        if (!sameCreator && (!extended || !decay)) continue;
        if (nativeEvidence && capture) ++captureCreatorMatches;
        if (decay && sameCreator &&
            (!std::isfinite(child.GetGlobalTime()) || !SameTime(parentTime, child.GetGlobalTime())))
            throw std::runtime_error("activation decay daughter global time differs from post-step parent time");
        const bool nuclearChild = NuclearIon(child) != nullptr;
        if (capture && !nuclearChild) continue;
        const char* kind = capture ? "capture_ion" : (sameCreator ? "rdm_secondary" : "rdm_excluded_secondary");
        auto row = MakeRecord(child, runID, eventID, stepID, kind, creator,
                              child.GetPosition(), child.GetGlobalTime(), child.GetWeight());
        // The kernel can assign a track number only after the producing step.
        if (row.parentID != parentID)
            throw std::runtime_error("activation secondary parent differs from producing track");
        row.originStepID = stepID;
        row.secondaryOrdinal = static_cast<int>(i);
        if (extended) {
            SetClockAndEnergy(row, child.GetProperTime(), child.GetKineticEnergy());
            if (decay) {
                row.secondaryCreatorRelation = sameCreator ? "same_process" : (creator ? "other_process" : "unknown");
                if (sameCreator) {
                    row.creatorModelID = child.GetCreatorModelID();
                    row.creatorModelName = child.GetCreatorModelName();
                }
            }
        }
        if (decay) {
            if (sameCreator) ++decaySecondaries;
            else ++excludedSecondaries;
        }
        // This pointer is only an identity token while the native kernel owns an unstacked secondary.
        // It is never dereferenced after this step. Native classification resolves the assigned track ID.
        if (sameCreator && nuclearChild && !pendingBirths_.emplace(&child, BirthLink{records_.size(), creator}).second)
            throw std::runtime_error("activation pending secondary identity is already in use");
        records_.push_back(std::move(row));
    }
    if (extended && decay) records_[parentRow].stepExcludedSecondaryCount = excludedSecondaries;
    if (nativeEvidence && capture) SetCaptureEvidence(records_[parentRow], step, *hadronic, captureCreatorMatches);
    if (decaySecondaries > 0) {
        if (!decayedTracks_.insert(parentID).second)
            throw std::runtime_error("activation observed multiple confirmed decay steps for a single mother track");
        records_[parentRow].kind = "rdm_decay";
    }
}

void Event::AppendCompletedEventPrimaries(const G4Event& event, int runID)
{
    ActivationObservationRecord row{};
    row.runID = runID;
    row.eventID = event.GetEventID();
    row.trackID = row.parentID = row.stepID = -1;
    row.kind = "event_primary_neutron_summary";
    int neutrons = 0;
    int unknown = 0;
    double neutronWeight = 0;
    for (int i = 0; i < event.GetNumberOfPrimaryVertex(); ++i) {
        const auto* vertex = event.GetPrimaryVertex(i);
        if (!vertex) throw std::runtime_error("activation primary vertex is unavailable");
        for (const auto* primary = vertex->GetPrimary(); primary; primary = primary->GetNext()) {
            const auto* definition = primary->GetG4code();
            if (definition && definition->GetPDGEncoding() != kNeutronPdg) continue;
            auto& count = definition ? neutrons : unknown;
            if (count == std::numeric_limits<int>::max())
                throw std::runtime_error("activation primary count exceeds integer range");
            ++count;
            if (definition) {
                const double weight = primary->GetWeight();
                if (weight < 0) throw std::runtime_error("negative activation primary weight");
                neutronWeight = ScoringNumeric::Add(neutronWeight, weight, "activation primary neutron weight");
            }
        }
    }
    row.generatedPrimaryNeutrons = neutrons;
    row.generatedPrimaryNeutronWeight = neutronWeight;
    row.unknownPrimaryDefinitions = unknown;
    records_.push_back(std::move(row));
}

void Event::ObserveStackedTrack(const G4Track& track, bool extended)
{
    const auto pending = pendingBirths_.find(&track);
    if (pending == pendingBirths_.end()) return;
    const auto link = pending->second;
    pendingBirths_.erase(pending);
    const auto& birth = records_.at(link.rowIndex);
    const auto* ion = NuclearIon(track);
    if (track.GetTrackID() <= 0 || track.GetParentID() != birth.parentID ||
        track.GetCreatorProcess() != link.creator || !ion ||
        ion->GetAtomicNumber() != birth.atomicNumber || ion->GetAtomicMass() != birth.massNumber ||
        ion->GetIsomerLevel() != birth.isomer || ion->GetExcitationEnergy()/keV != birth.excitationKeV ||
        (extended && !SameCreatorModel(track, birth)))
        throw std::runtime_error("activation stacked track identity does not match its recorded birth");
    if (!stackedBirths_.emplace(track.GetTrackID(), link).second)
        throw std::runtime_error("activation stacked track ID has multiple births");
}

void Event::Clear()
{
    records_.clear();
    decayedTracks_.clear();
    pendingBirths_.clear();
    stackedBirths_.clear();
    nuclearLineage_.clear();
}

}  // namespace activation_observation
