#pragma once

// Backend geometry export (roadmap A5): the Geant4 world as it was actually
// built, every physical volume copy (including replica and parameterised
// copies) as a polyhedron mesh in world coordinates, for the GUI 3D preview.
//
// JSON schema g4usim_geometry_mesh_v1 (lengths in mm):
//   { "schema", "length_unit": "mm", "volume_count",
//     "volumes": [ { "path", "name", "copy", "depth", "logical", "solid",
//                    "material", "sensitive", "cubic_volume_mm3",
//                    "vertices": [[x,y,z],...], "faces": [[i,j,k(,l)],...] } ] }
// Face indices are 0-based into that volume's vertex list.

#include <string>

namespace GeometryExport {

// Writes the current world (needs /run/initialize). maxDepth < 0 = no limit.
// Returns the number of exported volume copies.
int WriteMeshJson(const std::string& path, int maxDepth = -1);

}  // namespace GeometryExport
