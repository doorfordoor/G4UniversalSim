#pragma once

#include "Config/EffectiveConfig.hh"
#include "Geometry/GeometryTypes.hh"

#include <string>
#include <vector>

class G4VSolid;
class VolumeBuilder;
class VolumeNode;

// This registry describes the existing hierarchical solid contract. It is not a
// replacement for GeometryConfig's source-aware numeric/relational validation.
class SolidRegistry {
public:
    enum class Context { Volume, BooleanTool };
    struct Field {
        std::string name;
        std::string dimension;  // length, angle, integer, length_list, path, length_unit
        bool required = true;
        std::string defaultValue = {};
    };
    using Factory = G4VSolid* (*)(VolumeBuilder&, const VolumeNode&);
    struct Entry {
        VolumeShape shape;
        std::string name;
        std::vector<std::string> aliases;
        std::string geant4Class;
        std::vector<Field> parameters;  // ordered; optional tail for ellipsoid
        std::vector<int> parameterCounts;  // exact hierarchical counts; empty = forbidden
        std::vector<Field> properties;
        bool usesSize;
        bool booleanTool;
        bool experimental;
        bool precomputeVolume;  // A5 only, during master-owned geometry construction
        std::string builderCompatibility;  // C++ builder legacy fallback, NOT an INI permission
        Factory factory;
    };

    static const std::vector<Entry>& Entries();
    static const Entry* Find(VolumeShape shape);
    static const Entry* Find(const std::string& name);  // trim + case insensitive, existing aliases only
    static bool Supports(VolumeShape shape, Context context = Context::Volume);
    // Dispatches existing constructors, preserving their validations, accounting,
    // input evidence and Geant4 ownership. Caller must use the normal master build
    // lifecycle; this function does not support worker-side geometry creation.
    static G4VSolid* Create(VolumeBuilder& builder, const VolumeNode& node,
                           Context context = Context::Volume);
    // Versioned, deterministic JSON-ready definition, without constructing solids
    // or touching Geant4 stores/RNG. This advertises capabilities, not runtime proof.
    static effective_config::Value Describe();
};
