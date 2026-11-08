#include "Core/RuntimeExecution.hh"
#include "G4RunManager.hh"
#include "G4UImanager.hh"
#include <cstdlib>
#include <stdexcept>

namespace runtime {

Geant4Execution::Geant4Execution(G4RunManager* manager) noexcept : manager_(manager) {}

G4RunManager* Geant4Execution::RunManager() const
{
    return manager_ ? manager_ : G4RunManager::GetRunManager();
}

int Geant4Execution::ApplyCommand(const std::string& command)
{
    // Explicit test opt-in at a single harmless echo marker. This exercises
    // the production main catch/finalization path without a second dispatcher.
    if (command == "/control/echo G4USIM_TEST_RUNTIME_DISPATCH") {
        const char* requested = std::getenv("G4USIM_TEST_RUNTIME_FAULT");
        const std::string fault = requested ? requested : "";
        if (fault == "throw_std") throw std::runtime_error("Injected runtime dispatch exception");
        if (fault == "throw_nonstd") throw 17031;
    }
    return G4UImanager::GetUIpointer()->ApplyCommand(command.c_str());
}

void Geant4Execution::InitializeKernel()
{
    RunManager()->Initialize();
}

void Geant4Execution::BeamOn(int events)
{
    RunManager()->BeamOn(events);
}

}  // namespace runtime
