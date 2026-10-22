#pragma once

#include <map>
#include <string>
#include <vector>

enum class VolumeShape {
    Box,
    Tubs,
    Sphere,
    Orb,
    Cone,
    Trd,
    Trap,
    // roadmap A5
    Ellipsoid,
    EllipticalTube,
    Torus,
    Para,
    Hype,
    Polycone,
    Polyhedra,
    Tessellated,
    Unknown
};

enum class PlacementType {
    Normal,
    Replica,
    Parameterised,
    Assembly
};

enum class BooleanOperation {
    None,
    Union,
    Subtraction,
    Intersection
};

struct Vec3 {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct Rotation3 {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct ProductionCut {
    double gamma = -1.0;
    double electron = -1.0;
    double positron = -1.0;
    double proton = -1.0;
};

struct VisualAttributes {
    bool visible = true;
    std::string color;
    double alpha = 1.0;
    bool wireframe = false;
};

// One copy of a parameterised placement (position/rotation in the mother
// frame; empty material = the volume's own material).
struct ParameterisedCopy {
    Vec3 position;
    Rotation3 rotation;
    std::string material;
};

// placement = replica: Geant4 G4PVReplica slices of the mother along axis
// (x, y, z for a box mother; phi for a tubs mother). placement = parameterised:
// G4PVParameterised with one entry per copy.
struct PlacementSpec {
    std::string replicaAxis;
    int replicaCount = 0;
    double replicaWidth = 0.0;
    double replicaOffset = 0.0;
    bool hasReplicaOffset = false;  // phi: defaults to the mother's startPhi
    std::vector<ParameterisedCopy> copies;
};

struct BooleanOperand {
    VolumeShape shape = VolumeShape::Unknown;
    std::string shapeName;
    Vec3 size;
    std::vector<double> parameters;
    Vec3 position;
    Rotation3 rotation;
    std::map<std::string, std::string> properties;
};

struct BooleanSolidOperation {
    BooleanOperation operation = BooleanOperation::None;
    BooleanOperand tool;
    std::string name;
};
