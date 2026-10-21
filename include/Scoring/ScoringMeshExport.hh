#pragma once

// Export of Geant4 command-based scoring meshes (/score/...).
//
// Geant4 accumulates each mesh cell as a G4StatDouble over events (sum of the
// per-event values, sum of their squares, number of contributing events) and
// merges worker meshes into the master at the end of a run. These helpers read
// the merged result on the master (or sequential) thread.

#include <string>
#include <vector>

class RunSummary;

namespace ScoringMeshExport {

struct Cell {
    std::string mesh;
    std::string quantity;   // primitive scorer name as given to /score/quantity/...
    std::string unit;       // unit of value/sum, e.g. "Gy", "MeV", "cm-2"
    int i0 = 0;             // bin indices along the mesh's three division axes
    int i1 = 0;
    int i2 = 0;
    double sum = 0.0;       // sum over events of the per-event cell value [unit]
    double sumSquares = 0.0;// sum over events of (per-event value)^2 [unit^2]
    int entries = 0;        // number of events that contributed to the cell
};

struct MeshInfo {
    std::string name;
    std::string shape;      // box, cylinder, ...
    int bins[3] = {0, 0, 0};
    std::string axes[3];
    double sizeMm[3] = {0.0, 0.0, 0.0};   // half-lengths (box) or Geant4 mesh size parameters
    double centerMm[3] = {0.0, 0.0, 0.0};
    std::vector<std::string> quantities;
};

// True once G4ScoringManager exists (created by main) and holds at least one mesh.
bool HasMeshes();
std::vector<MeshInfo> DescribeMeshes();
// Non-empty cells of every quantity of every mesh, in deterministic order.
std::vector<Cell> CollectCells();
// Relative statistical error of the run total, Geant4/MCNP convention:
// R = sqrt(sum2/sum^2 - 1/N) with N the number of events in the run.
double RelativeError(double sum, double sumSquares, long long events);
// Record mesh layout in the run summary (and thus run_metadata.json).
void RecordInSummary(RunSummary& summary);

}  // namespace ScoringMeshExport
