#pragma once

// Locating the Geant4 physics data of an installed package (roadmap D).
//
// The package does not ship the Geant4 data. Geant4 itself resolves each dataset
// from its environment variable (G4LEDATA, ...) or, when that is unset, from
// GEANT4_DATA_DIR/<versioned folder> or the Geant4 install prefix compiled into
// the libraries. ApplyGeant4DataFile() lets an installed copy point at an existing
// data folder without setting environment variables: when neither GEANT4_DATA_DIR
// nor any per-dataset variable is set, the first non-comment line of
// geant4-data.txt next to the executable becomes GEANT4_DATA_DIR for this process.

#include <ostream>
#include <string>
#include <vector>

namespace Geant4DataLocator {

struct DatasetStatus {
    std::string env;        // e.g. G4LEDATA
    std::string folder;     // versioned folder name, e.g. G4EMLOW8.6.1
    bool required = false;  // needed by the standard EM/hadronic/decay physics
    std::string path;       // resolved directory, empty when missing
};

// Returns a human-readable note describing what was applied (empty if nothing).
std::string ApplyGeant4DataFile(const char* argv0);

// Status of every dataset of the Geant4 version this program was built with.
std::vector<DatasetStatus> CheckDatasets();

// JSON report (schema g4usim_geant4_data_v1); returns true if all required datasets exist.
bool WriteReport(std::ostream& out, const std::string& note);

}  // namespace Geant4DataLocator
