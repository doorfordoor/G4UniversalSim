#pragma once

#include <string>

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
