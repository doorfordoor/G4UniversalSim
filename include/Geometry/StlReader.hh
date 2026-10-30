#pragma once

// STL meshes for G4TessellatedSolid (roadmap A5: CAD import).
//
// Reads ASCII or binary STL, welds vertices closer than a tolerance, and checks
// that the mesh is closed and manifold (every edge shared by exactly two
// triangles) with a non-zero enclosed volume. Triangles are reoriented so the
// mesh encloses a positive volume (outward normals), as Geant4 requires.

#include <array>
#include <string>
#include <vector>

struct StlMesh {
    std::string inputPath;
    std::string inputSha256;
    double lengthUnit = 1.0;
    bool binary = false;
    std::vector<std::array<double, 3>> vertices;   // Geant4 internal length units
    std::vector<std::array<int, 3>> triangles;     // indices into vertices
    double volume = 0.0;                           // enclosed volume (> 0)
    std::array<double, 3> minCorner{};
    std::array<double, 3> maxCorner{};
};

namespace StlReader {

// lengthUnit: value of one file unit in Geant4 units (e.g. CLHEP::mm).
StlMesh Read(const std::string& path, double lengthUnit, const std::string& role = "mesh_parse");

}  // namespace StlReader
