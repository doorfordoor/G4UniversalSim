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
