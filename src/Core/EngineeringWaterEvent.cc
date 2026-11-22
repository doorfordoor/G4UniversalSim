#ifdef G4USIM_H6_ENGINEERING
#include "Core/EngineeringWaterEvent.hh"
#include "Core/EngineeringWaterEscape.hh"
#include "Core/EngineeringWaterState.hh"
#include "Core/EngineeringWaterGate.hh"
#include "Output/OutputManager.hh"
#include "G4WaterObservation.hh"
#include "G4HadronElasticProcess.hh"
#include "G4Neutron.hh"
#include "G4CoupledTransportation.hh"
#include "G4NeutronElasticXS.hh"
#include "G4ProcessManager.hh"
#include "G4ParticleHPElasticData.hh"
#include "G4ParticleHPThermalScatteringData.hh"
#include "Randomize.hh"
#include "CLHEP/Random/MixMaxRng.h"
#include "G4ParticleHPElastic.hh"
#include "G4ParticleHPThermalScattering.hh"
#include "G4HadronicProcessType.hh"
#include "G4Event.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4Step.hh"
#include "G4Threading.hh"
#include "G4SystemOfUnits.hh"
#include <sstream>
#include <iomanip>

namespace engineering_event {
namespace {
using namespace G4WaterObservation;
enum class Phase { idle, beforePrimary, generated, begun, observed };
struct Worker {
    Phase phase=Phase::idle;
    int run=-1,worker=-1,next=0,event=-1,calls=0;
    bool armed=false;
    int invalidations=0;
    const G4HadronElasticProcess* cacheOwner=nullptr;
    const G4Event* current=nullptr;
    Record native{};
    std::vector<unsigned long> rngState;
    std::string row;
};
thread_local Worker w;
void sink(const Record& r) noexcept {
    if (++w.calls==1) w.native=r;
}
void disarm() { if(w.armed){ SetThreadSink(nullptr); w.armed=false; } }
void fail(OutputManager& out,const char* reason) {
    disarm();
    out.RecordOutputFailure("engineering_water_event",reason,w.run);
    if(auto* manager=G4RunManager::GetRunManager())manager->AbortRun(false);
}
bool same(const G4Event* e) {
    const auto* run=G4RunManager::GetRunManager()->GetCurrentRun();
    return e && run && w.run==run->GetRunID() && w.worker==G4Threading::G4GetThreadId() &&
           w.current==e && w.event==e->GetEventID();
}
}
void BeginRun(const G4Run& run) {
    disarm();w=Worker{}; w.run=run.GetRunID();w.worker=G4Threading::G4GetThreadId();
}
void BeforePrimary(const G4Event& e,OutputManager& out) {
    if(!engineering_water::captureFirstWorkerState || out.HasOutputFailure())return;
    if(w.phase!=Phase::idle || w.next!=0 || e.GetEventID()!=0 ||
       w.run!=0 || w.worker<0 || engineering_water::parsedMainSha256!=engineering_water::approvedMain ||
       engineering_water::parsedMainSha256.size()!=64 || out.GetExecutionId().size()!=32){
        fail(out,"invalid first-primary state identity");return;
    }
    w.current=&e;w.event=e.GetEventID();
    if(!same(&e)){fail(out,"worker mismatch before primary");return;}
    const auto* engine=G4Random::getTheEngine();
    if(!engine || typeid(*engine)!=typeid(CLHEP::MixMaxRng)){
        fail(out,"first-primary state requires MixMaxRng");return;
    }
    const auto* mixmax=static_cast<const CLHEP::MixMaxRng*>(engine);
    w.rngState=mixmax->put();
    if(w.rngState.size()!=38 /* engine ID, 17 low/high pairs, counter and checksum pair */ || w.rngState!=mixmax->put()){
        fail(out,"incomplete or changing first-primary RNG state");return;
    }
    w.phase=Phase::beforePrimary;
}
void Generated(const G4Event& e,OutputManager& out) {
    if(out.HasOutputFailure())return;
    const Phase expected=engineering_water::captureFirstWorkerState?Phase::beforePrimary:Phase::idle;
    if(w.phase!=expected || e.GetEventID()!=w.next || (expected==Phase::beforePrimary && !same(&e))) {fail(out,"duplicate, missing or reordered generated primary");return;}
    w.current=&e;w.event=e.GetEventID();
    if(!same(&e)){fail(out,"generated primary run/worker mismatch");return;}
    w.phase=Phase::generated;
}
void Begin(const G4Event& e,OutputManager& out) {
    if(out.HasOutputFailure())return;
    if(w.phase!=Phase::generated || !same(&e)){fail(out,"event begin identity mismatch");return;}
    w.invalidations=0;
    w.cacheOwner=nullptr;
    if(engineering_water::approvedEventLocal){
        auto* pm=G4Neutron::Definition()->GetProcessManager();
        G4HadronElasticProcess* owner=nullptr;
        if(!pm || w.worker<0 || G4RunManager::GetRunManager()->GetCurrentEvent()!=&e){
            fail(out,"invalid worker before GPIL");return;
        }
        for(int i=0;i<pm->GetProcessListLength();++i){
            auto* proc=(*pm->GetProcessList())[i];
            if(proc->GetProcessSubType()!=fHadronElastic)continue;
            if(owner || !pm->GetProcessActivation(i) || typeid(*proc)!=typeid(G4HadronElasticProcess)){
                fail(out,"ambiguous or inactive neutron elastic process");return;
            }
            owner=static_cast<G4HadronElasticProcess*>(proc);
        }
        if(!owner || !owner->GetCrossSectionDataStore()){fail(out,"missing neutron elastic datastore");return;}
        auto* store=owner->GetCrossSectionDataStore();
        const auto& datasets=store->GetDataSetList();
        if(datasets.size()!=3 || !datasets[0] || !datasets[1] || !datasets[2] ||
           typeid(*datasets[0])!=typeid(G4NeutronElasticXS) ||
           typeid(*datasets[1])!=typeid(G4ParticleHPElasticData) ||
           typeid(*datasets[2])!=typeid(G4ParticleHPThermalScatteringData)){
            fail(out,"unapproved neutron elastic dataset sequence");return;
        }
        auto* hp=static_cast<G4ParticleHPElasticData*>(datasets[1]);
        const auto rng=G4Random::getTheEngine()->put();
        hp->InvalidateScopedWaterEventCache();
        store->InvalidateScopedWaterEventCache();
        if(G4Random::getTheEngine()->put()!=rng){fail(out,"invalidation changed RNG");return;}
        w.cacheOwner=owner;++w.invalidations;
    }
    auto previous=SetThreadSink(sink);
    if(previous){SetThreadSink(previous);fail(out,"native listener already occupied");return;}
    w.armed=true;w.calls=0;w.native=Record{};w.phase=Phase::begun;
}
void Observe(const G4Step& step,OutputManager& out) {
    if(out.HasOutputFailure())return;
    auto* manager=G4RunManager::GetRunManager();
    if(!same(manager->GetCurrentEvent()) || w.phase!=Phase::begun || !w.armed){
        fail(out,"duplicate or unmatched first physical step");return;
    }
    if(SetThreadSink(nullptr)!=sink){w.armed=false;fail(out,"native listener replaced");return;}
    w.armed=false;
    const auto& r=w.native;
    const auto* pre=step.GetPreStepPoint();
    const auto* post=step.GetPostStepPoint();
    const auto* track=step.GetTrack();
    const auto* proc=post->GetProcessDefinedStep();
    const char* branch=nullptr;
    const bool escape=engineering_water::thinWorld && w.calls==0 &&
        track->GetStep()==&step && track->GetTrackID()==1 && track->GetParentID()==0 &&
        track->GetCurrentStepNumber()==1 && track->GetDefinition()==G4Neutron::Definition() &&
        track->GetTrackStatus()==fStopAndKill && pre->GetTouchable() &&
        pre->GetTouchable()->GetVolume()==engineering_water::acceptedWorld &&
        SameEmptyDownstreamTouchable(post->GetTouchable(),track->GetNextTouchable()) && proc &&
        typeid(*proc)==typeid(G4CoupledTransportation) && post->GetStepStatus()==fWorldBoundary;
    if(escape) branch="world_escape";
    else if(proc->GetProcessSubType()==fCapture && w.calls==0 && track->GetTrackStatus()==fStopAndKill)
       branch="capture";
    else if(w.calls==1 && r.state==State::ordinaryProposal && r.proposal && r.track==track &&
       r.step==&step && (!w.cacheOwner || r.process==w.cacheOwner) && r.process==proc && typeid(*proc)==typeid(G4HadronElasticProcess) &&
       r.model && r.element && r.sampledA>0 && r.returnedA>0 && r.returnedZ>0 &&
       (r.element==pre->GetMaterial()->GetElement(0) || r.element==pre->GetMaterial()->GetElement(1)) &&
       r.sampledZ==r.element->GetZasInt() && r.projectileEnergy==pre->GetKineticEnergy()) {
        const bool sameZA=r.sampledZ==r.returnedZ && r.sampledA==r.returnedA;
        if(engineering_water::thermal && typeid(*r.model)==typeid(G4ParticleHPThermalScattering) && sameZA){
            if(r.branch==Branch::waterInelastic && r.sampledZ==1) branch="H_water_inelastic";
            if(r.branch==Branch::certifiedOxygenHP && r.sampledZ==8) branch="O_HP_fallback";
        } else if(!engineering_water::thermal && typeid(*r.model)==typeid(G4ParticleHPElastic) &&
                  r.branch==Branch::unmarked)branch=sameZA?"ordinary_HP":"ordinary_HP_reselected";
    }
    if(!branch || (!escape && post->GetStepStatus()!=fPostStepDoItProc)){fail(out,"native first collision unresolved");return;}
    std::ostringstream modelEnergy;
    if(r.model)modelEnergy<<std::setprecision(17)<<r.projectileEnergy/eV;else modelEnergy<<"null";
    std::ostringstream row;
    row<<std::setprecision(17)<<"{\"schema\":\"g4usim_water_collision_engineering_v1\",\"run\":"<<w.run<<",\"event\":"<<w.event<<",\"worker\":"<<w.worker
       <<",\"oxygen_cache_policy\":\"" << (engineering_water::approvedEventLocal?"event_local":"legacy")
       <<"\",\"cache_invalidations\":"<<w.invalidations<<",\"track\":"<<track->GetTrackID()<<",\"step\":"<<track->GetCurrentStepNumber()
       <<",\"process\":\""<<proc->GetProcessName()<<"\",\"branch\":\""<<branch<<"\",\"model\":\""
       <<(r.model?r.model->GetModelName():G4String("unobserved"))<<"\",\"sampled_Z\":"<<r.sampledZ
       <<",\"sampled_A\":"<<r.sampledA<<",\"returned_Z\":"<<r.returnedZ<<",\"returned_A\":"<<r.returnedA
       <<",\"model_eV\":"<<modelEnergy.str()
       <<",\"pre_eV\":"<<pre->GetKineticEnergy()/eV<<",\"post_eV\":"<<post->GetKineticEnergy()/eV
       <<",\"temperature_K\":"<<pre->GetMaterial()->GetTemperature()/kelvin
       <<",\"time_s\":"<<post->GetGlobalTime()/s<<",\"position_mm\":["<<post->GetPosition().x()/mm<<','
       <<post->GetPosition().y()/mm<<','<<post->GetPosition().z()/mm<<"]";
    if(escape){
        row<<",\"pre_mass_touchable\":\"located\",\"post_mass_touchable\":\"null_volume\","
              "\"track_next_mass_touchable\":\"null_volume\",\"post_touchable_matches_next\":true,"
              "\"post_step_status\":\"fWorldBoundary\",\"post_track_status\":\"fStopAndKill\",\"native_callbacks\":0";
    }
    if(engineering_water::captureFirstWorkerState){
        row<<",\"worker_rng_before_primary\":{\"schema\":\"g4usim_mixmax_put_v1\",\"engine\":\"MixMaxRng\","
           <<"\"execution_id\":\""<<out.GetExecutionId()<<"\",\"main_config_sha256\":\""
           <<engineering_water::parsedMainSha256<<"\",\"run\":"<<w.run<<",\"worker\":"<<w.worker
           <<",\"event\":"<<w.event<<",\"put_words\":[";
        for(std::size_t i=0;i<w.rngState.size();++i){
            if(i)row<<',';
            row<<w.rngState[i];
        }
        row<<"]}";
    }
    row<<"}\n";
    w.row=row.str();w.phase=Phase::observed;
}
void End(const G4Event& e,OutputManager& out) {
    if(out.HasOutputFailure()){disarm();return;}
    if(!same(&e) || w.phase!=Phase::observed || e.IsAborted()){fail(out,"event ended without one matching first physical step");return;}
    try {out.WriteEngineeringWaterEvent(w.run,w.event,w.row);}
    catch(const std::exception& err){fail(out,err.what());return;}
    ++w.next;w.phase=Phase::idle;w.current=nullptr;w.row.clear();
}
void EndRun(const G4Run& run,OutputManager& out) {
    disarm();
    if(!out.HasOutputFailure() && (w.phase!=Phase::idle || w.run!=run.GetRunID() ||
            w.next!=run.GetNumberOfEvent() || w.next!=engineering_water::approvedEvents)) fail(out,"run ended with incomplete event ledger");
}
}
#endif
