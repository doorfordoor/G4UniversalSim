#pragma once

// Electromagnetic fields (roadmap A7), from the main INI:
//
//   [field]                      global field (whole world)
//   [field.<name>]               local field on the listed logical volumes
//   magnetic = Bx, By, Bz unit   uniform magnetic field (T, mT, uT, G, kG)
//   electric = Ex, Ey, Ez unit   uniform electric field (V/m, kV/m, MV/m, V/cm, kV/cm, MV/cm, kV/mm)
//   magnetic_map / electric_map  CSV grid instead of a uniform value
//   volumes = A, B               local fields only (logical volume or volume names)
//   min_step, delta_chord, delta_one_step, delta_intersection   integration accuracy
//
// Field-map CSV: header x_<len>,y_<len>,z_<len>,<C>x_<unit>,<C>y_<unit>,<C>z_<unit>
// (C = B or E; len = mm, cm or m), one row per node of a regular grid that
// covers every combination of the distinct x, y and z values exactly once.
// Values are interpolated trilinearly in global coordinates; outside the grid
// the field is zero.

#include "G4ThreeVector.hh"

#include <memory>
#include <string>
#include <vector>

class ConfigManager;

struct FieldMap {
    std::string file;
    std::vector<double> x, y, z;            // sorted node coordinates (Geant4 units)
    std::vector<G4ThreeVector> values;      // index (ix * ny + iy) * nz + iz
    G4ThreeVector Value(const G4ThreeVector& point) const;
};

struct FieldSpec {
    std::string name;                       // "" = global
    bool hasMagnetic = false;
    bool hasElectric = false;
    G4ThreeVector magnetic;                 // uniform value (Geant4 units)
    G4ThreeVector electric;
    std::shared_ptr<const FieldMap> magneticMap;  // shared read-only by all threads
    std::shared_ptr<const FieldMap> electricMap;
    std::vector<std::string> volumes;
    double minStep = 0.01;                  // mm (set in Geant4 units by the loader)
    double deltaChord = 0.25;
    double deltaOneStep = 0.01;
    double deltaIntersection = 0.001;

    bool IsGlobal() const { return name.empty(); }
    std::string Describe() const;
};

class FieldConfig {
public:
    void LoadFromConfig(const ConfigManager& config);
    const std::vector<FieldSpec>& GetFields() const { return fields_; }
    bool Empty() const { return fields_.empty(); }

    // Parses "Bx, By, Bz unit" (or one unit per component) for a magnetic
    // (kind 'B') or electric (kind 'E') field vector.
    static G4ThreeVector ParseFieldVector(const std::string& text, char kind);
    static std::shared_ptr<const FieldMap> LoadMap(const std::string& path, char kind);

private:
    std::vector<FieldSpec> fields_;
};
