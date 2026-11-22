#pragma once
class G4Event;
class G4Run;
class G4Step;
class OutputManager;
namespace engineering_event {
void BeginRun(const G4Run&);
void BeforePrimary(const G4Event&,OutputManager&);
void Generated(const G4Event&,OutputManager&);
void Begin(const G4Event&,OutputManager&);
void Observe(const G4Step&,OutputManager&);
void End(const G4Event&,OutputManager&);
void EndRun(const G4Run&,OutputManager&);
}
