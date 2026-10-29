#pragma once

// Phase-space files (roadmap A4): particles crossing into a chosen physical volume
// (state at the boundary, before any interaction inside),
// written per worker as phase_space_tN[_rR].csv (schema phase_space_csv_v1) and
// read back as a primary source ([source] phase_space_file).
//
// Columns: runID, eventID, trackID, parentID, particle, pdg, x_mm, y_mm, z_mm,
// u, v, w (unit direction), kineticEnergy_MeV, time_ns, weight.
// Rows with the same (runID, eventID) that follow each other form one history;
// worker files of one run can simply be concatenated (event IDs are unique
// across the threads of a run).

#include "Config/InputProvenance.hh"
#include <string>
#include <vector>

struct PhaseSpaceParticle {
    int runID = 0;
    int eventID = 0;
    int trackID = 0;
    int parentID = 0;
    std::string particle;
    int pdg = 0;
    double x = 0.0, y = 0.0, z = 0.0;   // Geant4 internal units
    double u = 0.0, v = 0.0, w = 1.0;
    double kineticEnergy = 0.0;
    double time = 0.0;
    double weight = 1.0;
};

namespace PhaseSpace {

const std::vector<std::string>& Header();
std::vector<std::string> Row(const PhaseSpaceParticle& particle);
// Reads and validates the files in order; throws with file and line on error.
// Optional acceptedInputs receives path/hash metadata (bytes released), only on success.
std::vector<std::vector<PhaseSpaceParticle>> ReadHistories(const std::vector<std::string>& files,
    std::vector<input_provenance::InputFile>* acceptedInputs = nullptr);

}  // namespace PhaseSpace
