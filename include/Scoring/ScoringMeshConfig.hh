#pragma once

// INI front end for Geant4 command-based scoring meshes.
//
//   [scoring.mesh.<mesh>]            shape, size, bins, center
//   [scoring.mesh.<mesh>.<quantity>] type, unit, particles, energy_min, energy_max
//
// The sections are translated into the equivalent /score/ commands, which main
// applies once G4ScoringManager exists and before any user macro runs, so
// INI meshes and macro meshes behave identically.

#include <string>
#include <vector>

class ConfigManager;

namespace ScoringMeshConfig {

// Validates the sections and returns the /score/ commands in order.
// Throws std::runtime_error with the offending section/key on invalid input.
std::vector<std::string> BuildCommands(const ConfigManager& config);

// Keys accepted in the two section kinds (for unknown-key diagnostics).
const std::vector<std::string>& MeshKeys();
const std::vector<std::string>& QuantityKeys();

}  // namespace ScoringMeshConfig
