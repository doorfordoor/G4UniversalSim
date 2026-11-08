#include "Source/PhaseSpaceReplayState.hh"
#include "G4DynamicParticle.hh"
#include "G4Step.hh"
#include "G4ParticleTable.hh"
#include "G4EventManager.hh"
#include "G4Event.hh"
#include "G4RunManager.hh"
#include "G4Run.hh"
#include "G4IonTable.hh"
#include "G4ParticleDefinition.hh"
#include "G4PrimaryParticle.hh"
#include "G4StepPoint.hh"
#include "G4Track.hh"
#include "G4VUserPrimaryParticleInformation.hh"
#include "G4SystemOfUnits.hh"
#include "G4PhysicalConstants.hh"
#include <cmath>
#include <cfloat>
#include <cstdlib>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <sstream>
#include <mutex>
#include <limits>
#include <stdexcept>
#include <utility>
namespace {
std::string Where(const PhaseSpaceParticle& p,const std::string& file) {
    return "PhaseSpace '"+file+"' line "+std::to_string(p.inputLine);
}
bool Ion(const G4ParticleDefinition& d){return G4IonTable::IsIon(&d)||G4IonTable::IsAntiIon(&d);}
void CheckKinematics(double energy,double mass,const std::string& where) {
    if(!std::isfinite(energy)||energy<0||!std::isfinite(mass)||mass<0)
        throw std::runtime_error(where+": invalid kinematics input");
    const double total=energy+mass,twice=energy+2.*mass,product=energy*twice;
    if(!std::isfinite(total)||!std::isfinite(twice)||!std::isfinite(product))
        throw std::runtime_error(where+": kinematics exceed finite SDK energy/momentum range");
    const double momentum=std::sqrt(product);
    const double beta=mass>0 && energy<1000.*mass ? momentum/total : 1.;
    if(!std::isfinite(momentum)||!std::isfinite(beta)||!std::isfinite(beta*c_light))
        throw std::runtime_error(where+": nonfinite derived kinematics");
}
class Payload final:public G4VUserPrimaryParticleInformation {
public:
    Payload(const PhaseSpaceParticle& p,std::string f):record(p),file(std::move(f)){}
    void Print() const override {}
    const PhaseSpaceParticle record;
    const std::string file;
    // Lifecycle receipt only; not a second state authority. Owned by this primary/event.
    const G4Track* restoredTrack=nullptr;
};
void Trace(const char* stage,const G4Track& t,const Payload& payload,const G4StepPoint* pre) {
    const char* path=std::getenv("G4USIM_TEST_PRIMARY_VERTICES");if(!path||!*path)return;
    const auto* d=t.GetDynamicParticle();const auto* primary=d->GetPrimaryParticle();
    auto* em=G4EventManager::GetEventManager();const auto* event=em?em->GetConstCurrentEvent():nullptr;
    auto* rm=G4RunManager::GetRunManager();const auto* run=rm?rm->GetCurrentRun():nullptr;
    std::ostringstream line;line<<std::setprecision(17)<<"{\"stage\":\""<<stage<<"\",\"event\":"<<(event?event->GetEventID():-1)<<",\"run\":"<<(run?run->GetRunID():-1)
      <<",\"track_id\":"<<t.GetTrackID()<<",\"input_line\":"<<payload.record.inputLine
      <<",\"recorded_charge_eplus\":"<<*payload.record.charge/eplus<<",\"primary_charge_eplus\":"<<primary->GetCharge()/eplus
      <<",\"actual_charge_eplus\":"<<(pre?pre->GetCharge():d->GetCharge())/eplus
      <<",\"mass_MeV\":"<<(pre?pre->GetMass():d->GetMass())/MeV
      <<",\"energy_MeV\":"<<(pre?pre->GetKineticEnergy():d->GetKineticEnergy())/MeV
      <<",\"beta\":"<<(pre?pre->GetVelocity():t.GetVelocity())/c_light;
    if(!pre){line<<",\"occupancy\":";const auto* o=d->GetElectronOccupancy();if(!o)line<<"null";else{line<<'[';for(int i=0;i<o->GetSizeOfOrbit();++i){if(i)line<<',';line<<o->GetOccupancy(i);}line<<']';}}
    line<<"}\n";
    static std::mutex mutex;std::lock_guard<std::mutex> lock(mutex);
    std::ofstream stream(std::filesystem::u8path(std::string(path)+".phase-state.jsonl"),std::ios::binary|std::ios::app);
    stream<<line.str();stream.close();if(!stream)throw std::runtime_error("Cannot write phase-state diagnostic");
}
}
namespace phase_space_replay {
void ValidateForDefinition(const PhaseSpaceParticle& p,const G4ParticleDefinition& d,const std::string& file) {
    const auto where=Where(p,file);
    if(!p.charge || !std::isfinite(*p.charge))throw std::runtime_error(where+": missing finite actual charge");
    CheckKinematics(p.kineticEnergy,d.GetPDGMass(),where);
    if(p.dynamicState && (d.IsShortLived() || d.GetPDGEncoding()==0 ||
       G4ParticleTable::GetParticleTable()->FindParticle(d.GetPDGEncoding())!=&d))
        throw std::runtime_error(where+": v3 sentinel requires a registered non-short-lived definition");
    if(*p.charge==DBL_MAX)throw std::runtime_error(where+": DBL_MAX is an internal construction sentinel, not recorded charge");
    // Mirror only the actual SDK conversion branch; do not execute an unsafe cast.
    if(!p.dynamicState && d.GetAtomicNumber()>=0) {
        const long double integerCharge=std::trunc(static_cast<long double>(*p.charge/eplus));
        const long double lo=std::numeric_limits<G4int>::min(),hi=std::numeric_limits<G4int>::max();
        const long double electrons=static_cast<long double>(d.GetAtomicNumber())-integerCharge;
        if(integerCharge<lo || integerCharge>hi || electrons<lo || electrons>hi)
            throw std::runtime_error(where+": charge is unsafe for SDK PrimaryTransformer integer charge/atomic-number difference");
        if(electrons>0 && G4IonTable::IsIon(&d))CheckKinematics(p.kineticEnergy,d.GetPDGMass()+static_cast<double>(electrons)*electron_mass_c2,where);
    }
    if(!p.dynamicState) {
        if(Ion(d))throw std::runtime_error(where+": legacy v2 ion lacks dynamic state; record phase_space_csv_v3");
        return; // Explicit v2 non-ion compatibility: definition mass/occupancy assumption.
    }
    const auto& s=*p.dynamicState;PhaseSpace::ValidateDynamicState(s,where);
    CheckKinematics(p.kineticEnergy,s.mass,where);
    if(Ion(d) && s.mass<=0)throw std::runtime_error(where+": v3 ion requires positive dynamic mass");
    // Complete v3 uses DBL_MAX only for construction: the SDK leaves actual none intact.
    // SDK AllocateElectronOccupancy supports IsIon, not every IsAntiIon layout.
    if(s.electronOccupancy && !G4IonTable::IsIon(&d))
        throw std::runtime_error(where+": SDK cannot restore electron_occupancy for this particle layout");
    if(!Ion(d) && s.electronOccupancy)throw std::runtime_error(where+": non-ion electron_occupancy unsupported");
    if(s.electronOccupancy && s.electronOccupancy->size()!=G4ElectronOccupancy::MaxSizeOfOrbit)
        throw std::runtime_error(where+": unsupported SDK electron_occupancy orbit count");
    if(d.GetParticleName()=="opticalphoton")throw std::runtime_error(where+": optical photon dynamic replay unsupported");
}
PhaseSpaceDynamicState CaptureDynamicState(const G4Track& t,const G4StepPoint& post) {
    const auto* d=t.GetDynamicParticle();
    if(!d || d->GetCharge()!=post.GetCharge() || d->GetMass()!=post.GetMass() ||
       d->GetPolarization()!=post.GetPolarization())
        throw std::runtime_error("PhaseSpace boundary dynamic/post state mismatch");
    if(d->GetPreAssignedDecayProducts() || !std::isfinite(d->GetPreAssignedDecayProperTime()) || d->GetPreAssignedDecayProperTime()>=0.)
        throw std::runtime_error("PhaseSpace preassigned decay products/time unsupported (ordinary proper time is not this field)");
    if(d->GetSpin()!=d->GetDefinition()->GetPDGSpin())throw std::runtime_error("PhaseSpace custom dynamic spin unsupported");
    PhaseSpaceDynamicState s;s.mass=d->GetMass();s.magneticMoment=d->GetMagneticMoment();
    const auto pol=d->GetPolarization();s.polarization={{pol.x(),pol.y(),pol.z()}};
    if(const auto* o=d->GetElectronOccupancy()) {
        s.electronOccupancy.emplace();
        for(int i=0;i<o->GetSizeOfOrbit();++i)s.electronOccupancy->push_back(o->GetOccupancy(i));
    }
    PhaseSpace::ValidateDynamicState(s,"capture");
    // Preserve genuine none, including anti-ion layouts. Replay validates support before events.
    return s;
}
void AttachPrimaryState(G4PrimaryParticle& primary,const PhaseSpaceParticle& p,const std::string& file) {
    if(!p.charge)return; // v1 non-ion legacy, no fabricated state.
    if(primary.GetUserInformation())throw std::runtime_error(Where(p,file)+": primary userinfo already occupied");
    if(!primary.GetG4code())throw std::runtime_error(Where(p,file)+": primary definition missing");
    ValidateForDefinition(p,*primary.GetG4code(),file);
    primary.SetUserInformation(new Payload(p,file));
    if(p.dynamicState) primary.SetCharge(DBL_MAX); // Never overwrite the immutable recorded charge.
}
RestoreResult RestoreBeforeTracking(G4Track& t) {
    // SDK copies may retain a primary pointer. Secondary ancestry wins over payload identity.
    if (t.GetParentID()!=0) return RestoreResult::NotMarked;
    auto* d=const_cast<G4DynamicParticle*>(t.GetDynamicParticle());
    auto* p=d?d->GetPrimaryParticle():nullptr;
    auto* payload=p?dynamic_cast<Payload*>(p->GetUserInformation()):nullptr;
    if(!payload)return RestoreResult::NotMarked;
    const auto fail=[&](const char* msg){throw std::runtime_error(Where(payload->record,payload->file)+": "+msg);};
    if(payload->restoredTrack) {
        if(payload->restoredTrack!=&t)fail("primary reused by another track");
        return RestoreResult::AlreadyRestored; // Legitimate reclassification: never overwrite evolved state.
    }
    if(t.GetCurrentStepNumber()!=0 || t.GetStep()!=nullptr)fail("restore must precede tracking/step initialization");
    const auto& record=payload->record;
    if(d->GetDefinition()->GetPDGEncoding()!=record.pdg)fail("definition/record PDG mismatch");
    ValidateForDefinition(record,*d->GetDefinition(),payload->file);
    if(t.UseGivenVelocity())fail("externally prescribed velocity unsupported");
    if(d->GetPreAssignedDecayProducts() || !std::isfinite(d->GetPreAssignedDecayProperTime()) || d->GetPreAssignedDecayProperTime()>=0.)
        fail("preassigned decay products/time unsupported");
    const auto energy=d->GetKineticEnergy();
    if(record.dynamicState) {
        const auto& s=*record.dynamicState;
        if(!s.electronOccupancy && d->GetElectronOccupancy())fail("cannot remove SDK electron occupancy object");
        if(s.electronOccupancy) {
            if (!d->GetElectronOccupancy()) d->AddElectron(0,0); // public API allocates without adding electrons
            const auto* o=d->GetElectronOccupancy();
            if(!o || o->GetSizeOfOrbit()!=static_cast<int>(s.electronOccupancy->size()))fail("SDK orbit allocation mismatch");
            // Remove first across all orbits to avoid transient total-count overflow.
            for(int i=0;i<o->GetSizeOfOrbit();++i) {
                const auto have=d->GetOccupancy(i),want=s.electronOccupancy->at(i);
                if(have>want)d->RemoveElectron(i,have-want);
            }
            for(int i=0;i<o->GetSizeOfOrbit();++i) {
                const auto have=d->GetOccupancy(i),want=s.electronOccupancy->at(i);
                if(have<want)d->AddElectron(i,want-have);
                if(d->GetOccupancy(i)!=want)fail("SDK orbit restoration mismatch");
            }
        }
        d->SetMass(s.mass);d->SetMagneticMoment(s.magneticMoment);
        d->SetPolarization(s.polarization[0],s.polarization[1],s.polarization[2]);
    }
    d->SetCharge(*record.charge);
    // Add/RemoveElectron changes mass directly. SetMass may see equal mass;
    // Both setters invalidate beta only when their value changes. Force a local
    // two-set reset before tracking starts, then restore the exact energy.
    d->SetKineticEnergy(energy==0. ? 1.*eV : 0.);
    d->SetKineticEnergy(energy);
    const double momentum=std::sqrt(energy*(energy+2*d->GetMass()));
    const double beta=d->GetMass()>0 && energy<1000*d->GetMass()?momentum/(energy+d->GetMass()):1.;
    const double actualVelocity=t.GetVelocity(),actualMomentum=d->GetTotalMomentum();
    if(!std::isfinite(actualVelocity)||!std::isfinite(actualMomentum)||!std::isfinite(beta)||
       !std::isfinite(d->GetCharge())||std::abs(actualVelocity/c_light-beta)>1e-12 || d->GetCharge()!=*record.charge)
        fail("restored velocity/charge readback mismatch");
    payload->restoredTrack=&t;
    Trace("dynamic_restored",t,*payload,nullptr);
    return RestoreResult::Restored;
}
void ObserveFirstStep(const G4Step& step) {
    const auto* t=step.GetTrack();if(!t || t->GetParentID()!=0 || t->GetCurrentStepNumber()!=1)return;
    const auto* primary=t->GetDynamicParticle()->GetPrimaryParticle();
    const auto* payload=primary?dynamic_cast<const Payload*>(primary->GetUserInformation()):nullptr;
    if(!payload)return;
    const auto* pre=step.GetPreStepPoint();
    if(payload->restoredTrack!=t || !pre || !std::isfinite(pre->GetCharge()) || pre->GetCharge()!=*payload->record.charge ||
       (payload->record.dynamicState && pre->GetMass()!=payload->record.dynamicState->mass))
        throw std::runtime_error(Where(payload->record,payload->file)+": first step did not receive restored phase state");
    Trace("first_step_pre",*t,*payload,pre);
}
}
