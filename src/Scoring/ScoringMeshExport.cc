#include "Scoring/ScoringMeshExport.hh"

#include "Output/RunSummary.hh"

#include "G4ScoringManager.hh"
#include "G4StatDouble.hh"
#include "G4SystemOfUnits.hh"
#include "G4THitsMap.hh"
#include "G4VScoringMesh.hh"

#include <algorithm>
#include <cmath>
#include <sstream>

namespace {

std::string ShapeName(G4VScoringMesh::MeshShape shape)
{
    switch (shape) {
    case G4VScoringMesh::MeshShape::box: return "box";
    case G4VScoringMesh::MeshShape::cylinder: return "cylinder";
    case G4VScoringMesh::MeshShape::probe: return "probe";
    case G4VScoringMesh::MeshShape::realWorldLogVol: return "real_world_volume";
    default: return "unknown";
    }
}

std::string Triple(const double values[3])
{
    std::ostringstream out;
    out << values[0] << ',' << values[1] << ',' << values[2];
    return out.str();
}

}  // namespace

namespace ScoringMeshExport {

bool HasMeshes()
{
    auto* manager = G4ScoringManager::GetScoringManagerIfExist();
    return manager && manager->GetNumberOfMesh() > 0;
}

std::vector<MeshInfo> DescribeMeshes()
{
    std::vector<MeshInfo> result;
    auto* manager = G4ScoringManager::GetScoringManagerIfExist();
    if (!manager) return result;
    for (std::size_t index = 0; index < manager->GetNumberOfMesh(); ++index) {
        G4VScoringMesh* mesh = manager->GetMesh(static_cast<G4int>(index));
        if (!mesh) continue;
        MeshInfo info;
        info.name = mesh->GetWorldName();
        info.shape = ShapeName(mesh->GetShape());
        mesh->GetNumberOfSegments(info.bins);
        G4String axes[3];
        mesh->GetDivisionAxisNames(axes);
        const G4ThreeVector size = mesh->GetSize();
        const G4ThreeVector center = mesh->GetTranslation();
        for (int axis = 0; axis < 3; ++axis) {
            info.axes[axis] = axes[axis];
            info.sizeMm[axis] = size[axis] / mm;
            info.centerMm[axis] = center[axis] / mm;
        }
        for (const auto& item : mesh->GetScoreMap()) info.quantities.push_back(item.first);
        result.push_back(info);
    }
    return result;
}

std::vector<Cell> CollectCells()
{
    std::vector<Cell> cells;
    auto* manager = G4ScoringManager::GetScoringManagerIfExist();
    if (!manager) return cells;
    for (std::size_t index = 0; index < manager->GetNumberOfMesh(); ++index) {
        G4VScoringMesh* mesh = manager->GetMesh(static_cast<G4int>(index));
        if (!mesh) continue;
        G4int bins[3] = {0, 0, 0};
        mesh->GetNumberOfSegments(bins);
        const int stride1 = std::max(1, bins[2]);
        const int stride0 = std::max(1, bins[1]) * stride1;
        for (const auto& item : mesh->GetScoreMap()) {
            const G4String& quantity = item.first;
            G4VScoringMesh::RunScore* score = item.second;
            if (!score || !score->GetMap()) continue;
            const G4double unitValue = mesh->GetPSUnitValue(quantity);
            const std::string unit = mesh->GetPSUnit(quantity);
            const double scale = unitValue > 0.0 ? 1.0 / unitValue : 1.0;
            for (const auto& entry : *score->GetMap()) {
                if (!entry.second) continue;
                const int key = entry.first;
                const G4StatDouble& stat = *entry.second;
                Cell cell;
                cell.mesh = mesh->GetWorldName();
                cell.quantity = quantity;
                cell.unit = unit;
                cell.i0 = key / stride0;
                cell.i1 = (key % stride0) / stride1;
                cell.i2 = key % stride1;
                cell.sum = stat.sum_wx() * scale;
                cell.sumSquares = stat.sum_wx2() * scale * scale;
                cell.entries = stat.n();
                cells.push_back(cell);
            }
        }
    }
    return cells;
}

double RelativeError(double sum, double sumSquares, long long events)
{
    if (events <= 0 || sum == 0.0) return 0.0;
    const double value = sumSquares / (sum * sum) - 1.0 / static_cast<double>(events);
    return value > 0.0 ? std::sqrt(value) : 0.0;
}

void RecordInSummary(RunSummary& summary)
{
    const auto meshes = DescribeMeshes();
    summary.Set("scoring_mesh_count", static_cast<int>(meshes.size()));
    for (const MeshInfo& mesh : meshes) {
        const std::string prefix = "scoring_mesh_" + mesh.name + "_";
        summary.Set(prefix + "shape", mesh.shape);
        std::ostringstream bins;
        bins << mesh.bins[0] << ',' << mesh.bins[1] << ',' << mesh.bins[2];
        summary.Set(prefix + "bins", bins.str());
        summary.Set(prefix + "axes", mesh.axes[0] + "," + mesh.axes[1] + "," + mesh.axes[2]);
        summary.Set(prefix + "size_mm", Triple(mesh.sizeMm));
        summary.Set(prefix + "center_mm", Triple(mesh.centerMm));
        std::string quantities;
        for (const std::string& quantity : mesh.quantities) {
            quantities += (quantities.empty() ? "" : ",") + quantity;
        }
        summary.Set(prefix + "quantities", quantities);
    }
}

}  // namespace ScoringMeshExport
