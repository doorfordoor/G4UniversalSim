// AR2 component probe: no run manager, physics initialization or transport.
#include "Scoring/ScoringManager.hh"
#include "Scoring/EdepScorer.hh"
#include "Config/ConfigManager.hh"
#include "G4Electron.hh"
#include "G4Gamma.hh"
#include "G4Version.hh"
#include "BuildInfo.hh"
#include <iostream>
#include <stdexcept>
#include <thread>
#include <vector>
#include <atomic>

#ifndef G4USIM_BUILD_CONFIGURATION
#define G4USIM_BUILD_CONFIGURATION "unknown"
#endif

namespace {
int checks = 0;
std::atomic<int> calls{0}, alive{0};
void Require(bool ok, const char* text) { if (!ok) throw std::runtime_error(text); ++checks; }
template<class F> void Reject(F f, const std::string& text)
{
    try { f(); } catch (const std::exception& e) {
        Require(std::string(e.what()).find(text) != std::string::npos, e.what()); return;
    }
    throw std::runtime_error("Expected rejection: " + text);
}
class Counter final : public ScorerBase {
public:
    explicit Counter(const std::string& id, double scale = 1) : ScorerBase(id), scale_(scale) { ++alive; }
    ~Counter() override { --alive; }
    void BeginRun(int run) override {
        ++begins[run];
        if (run == failBeginRun) throw std::runtime_error("probe BeginRun " + GetName());
        values.clear(); value = 0;
    }
    void EndRun(int run) override {
        ++ends[run];
        if (run == failEndRun) throw std::runtime_error("probe EndRun " + GetName());
    }
    void BeginEvent(int) override { value = 0; }
    void ScoreHit(const HitRecord& h) override { value += scale_ * h.edep; }
    void EndEvent(int event) override { values.emplace(event, value); }
    std::map<int,double> values;
    std::map<int,int> begins, ends;
    int failBeginRun = -1, failEndRun = -1;
    double value = 0;
private:
    double scale_;
};
std::unique_ptr<ScorerBase> MakeCounter(const ScorerDescription& d, int thread)
{
    ++calls;
    const auto& parameters = d.Settings().parameters;
    const auto fault = parameters.find("fault_thread");
    if (fault != parameters.end() && thread >= 0 && fault->second == thread)
        throw std::runtime_error("worker-only probe failure");
    const auto scale = parameters.find("scale");
    return std::make_unique<Counter>(d.Id(), scale == parameters.end() ? 1 : scale->second);
}
std::unique_ptr<ScorerBase> Null(const ScorerDescription&,int) { return nullptr; }
std::unique_ptr<ScorerBase> Wrong(const ScorerDescription&,int) { return std::make_unique<Counter>("wrong-return-name"); }
std::unique_ptr<ScorerBase> Throw(const ScorerDescription&,int) { throw std::runtime_error("probe std failure"); }
std::unique_ptr<ScorerBase> NonStd(const ScorerDescription&,int) { throw 7; }

void Factories()
{
    ScoringManager m;
    m.SetAutoCreateDefaultScorers(false);
    Reject([&]{m.RegisterScorerFactory("empty", nullptr);},"nonnull");
    Reject([&]{m.RegisterScorer(std::unique_ptr<ScorerBase>{});},"null scorer");
    m.RegisterScorerFactory("counter",MakeCounter);
    Reject([&]{m.RegisterScorerFactory(" Counter ",MakeCounter);},"Duplicate");
    ScorerSettings settings; settings.parameters["scale"]=2;
    m.RegisterScorer(ScorerDescription(" Count ","COUNTER",true,settings));
    Reject([&]{m.RegisterScorer(ScorerDescription("edep","counter"));},"Reserved");
    const auto original=m.GetScorer("count");
    Reject([&]{m.RegisterScorer(ScorerDescription("count","counter"));},"Duplicate");
    Reject([&]{m.RegisterScorer(std::make_unique<Counter>(" COUNT "));},"duplicate");
    Reject([&]{m.RegisterScorer(ScorerDescription("unknown","unknown",false));},"unknown type");
    for (const auto& entry : std::vector<std::pair<std::string,ScorerFactoryRegistry::Factory>>{
             {"null",Null},{"wrong",Wrong},{"throw",Throw},{"nonstd",NonStd}}) {
        m.RegisterScorerFactory(entry.first,entry.second);
        Reject([&]{m.RegisterScorer(ScorerDescription(entry.first,entry.first));},"id='"+entry.first+"'");
        Require(m.GetScorerNames().size()==1 && m.GetScorer("count")==original,"registration atomic");
    }
    for (int workers : {1,2,4}) {
        std::vector<std::unique_ptr<ScoringManager>> copies;
        for (int t=0;t<workers;++t) copies.push_back(m.CloneForThread(nullptr,t));
        for(int t=0;t<workers;++t) {
            Require(copies[t]->GetScorer("count")!=original,"new worker instance");
            for(int u=0;u<t;++u) Require(copies[t]->GetScorer("count")!=copies[u]->GetScorer("count"),"worker isolation");
        }
        std::vector<std::thread> threads;
        std::atomic<bool> ok{true};
        for(int t=0;t<workers;++t) threads.emplace_back([&,t]{
            try {
                auto& c=*copies[t];
                for(int run=0;run<2;++run) {
                    c.BeginRun(run);
                    for(int event=0;event<3;++event) {
                        c.BeginEvent(event);
                        if(event!=1) { HitRecord h; h.edep=t+1; c.ScoreHit(h); }
                        c.EndEvent(event);
                    }
                    c.EndRun(run);
                    const auto* counter=dynamic_cast<Counter*>(c.GetScorer("count"));
                    if(counter->values.size()!=3 || counter->values.at(1)!=0 || counter->values.at(0)!=2*(t+1)) ok=false;
                }
            } catch(...) {ok=false;}
        });
        for(auto& thread:threads) thread.join();
        Require(ok,"two run reset and event isolation including zero history");
    }
    Require(dynamic_cast<Counter*>(original)->values.empty(),"master unmodified");
    auto legacy=std::make_unique<Counter>("legacy"); legacy->SetEnabled(false);
    m.RegisterScorer(std::move(legacy));
    int before=calls;
    for(int id : {-1,0,3}) Reject([&]{m.CloneForThread(nullptr,id);},"legacy");
    Require(calls==before && m.HasScorer("legacy"),"legacy refused before any factory, not lost");
    m.GetScorer("legacy")->SetEnabled(true);
    m.BeginRun(0);m.BeginEvent(0);HitRecord h;h.edep=3;m.ScoreHit(h);m.EndEvent(0);m.EndRun(0);
    Require(dynamic_cast<Counter*>(m.GetScorer("legacy"))->values.at(0)==3,"legacy direct use retained");
    ScoringManager f; f.SetAutoCreateDefaultScorers(false);f.RegisterScorerFactory("counter",MakeCounter);
    f.RegisterScorer(ScorerDescription("first","counter"));
    settings.parameters["fault_thread"]=0;
    f.RegisterScorer(ScorerDescription("second","counter",true,settings));
    const auto live=alive.load();
    Reject([&]{f.CloneForThread(nullptr,0);},"thread=0");
    Require(alive==live && f.GetScorerNames().size()==2,"failed clone destroys partial instances");
    Require(f.CloneForThread(nullptr,1)->GetScorerNames().size()==2,"nonfault worker succeeds");
    auto frozen=f.CloneForThread(nullptr,1);
    Reject([&]{frozen->RegisterScorerFactory("late",MakeCounter);},"frozen");
}

void Builtins()
{
    ScoringManager m;
    m.EnableLETScoring(true);m.EnableDoseScoring(true);m.EnableFluenceScoring(true);m.EnableDisplacementScoring(true);
    m.ConfigureEdepHistogram(17,0,34);m.ConfigureWeightedEdepHistogram(19,1,39);
    m.EnsureDefaultScorers();
    auto snapshot=m.GetScorerDescriptions();
    Require(snapshot.size()==5,"all five builtins described");
    m.ConfigureEdepHistogram(11,0,22);m.EnableLETScoring(false);
    auto c=m.CloneForThread(nullptr,0);
    Require(c->GetScorerNames().size()==5 && !c->GetScorer("let")->IsEnabled(),"disabled builtin survives clone");
    Require(snapshot.front().Settings().rawHistogram.bins==17 && c->GetScorerDescriptions().front().Settings().rawHistogram.bins==11,"immutable snapshot and current authority");
    c->EnableDoseScoring(false);c->EnableFluenceScoring(false);c->EnableDisplacementScoring(false);
    for(int run=0;run<2;++run) {
        c->BeginRun(run); c->BeginEvent(0);HitRecord h;h.edep=2;h.weight=3;c->ScoreHit(h);c->EndEvent(0);
        c->BeginEvent(1);c->EndEvent(1);c->EndRun(run);
        auto* edep=dynamic_cast<EdepScorer*>(c->GetScorer("edep"));
        Require(edep->GetRunRawEdep()==2 && edep->GetRunWeightedEdep()==6,"builtin two-run Edep preserved");
    }
}

void Selectors()
{
    ScoringManager notReady;notReady.SetLETParticles({"e-"});
    Reject([&]{notReady.ValidateVolumeConfigsForRun();},"not ready");
    G4Electron::ElectronDefinition();G4Gamma::GammaDefinition();
    for(const auto& section : {std::string("scoring.let"),std::string("phase_space")}) {
        for(const auto& tokens : {std::string("all"),std::string("gamma"),std::string("e-,misspelled"),std::string("misspelled")}) {
            ConfigManager config;
            const std::string bytes="[scoring]\nlet=true\n["+section+"]\n"+
                (section=="phase_space"?"volume=Probe_PV\n":"")+"particles="+tokens+"\n";
            config.LoadMainConfigBytes("selector-probe.ini",bytes);
            ScoringManager m;m.LoadFromConfig(config);
            Require(!m.HasVolumeConfig(),"selector check has no filter/spectrum");
            if(tokens.find("misspelled")!=std::string::npos) {
                Reject([&]{m.ValidateVolumeConfigsForRun();},"["+section+"]/particles");
                Reject([&]{m.BeginRun(0);},"misspelled");
                auto c=m.CloneForThread(nullptr,0);
                Reject([&]{c->ValidateVolumeConfigsForRun();},"selector-probe.ini line");
            } else {
                m.ValidateVolumeConfigsForRun();
                m.BeginRun(0);m.BeginEvent(0);m.EndEvent(0);m.EndRun(0);
                Require(m.GetCurrentEventRawEdep()==0,"legal selector permits zero contribution event");
            }
        }
    }
}

void StartupCleanup()
{
    // Reuse the sole deterministic probe type; no production injection or new type branch.
    for(int mode=0; mode<3; ++mode) {
        ScoringManager m; m.SetAutoCreateDefaultScorers(false);
        auto a=std::make_unique<Counter>("a"); auto* pa=a.get();
        auto b=std::make_unique<Counter>("b"); auto* pb=b.get();
        auto c=std::make_unique<Counter>("c"); auto* pc=c.get();
        m.RegisterScorer(std::move(a));m.RegisterScorer(std::move(b));m.RegisterScorer(std::move(c));
        if(mode==0) {
            pb->failBeginRun=0;
            Reject([&]{m.BeginRun(0);},"probe BeginRun b");
            Require(pa->begins[0]==1 && pb->begins[0]==1 && pc->begins[0]==0,"only A/B entered after B begin failure");
            m.EndRun(0);
            Require(pa->ends[0]==1 && pb->ends[0]==1 && pc->ends[0]==0,"partial Begin ends exactly A/B");
            m.EndRun(0);
            Require(pa->ends[0]==1 && pb->ends[0]==1 && pc->ends[0]==0,"partial Begin duplicate End is inert");
        } else if(mode==1) {
            pb->failEndRun=0;
            m.BeginRun(0);
            Reject([&]{m.EndRun(0);},"probe EndRun b");
            Require(pa->ends[0]==1 && pb->ends[0]==1 && pc->ends[0]==1,"B End failure still cleans C");
            m.EndRun(0);
            Require(pa->ends[0]==1 && pb->ends[0]==1 && pc->ends[0]==1,"throwing End consumed once");
        } else {
            m.BeginRun(0);m.EndRun(0);
            Require(pa->ends[0]==1 && pb->ends[0]==1 && pc->ends[0]==1,"first run completed all cleanup");
            m.SetLETParticles({"protno"});
            Reject([&]{m.BeginRun(1);},"protno");
            Require(pa->begins[1]==0 && pb->begins[1]==0 && pc->begins[1]==0,"second selector failure enters no scorer");
            m.EndRun(1);m.EndRun(1);m.EndRun(0);
            Require(pa->ends[1]==0 && pb->ends[1]==0 && pc->ends[1]==0,"second selector failure ends no scorer");
            Require(pa->ends[0]==1 && pb->ends[0]==1 && pc->ends[0]==1,"second failure never replays first run cleanup");
        }
    }
}

void BuiltinAliasesAndEnabledDrift()
{
    auto registry=BuiltinScorerFactories();
    ScoringManager aliases; aliases.SetAutoCreateDefaultScorers(false);
    for(const std::string type : {"edep","let","dose","fluence","displacement"}) {
        Reject([&]{registry.Create(ScorerDescription("alias_"+type,type),-1);},"canonical id");
        Reject([&]{aliases.RegisterScorer(ScorerDescription("alias_"+type,type));},"canonical id");
        Require(aliases.GetScorerNames().empty() && aliases.GetScorerDescriptions().empty(),"builtin alias rejection is atomic");
        auto canonical=registry.Create(ScorerDescription(type,type),0);
        Require(canonical && canonical->GetName()==type && canonical->IsEnabled(),"canonical builtin factory remains usable");
    }
    ScoringManager defaults;
    defaults.EnableLETScoring(true);defaults.EnableDoseScoring(true);
    defaults.EnableFluenceScoring(true);defaults.EnableDisplacementScoring(true);
    defaults.EnsureDefaultScorers();
    auto defaultClone=defaults.CloneForThread(nullptr,0);
    Require(defaultClone->GetScorerNames()==defaults.GetScorerNames() && defaultClone->GetScorerNames().size()==5,
            "canonical default Manager path remains usable");
    for(bool enabled : {true,false}) {
        ScoringManager m; m.SetAutoCreateDefaultScorers(false);
        m.RegisterScorerFactory("counter",MakeCounter);
        m.RegisterScorer(ScorerDescription("first_custom","counter"));
        m.RegisterScorer(ScorerDescription("independent_custom_id","counter",enabled));
        auto* instance=m.GetScorer("independent_custom_id");
        const auto snapshot=m.GetScorerDescriptions();
        auto good=m.CloneForThread(nullptr,0);
        Require(good->GetScorer("independent_custom_id")->IsEnabled()==enabled,"nonbuiltin custom id supports either enabled state");
        instance->SetEnabled(!enabled);
        const int before=calls;
        for(int thread : {-1,0,1}) Reject([&]{m.CloneForThread(nullptr,thread);},"enabled state differs");
        Require(calls==before,"drift rejected before any factory, including earlier valid custom instance");
        Require(m.GetScorer("independent_custom_id")==instance && instance->IsEnabled()==!enabled,
                "drift rejection never writes back or replaces master instance");
        Require(snapshot.back().Enabled()==enabled,"immutable snapshot remains authoritative");
        instance->SetEnabled(enabled);
        auto restored=m.CloneForThread(nullptr,1);
        Require(restored->GetScorer("independent_custom_id")!=instance &&
                restored->GetScorer("independent_custom_id")->IsEnabled()==enabled,
                "restoring declared enabled state permits fresh clone");
        Require(instance->IsEnabled()==enabled && m.GetScorerDescriptions().back().Enabled()==enabled,
                "recovery preserves master and accepted description");
    }
}
}

