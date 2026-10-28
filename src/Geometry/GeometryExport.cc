#include "Geometry/GeometryExport.hh"

#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4Polyhedron.hh"
#include "G4ReplicaNavigation.hh"
#include "G4SystemOfUnits.hh"
#include "G4Transform3D.hh"
#include "G4TransportationManager.hh"
#include "G4VPVParameterisation.hh"
#include "G4VPhysicalVolume.hh"
#include "G4VSensitiveDetector.hh"
#include "G4VSolid.hh"

#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace {

std::string Escape(const std::string& text)
{
    std::string out;
    for (char c : text) {
        if (c == '"' || c == '\\') out += '\\';
        out += c;
    }
    return out;
}

class Writer {
public:
    Writer(std::ostream& out, int maxDepth) : out_(out), maxDepth_(maxDepth) {}

    void Visit(G4VPhysicalVolume* physical, int copyNo, const G4Transform3D& parent, const std::string& parentPath,
               int depth, G4VSolid* solidOverride, G4Material* materialOverride)
    {
        G4LogicalVolume* logical = physical->GetLogicalVolume();
        const G4Transform3D local(physical->GetObjectRotationValue(), physical->GetObjectTranslation());
        const G4Transform3D global = parent * local;
        const std::string path = parentPath + "/" + physical->GetName() + "#" + std::to_string(copyNo);
        G4VSolid* solid = solidOverride ? solidOverride : logical->GetSolid();
        G4Material* material = materialOverride ? materialOverride : logical->GetMaterial();
        Emit(physical, logical, solid, material, copyNo, depth, path, global);
        if (maxDepth_ >= 0 && depth >= maxDepth_) return;
        for (std::size_t i = 0; i < logical->GetNoDaughters(); ++i) {
            G4VPhysicalVolume* daughter = logical->GetDaughter(static_cast<G4int>(i));
            const int copies = daughter->GetMultiplicity();
            if (daughter->IsReplicated()) {
                // Set the daughter's per-copy transformation (and solid) as
                // navigation would, then restore copy 0 for safety.
                EAxis axis = kUndefined;
                G4int count = 0;
                G4double width = 0.0, offset = 0.0;
                G4bool consuming = false;
                daughter->GetReplicationData(axis, count, width, offset, consuming);
                G4VPVParameterisation* parameterisation = daughter->GetParameterisation();
                for (int copy = 0; copy < copies; ++copy) {
                    G4VSolid* copySolid = nullptr;
                    G4Material* copyMaterial = nullptr;
                    if (parameterisation) {
                        parameterisation->ComputeTransformation(copy, daughter);
                        copySolid = parameterisation->ComputeSolid(copy, daughter);
                        copyMaterial = parameterisation->ComputeMaterial(copy, daughter, nullptr);
                    } else {
                        replicaNavigation_.ComputeTransformation(copy, daughter);
                    }
                    Visit(daughter, copy, global, path, depth + 1, copySolid, copyMaterial);
                }
            } else {
                Visit(daughter, daughter->GetCopyNo(), global, path, depth + 1, nullptr, nullptr);
            }
        }
    }

    int Count() const { return count_; }

private:
    void Emit(G4VPhysicalVolume* physical, G4LogicalVolume* logical, G4VSolid* solid, G4Material* material,
              int copyNo, int depth,
              const std::string& path, const G4Transform3D& global)
    {
        G4Polyhedron* polyhedron = solid->GetPolyhedron();
        // GCC rejects a ternary mixing G4String and std::string; MSVC converts
        // implicitly. Keep the conversion explicit so both toolchains agree.
        const std::string materialName = material ? std::string(material->GetName()) : std::string();
        out_ << (count_ ? ",\n" : "\n") << "  {\"path\": \"" << Escape(path) << "\", \"name\": \""
             << Escape(physical->GetName()) << "\", \"copy\": " << copyNo << ", \"depth\": " << depth
             << ", \"logical\": \"" << Escape(logical->GetName()) << "\", \"solid\": \""
             << Escape(solid->GetEntityType()) << "\", \"material\": \""
             << Escape(materialName) << "\", \"sensitive\": "
             << (logical->GetSensitiveDetector() ? "true" : "false") << ", \"cubic_volume_mm3\": "
             << solid->GetCubicVolume() / (mm * mm * mm);
        out_ << ", \"vertices\": [";
        if (polyhedron) {
            for (int i = 1; i <= polyhedron->GetNoVertices(); ++i) {
                const HepGeom::Point3D<double> local = polyhedron->GetVertex(i);
                const HepGeom::Point3D<double> p = global * local;
                out_ << (i > 1 ? "," : "") << "[" << p.x() / mm << "," << p.y() / mm << "," << p.z() / mm << "]";
            }
        }
        out_ << "], \"faces\": [";
        if (polyhedron) {
            for (int f = 1; f <= polyhedron->GetNoFacets(); ++f) {
                G4int n = 0;
                G4int nodes[4] = {0, 0, 0, 0};
                polyhedron->GetFacet(f, n, nodes);
                out_ << (f > 1 ? "," : "") << "[";
                for (int k = 0; k < n; ++k) out_ << (k ? "," : "") << nodes[k] - 1;
                out_ << "]";
            }
        }
        out_ << "]}";
        ++count_;
    }

    std::ostream& out_;
    int maxDepth_;
    int count_ = 0;
    G4ReplicaNavigation replicaNavigation_;
};

}  // namespace

namespace GeometryExport {

int WriteMeshJson(const std::string& path, int maxDepth)
{
    G4VPhysicalVolume* world =
        G4TransportationManager::GetTransportationManager()->GetNavigatorForTracking()->GetWorldVolume();
    if (!world) throw std::runtime_error("GeometryExport: no world volume; run /run/initialize first");
    std::ostringstream body;
    body << std::setprecision(10);
    Writer writer(body, maxDepth);
    writer.Visit(world, 0, G4Transform3D(), "", 0, nullptr, nullptr);

    const std::filesystem::path file = std::filesystem::u8path(path);
    if (file.has_parent_path()) std::filesystem::create_directories(file.parent_path());
    std::ofstream out(file);
    if (!out) throw std::runtime_error("GeometryExport: cannot write '" + path + "'");
    out << "{\"schema\": \"g4usim_geometry_mesh_v1\", \"length_unit\": \"mm\", \"volume_count\": " << writer.Count()
        << ", \"volumes\": [" << body.str() << "\n]}\n";
    out.close();
    if (!out) throw std::runtime_error("GeometryExport: failed to write '" + path + "'");
    return writer.Count();
}

}  // namespace GeometryExport
