#pragma once

// Per-region physics settings (roadmap A6): [physics.region.<name>] in the
// main INI or /AIHL/physics/setRegionCut. Lengths, times and energies are in
// Geant4 internal units; 0 means "not set".

#include <map>
#include <string>
#include <vector>

struct RegionPhysicsSettings {
    std::map<std::string, double> cuts;   // production range cuts: gamma, e-, e+, proton
    double maxStep = 0.0;                 // G4UserLimits (G4StepLimiter)
    double maxTrackLength = 0.0;          // G4UserLimits (G4UserSpecialCuts)
    double maxTime = 0.0;
    double minKineticEnergy = 0.0;
    std::vector<std::string> volumes;     // logical volumes that become region roots

    bool HasUserLimits() const
    {
        return maxStep > 0.0 || maxTrackLength > 0.0 || maxTime > 0.0 || minKineticEnergy > 0.0;
    }
};
