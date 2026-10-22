#pragma once

// Displacement damage function NIEL(E) of one particle in one material
// (roadmap B2), read from a user-supplied CSV:
//
//   # comment lines start with '#'
//   energy_MeV,niel_MeV_cm2_g
//   0.1,0.0123
//   ...
//
// Energies must be positive and strictly increasing, NIEL values finite and
// >= 0, at least two rows. Between nodes NIEL is interpolated log-log (linear
// where a node value is zero); outside [first, last] energy the table gives no
// value and the caller counts the step as out of range.

#include <memory>
#include <string>
#include <vector>

class NielTable {
public:
    static std::shared_ptr<const NielTable> Load(const std::string& path);

    // energy in Geant4 units; returns false outside the tabulated range.
    bool Evaluate(double energy, double& nielMeVcm2PerG) const;

    const std::string& GetFile() const { return file_; }
    double MinEnergy() const { return energies_.front(); }   // Geant4 units
    double MaxEnergy() const { return energies_.back(); }
    std::size_t Size() const { return energies_.size(); }

private:
    std::string file_;
    std::vector<double> energies_;  // Geant4 units
    std::vector<double> values_;    // MeV cm2/g
};
