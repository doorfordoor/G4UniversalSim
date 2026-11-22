#pragma once
#include "Scoring/NativeClockScope.hh"
#include "Config/InputProvenance.hh"
#include "Core/SessionJson.hh"
#include "Output/OutputManager.hh"
#include "G4DynamicParticle.hh"
#include "G4Event.hh"
#include "G4Ions.hh"
#include "G4PrimaryParticle.hh"
#include "G4PrimaryVertex.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4Step.hh"
#include "G4SystemOfUnits.hh"
#include "G4Threading.hh"
#include "G4Track.hh"
#include <cmath>
#include <cstring>
#include <filesystem>
#include <map>
#include <tuple>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace activation_observation {
class ClockEvent {
    using Json = SessionJson::Json;
    using StepKey = std::tuple<int,int,int,int>;
    NativeClockScope scope_{256};
    std::string digest_, module_, staged_;
    const G4PrimaryParticle* primary_ = nullptr;
    std::map<StepKey, bool> nuclearSteps_;
    Json start_;
    static std::string Hex(uint64_t value) {
        const char* digits = "0123456789abcdef";
        std::string result(16,'0');
        for (int i=15; i>=0; --i) {result[i]=digits[value & 15]; value >>= 4;}
        return result;
    }
    static std::string Bits(double value) {
        if (!std::isfinite(value)) throw std::runtime_error("nonfinite native clock source");
        uint64_t bits;
        std::memcpy(&bits,&value,sizeof(bits));
        return Hex(bits);
    }
    static std::string Image(const void* address) {
#ifdef _WIN32
        HMODULE module{};
        if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(address),&module))
            throw std::runtime_error("native observer module unavailable");
        wchar_t path[32768];
        auto n=GetModuleFileNameW(module,path,32768);
        if (!n || n>=32768) throw std::runtime_error("native observer module path unavailable");
        return std::filesystem::canonical(std::filesystem::path(std::wstring(path,n))).string();
#else
        Dl_info info{};
        if (!dladdr(address,&info) || !info.dli_fname)
            throw std::runtime_error("native observer module unavailable");
        return std::filesystem::canonical(info.dli_fname).string();
#endif
    }
    static void Identity(int run,int event) {
        auto* manager=G4RunManager::GetRunManager();
        if (!manager || !manager->GetCurrentRun() || !manager->GetCurrentEvent() ||
            manager->GetCurrentRun()->GetRunID()!=run || manager->GetCurrentEvent()->GetEventID()!=event)
            throw std::runtime_error("native clock current event/run mismatch");
    }
