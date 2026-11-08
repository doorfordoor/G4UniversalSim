#pragma once
#include <memory>
class G4RunManager;
class OutputManager;

// Composition-root adapter. The failure registry must outlive the run manager.
// Explicit sequential mode is also available in an MT-capable Geant4 build.
std::unique_ptr<G4RunManager> CreateSimulationRunManager(
    const OutputManager* output, int threads, bool sequential = false);