int main(int argc, char** argv)
{
    try {
        if (argc == 2 && std::string(argv[1]) == "--identity") {
            std::cout << effective_config::Value(effective_config::Value::Object{
                {"source_fingerprint", G4USIM_SOURCE_FINGERPRINT},
                {"probe_sha256", G4USIM_SCORER_FACTORY_PROBE_SHA256},
                {"geant4_version_number", G4VERSION_NUMBER},
                {"compiler", G4USIM_COMPILER_ID},
                {"compiler_version", G4USIM_COMPILER_VERSION},
                {"build_configuration", G4USIM_BUILD_CONFIGURATION},
                {"git_commit", G4USIM_GIT_COMMIT},
                {"git_source_state", G4USIM_GIT_SOURCE_STATE}}).ToJson() << '\n';
            return 0;
        }
        if (argc != 1) throw std::runtime_error("usage: scorerFactoryCheck [--identity]");
        Factories();Builtins();Selectors();
        Require(alive==0,"all probe instances destroyed");
        if(checks!=73) throw std::runtime_error("Original 73-check suite count changed");
        std::cout<<"Original scorer factory component: 73 checks passed\n";
        StartupCleanup();
        Require(alive==0,"cleanup regression releases all instances");
        if(checks!=86) throw std::runtime_error("Original 86-check suite count changed");
        std::cout<<"Prior scorer factory component: 86 checks passed\n";
        BuiltinAliasesAndEnabledDrift();
        Require(alive==0,"alias/drift regression releases all instances");
        std::cout<<"AR2 scorer factory component: "<<checks<<" checks passed; no transport\n";
        return 0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