public:
    bool active=false;
    explicit ClockEvent(const std::string& digest) : digest_(digest) {
        module_=Image(reinterpret_cast<const void*>(&G4AtRestObserverV1Begin));
        if (module_!=Image(reinterpret_cast<const void*>(&G4AtRestObserverV1End)) ||
            input_provenance::HashFile(module_).sha256!=digest_)
            throw std::runtime_error("native observer loaded library identity mismatch");
    }
    void Begin(int run,int event) {
        Identity(run,event);
        primary_=nullptr;
        nuclearSteps_.clear();
        start_=nullptr;
        staged_.clear();
        scope_.Begin(run,event,G4Threading::G4GetThreadId());
        active=true;
    }
    void Discard() noexcept { scope_.Discard(); active=false; staged_.clear(); }
    void Observe(const G4Step& step) {
        const auto* t=step.GetTrack();
        if (!active || !t) throw std::runtime_error("unbound clock step");
        const auto* ion=dynamic_cast<const G4Ions*>(t->GetDefinition());
        if (!ion) return;
        const int pdg=ion->GetPDGEncoding();
        StepKey key{t->GetTrackID(),t->GetCurrentStepNumber(),t->GetParentID(),pdg};
        if (!nuclearSteps_.emplace(key,true).second) throw std::runtime_error("duplicate ion step identity");
        if (t->GetParentID()!=0 || t->GetCurrentStepNumber()!=1) return;
        auto* pre=step.GetPreStepPoint();
        if (primary_ || !pre || (pdg!=1000090180 && pdg!=1000200470) || ion->GetExcitationEnergy()!=0)
            throw std::runtime_error("unsupported native primary ion start");
        primary_=t->GetDynamicParticle()->GetPrimaryParticle();
        if (!primary_) throw std::runtime_error("missing generating primary");
        start_={{"track_id",t->GetTrackID()},{"pdg",pdg},{"weight_bits",Bits(pre->GetWeight())},
                {"global_ns_bits",Bits(pre->GetGlobalTime()/ns)},{"local_ns_bits",Bits(pre->GetLocalTime()/ns)},
                {"proper_ns_bits",Bits(pre->GetProperTime()/ns)}};
    }
    void Stage(const G4Event& e,int run,int event) {
        Identity(run,event);
        const auto* v=e.GetPrimaryVertex();
        if (e.GetNumberOfPrimaryVertex()!=1 || !v || v->GetNumberOfParticle()!=1 ||
            !primary_ || v->GetPrimary()!=primary_ || !primary_->GetG4code() ||
            primary_->GetG4code()->GetPDGEncoding()!=start_.at("pdg").get<int>() ||
            primary_->GetTrackID()!=start_.at("track_id").get<int>())
            throw std::runtime_error("generated and started primary ion mismatch");
        const int worker=G4Threading::G4GetThreadId();
        scope_.Close(run,event,worker,[&](const auto* rows,uint64_t count){
            Json draws=Json::array();
            for (uint64_t i=0;i<count;++i) {
                const auto& r=rows[i];
                if (!nuclearSteps_.count(StepKey{r.track_id,r.step_number,r.parent_id,r.pdg_encoding}))
                    throw std::runtime_error("native draw has no ion step");
                draws.push_back({{"ordinal",r.ordinal},{"token",Hex(r.token)},{"track_id",r.track_id},
                    {"step",r.step_number},{"parent",r.parent_id},{"pdg",r.pdg_encoding},{"branch",r.branch},
                    {"u_bits",Hex(r.u_bits)},{"tau_ns_bits",Hex(r.tau_ns_bits)},{"wait_ns_bits",Hex(r.wait_ns_bits)},
                    {"pre_global_ns_bits",Hex(r.pre_global_ns_bits)},{"pre_local_ns_bits",Hex(r.pre_local_ns_bits)},
                    {"pre_proper_ns_bits",Hex(r.pre_proper_ns_bits)},{"sampled_global_ns_bits",Hex(r.sampled_global_ns_bits)},
                    {"sampled_local_ns_bits",Hex(r.sampled_local_ns_bits)},{"threshold_ns_bits",Hex(r.threshold_ns_bits)}});
            }
            Json result={{"schema","g4usim_native_at_rest_engineering_v1"},{"formal_eligible",false},
                {"run",run},{"event",event},{"worker",worker},{"token",Hex((uint64_t(run)<<32)|(uint64_t(event)+1))},
                {"status",count?"observed":"unclassified_no_draw"},{"library",module_},{"sha256",digest_},
                {"generated",{{"vertex",0},{"index",0},{"track_id",primary_->GetTrackID()},{"pdg",primary_->GetPDGcode()},
                    {"vertex_weight_bits",Bits(v->GetWeight())},{"weight_bits",Bits(primary_->GetWeight())},
                    {"global_ns_bits",Bits(v->GetT0()/ns)}}},{"started",start_},{"draws",std::move(draws)}};
            staged_=result.dump()+"\n";
        });
        active=false;
    }
    void Publish(OutputManager& out,int run,int event) {
        if (staged_.empty()) throw std::runtime_error("missing staged clock event");
        out.WriteNativeClockEvent(run,event,staged_);
        staged_.clear();
    }
};
}
