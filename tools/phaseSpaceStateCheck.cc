#include "Source/PhaseSpaceReplayState.hh"
#include "BuildInfo.hh"
#include "G4RunManager.hh"
#include "G4VUserDetectorConstruction.hh"
#include "G4VUserPhysicsList.hh"
#include "G4Box.hh"
#include "G4LogicalVolume.hh"
#include "G4PVPlacement.hh"
#include "G4NistManager.hh"
#include "G4BosonConstructor.hh"
#include "G4LeptonConstructor.hh"
#include "G4BaryonConstructor.hh"
#include "G4IonConstructor.hh"
#include "G4IonTable.hh"
#include "G4PrimaryTransformer.hh"
#include "G4Event.hh"
#include "G4PrimaryVertex.hh"
#include "G4Track.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh"
#include "G4DecayProducts.hh"
#include "G4AntiAlpha.hh"
#include "G4Proton.hh"
#include "G4Gamma.hh"
#include <sstream>
#include <iterator>
#include "G4Electron.hh"
#include "G4Alpha.hh"
#include "G4SystemOfUnits.hh"
#include "G4PhysicalConstants.hh"
#include "G4Version.hh"
#ifndef G4USIM_PHASE_STATE_CORE_ONLY
#include "Actions/PhaseSpaceStackingAction.hh"
#include "Actions/SteppingAction.hh"
#include "Core/SimulationManager.hh"
#include "G4TransportationManager.hh"
#include "G4Navigator.hh"
#include "Actions/WorkerRunContext.hh"
#include "Output/OutputManager.hh"
#include "Scoring/ScoringManager.hh"
#include "G4StackManager.hh"
#include "G4TrackingManager.hh"
#include "G4UserSteppingAction.hh"
#endif
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <vector>
#include <cmath>
#include <limits>
namespace {
int checks=0;
void Check(bool yes,const char* text){if(!yes)throw std::runtime_error(text);++checks;}
template<class F>void Reject(F f,const char* text){bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}Check(rejected,text);}
void Identity(std::ostream& o){o<<"{\"source_fingerprint\":\""<<G4USIM_SOURCE_FINGERPRINT<<"\",\"probe_sha256\":\""<<G4USIM_PHASE_STATE_PROBE_SHA256<<"\",\"geant4_version_number\":"<<G4VERSION_NUMBER<<",\"build_configuration\":\""<<G4USIM_BUILD_CONFIGURATION<<"\",\"compiler\":\""<<G4USIM_COMPILER_ID<<"\",\"compiler_version\":\""<<G4USIM_COMPILER_VERSION<<"\",\"core_only\":";
#ifdef G4USIM_PHASE_STATE_CORE_ONLY
 o<<"true}";
#else
 o<<"false}";
#endif
}
class Detector final:public G4VUserDetectorConstruction {G4VPhysicalVolume* Construct()override{auto*s=new G4Box("world",1*m,1*m,1*m);auto*l=new G4LogicalVolume(s,G4NistManager::Instance()->FindOrBuildMaterial("G4_Galactic"),"world");return new G4PVPlacement(nullptr,{},l,"world",nullptr,false,0);}};
class Physics final:public G4VUserPhysicsList {void ConstructParticle()override{G4BosonConstructor().ConstructParticle();G4LeptonConstructor().ConstructParticle();G4BaryonConstructor().ConstructParticle();G4IonConstructor().ConstructParticle();}void ConstructProcess()override{AddTransportation();}void SetCuts()override{SetCutsWithDefault();}};
std::vector<std::unique_ptr<G4Event>> events;
G4Track* Track(G4ParticleDefinition* def,const PhaseSpaceParticle* record,double q){auto e=std::make_unique<G4Event>(static_cast<int>(events.size()));auto*v=new G4PrimaryVertex({0,0,0},0);auto*p=new G4PrimaryParticle(def);p->SetKineticEnergy(120*MeV);p->SetMomentumDirection({1,0,0});p->SetCharge(q);v->SetPrimary(p);e->AddPrimaryVertex(v);if(record)phase_space_replay::AttachPrimaryState(*p,*record,"component.csv");G4PrimaryTransformer transform;auto*ts=transform.GimmePrimaries(e.get());Check(ts&&ts->size()==1,"one real transformed track");auto*t=ts->at(0);ts->clear();events.push_back(std::move(e));return t;}
// Test-only creation of NEW default-state fixtures, never historical-state migration.
int SyntheticDefaultFixture(const std::filesystem::path& request,const std::string& purpose,const std::filesystem::path& root){
 if(purpose!="scoring-numeric"&&purpose!="j2-sources-physics"&&purpose!="f1-input-resources"&&purpose!="q1-results")throw std::runtime_error("unknown fixture purpose");
 std::ifstream input(request,std::ios::binary);if(!input)throw std::runtime_error("fixture request missing");
 const std::string bytes((std::istreambuf_iterator<char>(input)),{});
 const std::string marker="synthetic_sdk_default_state_fixture_request_v1\n";
 if(bytes.compare(0,marker.size(),marker)!=0)throw std::runtime_error("requires NEW synthetic fixture request marker, not historical CSV");
 if(!std::filesystem::create_directory(root))throw std::runtime_error("fixture output must be new");
 const auto logical=root/"logical-request.csv";
 {std::ofstream f(logical,std::ios::binary);f<<bytes.substr(marker.size());f.close();if(!f)throw std::runtime_error("request write failed");}
 auto histories=PhaseSpace::ReadHistories({logical.string()});
 for(const auto& h:histories)for(const auto& p:h)if(p.charge||p.dynamicState||p.parentID!=0||!((p.particle=="proton"&&p.pdg==2212)||(p.particle=="gamma"&&p.pdg==22)))throw std::runtime_error("fixture limited to new 15-column primary proton/gamma defaults");
 auto kernel=std::make_unique<G4RunManager>();kernel->SetUserInitialization(new Detector);kernel->SetUserInitialization(new Physics);kernel->Initialize();
 std::ostringstream csv;
 const auto emit=[&](const std::vector<std::string>& row){for(std::size_t i=0;i<row.size();++i){if(i)csv<<',';csv<<row[i];}csv<<'\n';};
 emit(PhaseSpace::Header());std::size_t rows=0;
 for(const auto& h:histories)for(auto record:h){
  // Match default primary construction; do not attach replay state or set charge.
  G4Event event(record.eventID);auto*vertex=new G4PrimaryVertex({record.x,record.y,record.z},record.time);
  G4ParticleDefinition*definition=nullptr;
  if(record.pdg==2212)definition=G4Proton::Definition();else definition=G4Gamma::Definition();
  auto*primary=new G4PrimaryParticle(definition);primary->SetKineticEnergy(record.kineticEnergy);primary->SetMomentumDirection({record.u,record.v,record.w});primary->SetWeight(record.weight);vertex->SetPrimary(primary);event.AddPrimaryVertex(vertex);
  G4PrimaryTransformer transformer;auto*tracks=transformer.GimmePrimaries(&event);
  if(!tracks||tracks->size()!=1)throw std::runtime_error("fixture Transformer must yield one primary");
  std::unique_ptr<G4Track> track(tracks->at(0));tracks->clear();const auto*d=track->GetDynamicParticle();
  if(d->GetDefinition()!=definition||d->GetPrimaryParticle()!=primary)throw std::runtime_error("fixture definition/primary mismatch");
  G4StepPoint point;point.SetMass(d->GetMass());point.SetCharge(d->GetCharge());point.SetPolarization(d->GetPolarization());
  record.charge=d->GetCharge();record.dynamicState=phase_space_replay::CaptureDynamicState(*track,point);
  phase_space_replay::ValidateForDefinition(record,*definition,"synthetic-default-fixture");emit(PhaseSpace::Row(record));++rows;
 }
 const auto output=csv.str();{std::ofstream f(root/"fixture.csv",std::ios::binary);f<<output;f.close();if(!f)throw std::runtime_error("fixture write failed");}
 std::ofstream receipt(root/"result.json");receipt<<"{\"kind\":\"synthetic_sdk_default_state_fixture\",\"no_transport\":true,\"purpose\":\""<<purpose<<"\",\"rows\":"<<rows<<",\"request_sha256\":\""<<input_provenance::Sha256(bytes)<<"\",\"output_sha256\":\""<<input_provenance::Sha256(output)<<"\",\"identity\":";Identity(receipt);receipt<<"}\n";receipt.close();if(!receipt)throw std::runtime_error("fixture receipt failed");return 0;
}
PhaseSpaceParticle Record(G4ParticleDefinition* def,int electrons,double charge){PhaseSpaceParticle p;p.pdg=def->GetPDGEncoding();p.particle=def->GetParticleName();p.inputLine=42;p.charge=charge;p.kineticEnergy=120*MeV;p.u=1;p.v=0;p.w=0;p.dynamicState.emplace();auto&s=*p.dynamicState;s.mass=def->GetPDGMass()+electrons*electron_mass_c2;s.electronOccupancy=std::vector<int>(20,0);s.electronOccupancy->at(0)=electrons;s.magneticMoment=0.125*(MeV/tesla);s.polarization={{0.1,0.2,0.3}};return p;}
void Verify(const G4Track&t,const PhaseSpaceParticle&p){const auto*d=t.GetDynamicParticle();const auto&s=*p.dynamicState;Check(d->GetCharge()==*p.charge,"dynamic charge");Check(d->GetMass()==s.mass,"dynamic mass");Check(d->GetMagneticMoment()==s.magneticMoment,"magnetic moment");Check(d->GetElectronOccupancy()!=nullptr&&d->GetElectronOccupancy()->GetSizeOfOrbit()==20,"actual occupancy object/layout");for(int i=0;i<20;++i)Check(d->GetOccupancy(i)==s.electronOccupancy->at(i),"orbit");Check(d->GetPolarization()==G4ThreeVector(s.polarization[0],s.polarization[1],s.polarization[2]),"polarization");const double e=d->GetKineticEnergy(),m=d->GetMass();Check(std::abs(t.GetVelocity()/c_light-std::sqrt(e*(e+2*m))/(e+m))<1e-14,"beta cache invalidated");}
#ifndef G4USIM_PHASE_STATE_CORE_ONLY
class FirstStep final:public G4UserSteppingAction {public:PhaseSpaceParticle expected;bool seen=false;double charge=0,mass=0,beta=0;explicit FirstStep(PhaseSpaceParticle p):expected(std::move(p)){}void UserSteppingAction(const G4Step*s)override{phase_space_replay::ObserveFirstStep(*s);Check(!seen,"single diagnostic step");seen=true;auto*pre=s->GetPreStepPoint();charge=pre->GetCharge();mass=pre->GetMass();beta=pre->GetVelocity()/c_light;Check(charge==*expected.charge&&mass==expected.dynamicState->mass,"real first step restored state");Verify(*s->GetTrack(),expected);s->GetTrack()->SetTrackStatus(fStopAndKill);}};
int CaptureFailure(const std::string& mode,const std::string& config,const std::filesystem::path& root) {
 if(!std::filesystem::create_directory(root))throw std::runtime_error("output must be new");
 SimulationManager sim;SimulationCommandLineOverrides overrides;overrides.mainConfig=config;overrides.outputDir=(root/"output").string();overrides.numThreads=1;overrides.seed=20261109;overrides.interactive=false;overrides.dryRun=false;
 sim.SetCommandLineOverrides(overrides);sim.Configure();sim.BeginRuntimeTracking();sim.Initialize();
 auto kernel=std::make_unique<G4RunManager>();struct Cleanup{~Cleanup(){events.clear();}}cleanup;
 kernel->SetUserInitialization(new Detector);kernel->SetUserInitialization(new Physics);kernel->Initialize();
 auto context=std::make_shared<WorkerRunContext>();context->sequentialOutput=sim.GetOutputManager();context->scoring=sim.GetScoringManager()->CloneForThread(context->sequentialOutput,0);
 Check(context->scoring->IsPhaseSpaceEnabled()&&context->scoring->GetPhaseSpaceVolume()=="world","real configured phase recorder");
 auto*ion=G4IonTable::GetIonTable()->GetIon(6,12,0.);std::unique_ptr<G4Track> t(Track(ion,nullptr,2));
 auto*d=const_cast<G4DynamicParticle*>(t->GetDynamicParticle());
 if(mode=="--capture-decay-time")d->SetPreAssignedDecayProperTime(0.);else d->SetPreAssignedDecayProducts(new G4DecayProducts(*d));
 auto*navigator=G4TransportationManager::GetTransportationManager()->GetNavigatorForTracking();navigator->LocateGlobalPointAndSetup({0,0,0});
 t->SetTouchableHandle(navigator->CreateTouchableHistoryHandle());
 G4Step step;step.InitializeStep(t.get());step.GetPostStepPoint()->SetTouchableHandle(t->GetTouchableHandle());step.GetPostStepPoint()->SetStepStatus(fGeomBoundary);
 SteppingAction action(context);action.UserSteppingAction(&step); // production callback, explicitly synthetic boundary injection
 Check(sim.GetOutputManager()->HasOutputFailure()&&t->GetTrackStatus()==fStopAndKill,"callback latched/stopped without escaping");
 const auto first=sim.GetOutputManager()->GetOutputFailure();Check(first.stage=="phase_space_capture"&&first.message.find("preassigned decay")!=std::string::npos,"capture first cause");
 const bool finalized=sim.FinalizeRunSummary("failed",1,"failed");
 (void)finalized;Check(sim.GetOutputManager()->GetOutputFailure().message==first.message,"capture finalize retains first cause");
 Check(std::filesystem::is_regular_file(root/"output/run_summary.txt"),"production failure summary exists");
 std::ofstream result(root/"result.json");result<<"{\"status\":\"expected_failure\",\"callback_invoked\":true,\"synthetic_boundary\":true,\"beam_on_called\":false,\"checks\":"<<checks<<",\"identity\":";Identity(result);result<<"}\n";result.close();if(!result)throw std::runtime_error("capture result write failed");return 1;
}
void StackTests(G4ParticleDefinition*ion,const PhaseSpaceParticle&p,const std::filesystem::path&root){
 auto context=std::make_shared<WorkerRunContext>();context->output=std::make_unique<OutputManager>();context->output->SetOutputDir((root/"output").string());G4StackManager stack;stack.SetNumberOfAdditionalWaitingStacks(1);stack.SetUserStackingAction(new PhaseSpaceStackingAction(context));
 for(auto classification:{fUrgent,fWaiting,fPostpone,fWaiting_1}){stack.SetDefaultClassification(ion,classification);auto*t=Track(ion,&p,*p.charge);stack.PushOneTrack(t);Check((classification==fUrgent?stack.GetNUrgentTrack():classification==fWaiting?stack.GetNWaitingTrack():classification==fWaiting_1?stack.GetNWaitingTrack(1):stack.GetNPostponedTrack())==1,"default classification preserved");Verify(*t,p);if(classification!=fUrgent)stack.TransferStackedTracks(classification,fUrgent);const_cast<G4DynamicParticle*>(t->GetDynamicParticle())->SetCharge(3.25);stack.SetDefaultClassification(ion,fWaiting);stack.ReClassify();Check(stack.GetNWaitingTrack()==1&&t->GetDynamicParticle()->GetCharge()==3.25,"reclassification preserves evolved state/current default");stack.TransferStackedTracks(fWaiting,fUrgent);G4VTrajectory*trajectory=nullptr;auto*pop=stack.PopNextTrack(&trajectory);Check(pop==t,"same track");delete pop;}
 stack.SetDefaultClassification(ion,fWaiting);
 auto* original=Track(ion,&p,*p.charge);phase_space_replay::RestoreBeforeTracking(*original);
 auto* secondary=new G4Track(new G4DynamicParticle(*original->GetDynamicParticle()),0,{0,0,0});secondary->SetParentID(1);
 const auto secondaryQ=secondary->GetDynamicParticle()->GetCharge();stack.PushOneTrack(secondary);
 Check(!context->output->HasOutputFailure()&&stack.GetNWaitingTrack()==1&&secondary->GetDynamicParticle()->GetCharge()==secondaryQ,"copied secondary default/no failure");
 stack.TransferStackedTracks(fWaiting,fUrgent);G4VTrajectory* secondaryTrajectory=nullptr;delete stack.PopNextTrack(&secondaryTrajectory);delete original;
 stack.SetDefaultClassification(ion,fUrgent);auto*t=Track(ion,&p,*p.charge);stack.PushOneTrack(t);G4VTrajectory*trajectory=nullptr;t=stack.PopNextTrack(&trajectory);G4TrackingManager manager;auto*observer=new FirstStep(p);manager.SetUserAction(observer);manager.ProcessOneTrack(t);Check(observer->seen,"real first step observed");std::ofstream first(root/"first-step.json");first<<std::setprecision(17)<<"{\"charge_eplus\":"<<observer->charge/eplus<<",\"mass_MeV\":"<<observer->mass/MeV<<",\"beta\":"<<observer->beta<<",\"transport_steps\":1}\n";first.close();Check(bool(first),"first step receipt");delete t;
 auto*bad=Track(ion,&p,*p.charge);bad->IncrementCurrentStepNumber();stack.PushOneTrack(bad);Check(context->output->HasOutputFailure(),"failure latched");const auto failure=context->output->GetOutputFailure();Check(failure.stage=="phase_space_restore_first_track"&&failure.message.find("component.csv")!=std::string::npos&&failure.message.find("42")!=std::string::npos,"first cause file/line");stack.PushOneTrack(Track(ion,nullptr,2));Check(stack.GetNTotalTrack()==0,"remaining primary blocked");Check(context->output->GetOutputFailure().message==failure.message,"first cause retained");
}
#endif
}
int main(int argc,char**argv){if(argc==2&&std::string(argv[1])=="--identity"){Identity(std::cout);std::cout<<'\n';return 0;}try{
 if(argc==5&&std::string(argv[1])=="--synthetic-default-fixture")return SyntheticDefaultFixture(std::filesystem::absolute(argv[2]),argv[3],std::filesystem::absolute(argv[4]));
#ifndef G4USIM_PHASE_STATE_CORE_ONLY
 if(argc==4 && (std::string(argv[1])=="--capture-decay-time"||std::string(argv[1])=="--capture-decay-products"))return CaptureFailure(argv[1],argv[2],std::filesystem::absolute(argv[3]));
#endif
 if(argc!=2)throw std::runtime_error("usage: phaseSpaceStateCheck NEW_OUTPUT_DIR | --identity");const std::filesystem::path root=std::filesystem::absolute(argv[1]);if(!std::filesystem::create_directory(root))throw std::runtime_error("output must be new");auto kernel=std::make_unique<G4RunManager>();struct EventCleanup{~EventCleanup(){events.clear();}} eventCleanup;kernel->SetUserInitialization(new Detector);kernel->SetUserInitialization(new Physics);kernel->Initialize();auto*ion=G4IonTable::GetIonTable()->GetIon(6,12,0.);const auto definitionMass=ion->GetPDGMass(),definitionCharge=ion->GetPDGCharge();auto p=Record(ion,4,5.96566726277173),q=Record(ion,0,0.);
 std::unique_ptr<G4Track>a(Track(ion,&p,*p.charge)),b(Track(ion,&q,*q.charge));Check(a->GetDynamicParticle()->GetCharge()!=*p.charge,"Transformer distortion exercised");(void)a->GetVelocity();(void)b->GetVelocity();Check(phase_space_replay::RestoreBeforeTracking(*a)==phase_space_replay::RestoreResult::Restored,"first restoration");Verify(*a,p);phase_space_replay::RestoreBeforeTracking(*b);Verify(*b,q);Verify(*a,p);Check(ion->GetPDGMass()==definitionMass&&ion->GetPDGCharge()==definitionCharge,"definition unchanged");const_cast<G4DynamicParticle*>(a->GetDynamicParticle())->SetCharge(3.25);a->IncrementCurrentStepNumber();Check(phase_space_replay::RestoreBeforeTracking(*a)==phase_space_replay::RestoreResult::AlreadyRestored&&a->GetDynamicParticle()->GetCharge()==3.25,"repeat never reapplies");
 std::unique_ptr<G4Track> copiedSecondary(new G4Track(new G4DynamicParticle(*a->GetDynamicParticle()),0,{0,0,0}));
 copiedSecondary->SetParentID(1);const auto copiedQ=copiedSecondary->GetDynamicParticle()->GetCharge(),copiedMass=copiedSecondary->GetDynamicParticle()->GetMass();
 Check(copiedSecondary->GetDynamicParticle()->GetPrimaryParticle()==a->GetDynamicParticle()->GetPrimaryParticle(),"real SDK copy retains primary pointer");
 Check(phase_space_replay::RestoreBeforeTracking(*copiedSecondary)==phase_space_replay::RestoreResult::NotMarked&&copiedSecondary->GetDynamicParticle()->GetCharge()==copiedQ&&copiedSecondary->GetDynamicParticle()->GetMass()==copiedMass,"SDK copied secondary untouched");
 std::unique_ptr<G4Track> copiedPrimary(new G4Track(new G4DynamicParticle(*a->GetDynamicParticle()),0,{0,0,0}));
 Reject([&]{phase_space_replay::RestoreBeforeTracking(*copiedPrimary);},"same-primary another parent0 track rejects");
 std::unique_ptr<G4Track>gps(Track(ion,nullptr,2));const auto gpsMass=gps->GetDynamicParticle()->GetMass();Check(phase_space_replay::RestoreBeforeTracking(*gps)==phase_space_replay::RestoreResult::NotMarked,"GPS unchanged");gps->SetParentID(2);Check(phase_space_replay::RestoreBeforeTracking(*gps)==phase_space_replay::RestoreResult::NotMarked&&gps->GetDynamicParticle()->GetMass()==gpsMass&&gps->GetDynamicParticle()->GetCharge()==2,"secondary unchanged");std::unique_ptr<G4Track>late(Track(ion,&p,*p.charge));late->IncrementCurrentStepNumber();Reject([&]{phase_space_replay::RestoreBeforeTracking(*late);},"started track rejects");
 std::unique_ptr<G4Track> cache(Track(ion,&p,*p.charge));auto*cd=const_cast<G4DynamicParticle*>(cache->GetDynamicParticle());const auto beforeBeta=cd->GetBeta();
 cd->AddElectron(0,4);Check(cd->GetMass()==p.dynamicState->mass,"electron update already reached final mass");
 cd->SetMass(p.dynamicState->mass);cd->SetKineticEnergy(120*MeV);
 Check(cd->GetBeta()==beforeBeta,"same mass/E setters demonstrably leave stale beta");
 const double expectedBeta=std::sqrt(120.*(120.+2.*cd->GetMass()))/(120.+cd->GetMass());Check(std::abs(beforeBeta-expectedBeta)>1e-8,"negative control beta actually stale");
 phase_space_replay::RestoreBeforeTracking(*cache);Verify(*cache,p);
 G4StepPoint post;post.SetMass(cd->GetMass());post.SetCharge(cd->GetCharge());post.SetPolarization(cd->GetPolarization());
 cd->SetProperTime(12*ns);auto captured=phase_space_replay::CaptureDynamicState(*cache,post);Check(captured.mass==cd->GetMass(),"ordinary proper time accepted");
 cd->SetPreAssignedDecayProperTime(0);Reject([&]{phase_space_replay::CaptureDynamicState(*cache,post);},"preassigned decay time rejects");cd->SetPreAssignedDecayProperTime(-1);
 cd->SetPreAssignedDecayProducts(new G4DecayProducts(*cd));Reject([&]{phase_space_replay::CaptureDynamicState(*cache,post);},"preassigned products reject");
 delete cd->GetPreAssignedDecayProducts();cd->SetPreAssignedDecayProducts(nullptr);
 auto*anti=G4AntiAlpha::Definition();std::unique_ptr<G4Track> antiTrack(Track(anti,nullptr,anti->GetPDGCharge()));const auto*ad=antiTrack->GetDynamicParticle();
 G4StepPoint antiPost;antiPost.SetMass(ad->GetMass());antiPost.SetCharge(ad->GetCharge());antiPost.SetPolarization(ad->GetPolarization());auto antiState=phase_space_replay::CaptureDynamicState(*antiTrack,antiPost);
 if(!ad->GetElectronOccupancy()){Check(!antiState.electronOccupancy,"actual anti-ion none preserved");auto antiRecord=Record(anti,0,ad->GetCharge());antiRecord.dynamicState=antiState;phase_space_replay::ValidateForDefinition(antiRecord,*anti,"anti.csv");
 std::unique_ptr<G4Track> antiReplay(Track(anti,&antiRecord,*antiRecord.charge));phase_space_replay::RestoreBeforeTracking(*antiReplay);Check(!antiReplay->GetDynamicParticle()->GetElectronOccupancy()&&antiReplay->GetDynamicParticle()->GetCharge()==*antiRecord.charge,"actual SDK anti-ion none preserved on restoration");}
 std::ofstream noneReport(root/"none-conversion.csv");noneReport<<"particle,charge_eplus,has_occupancy,total_occupancy,mass_MeV\n"<<std::setprecision(17);
 for(auto* definition:{static_cast<G4ParticleDefinition*>(G4Proton::Definition()),ion}) {
   std::unique_ptr<G4Track> stripped(Track(definition,nullptr,definition->GetPDGCharge()));const auto* d=stripped->GetDynamicParticle();
   noneReport<<definition->GetParticleName()<<','<<d->GetCharge()/eplus<<','<<(d->GetElectronOccupancy()!=nullptr)<<','<<d->GetTotalOccupancy()<<','<<d->GetMass()/MeV<<'\n';
   Check(d->GetCharge()==definition->GetPDGCharge(),"fully stripped actual dynamic charge");
   auto noneRecord=Record(definition,0,d->GetCharge());noneRecord.dynamicState->electronOccupancy.reset();
   std::unique_ptr<G4Track> noneReplay(Track(definition,&noneRecord,*noneRecord.charge));phase_space_replay::RestoreBeforeTracking(*noneReplay);
   Check(!noneReplay->GetDynamicParticle()->GetElectronOccupancy()&&noneReplay->GetDynamicParticle()->GetMass()==noneRecord.dynamicState->mass,"fully stripped none restored without fabrication");
 }
 noneReport.close();Check(bool(noneReport),"none observation saved");
 auto zeroArray=Record(ion,0,6.);std::unique_ptr<G4Track> arrayTrack(Track(ion,&zeroArray,6.));
 Check(!arrayTrack->GetDynamicParticle()->GetElectronOccupancy(),"zero-array starts as real none");phase_space_replay::RestoreBeforeTracking(*arrayTrack);Verify(*arrayTrack,zeroArray);
 auto unsafe=p;unsafe.dynamicState.reset();auto*electron=G4Electron::Definition();unsafe.pdg=11;for(double charge:{1e100,-1e100,2147483648.,-2147483648.}){unsafe.charge=charge;Reject([&]{phase_space_replay::ValidateForDefinition(unsafe,*electron,"unsafe.csv");},"unsafe Transformer charge rejected before conversion");}
 unsafe=p;unsafe.dynamicState.reset();unsafe.pdg=11;unsafe.charge=2147483647.75;phase_space_replay::ValidateForDefinition(unsafe,*electron,"safe-bound.csv");Check(true,"safe positive truncation bound (no conversion executed)");
 unsafe.charge=-2147483647.75;phase_space_replay::ValidateForDefinition(unsafe,*electron,"safe-bound.csv");Check(true,"safe Z-minus-charge bound (no conversion executed)");
 std::unique_ptr<G4Track> missingRestore(Track(ion,&p,*p.charge));G4Step missingStep;missingStep.SetTrack(missingRestore.get());missingRestore->IncrementCurrentStepNumber();
 Reject([&]{phase_space_replay::ObserveFirstStep(missingStep);},"production first-step guard rejects missing restoration");
 auto huge=p;huge.dynamicState->mass=1e308;Reject([&]{phase_space_replay::ValidateForDefinition(huge,*ion,"huge-mass.csv");},"finite huge mass rejected before conversion");
 huge=p;huge.kineticEnergy=1e308;Reject([&]{phase_space_replay::ValidateForDefinition(huge,*ion,"huge-energy.csv");},"finite huge energy rejected before conversion");
 auto invalid=p;invalid.dynamicState->electronOccupancy.reset();phase_space_replay::ValidateForDefinition(invalid,*ion,"none.csv");std::unique_ptr<G4Track> fractionalNone(Track(ion,&invalid,*invalid.charge));Check(fractionalNone->GetDynamicParticle()->GetPrimaryParticle()->GetCharge()==std::numeric_limits<double>::max(),"complete v3 construction uses sentinel");phase_space_replay::RestoreBeforeTracking(*fractionalNone);Check(!fractionalNone->GetDynamicParticle()->GetElectronOccupancy()&&fractionalNone->GetDynamicParticle()->GetCharge()==*invalid.charge,"fractional C12 none restored");
 auto*alpha=G4Alpha::Definition();auto alphaState=Record(alpha,0,1.99);alphaState.dynamicState->electronOccupancy.reset();std::unique_ptr<G4Track> alphaTrack(Track(alpha,&alphaState,1.99));phase_space_replay::RestoreBeforeTracking(*alphaTrack);Check(!alphaTrack->GetDynamicParticle()->GetElectronOccupancy()&&alphaTrack->GetDynamicParticle()->GetCharge()==1.99,"fractional alpha none restored");
 std::unique_ptr<G4Track> fractionalControl(Track(ion,nullptr,5.96566726277173));Check(fractionalControl->GetDynamicParticle()->GetCharge()==5&&fractionalControl->GetDynamicParticle()->GetTotalOccupancy()==1,"non-sentinel fractional conversion control");invalid=p;invalid.dynamicState.reset();Reject([&]{phase_space_replay::ValidateForDefinition(invalid,*ion,"v2.csv");},"v2 ion");invalid=p;invalid.dynamicState->mass=std::numeric_limits<double>::quiet_NaN();Reject([&]{PhaseSpace::ValidateDynamicState(*invalid.dynamicState,"nan");},"nonfinite mass");invalid=p;invalid.dynamicState->electronOccupancy->at(0)=-1;Reject([&]{PhaseSpace::ValidateDynamicState(*invalid.dynamicState,"negative");},"negative occupancy");invalid=p;invalid.dynamicState->polarization={{2,0,0}};Reject([&]{PhaseSpace::ValidateDynamicState(*invalid.dynamicState,"polarization");},"polarization");
 std::ofstream csv(root/"roundtrip.csv");const auto line=[&](const std::vector<std::string>&v){for(std::size_t i=0;i<v.size();++i){if(i)csv<<',';csv<<v[i];}csv<<'\n';};line(PhaseSpace::Header());line(PhaseSpace::Row(p));csv.close();auto reread=PhaseSpace::ReadHistories({(root/"roundtrip.csv").string()});Check(reread.size()==1&&reread[0].size()==1&&reread[0][0].dynamicState->electronOccupancy==p.dynamicState->electronOccupancy&&reread[0][0].charge==p.charge,"v3 roundtrip");
#ifndef G4USIM_PHASE_STATE_CORE_ONLY
 StackTests(ion,p,root);
#endif
 std::ofstream result(root/"result.json");result<<"{\"status\":\"pass\",\"checks\":"<<checks<<",\"identity\":";Identity(result);result<<"}\n";result.close();if(!result)throw std::runtime_error("result write failed");std::cout<<"Phase space state checks passed: "<<checks<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<"phaseSpaceStateCheck: "<<e.what()<<'\n';return 1;}}
