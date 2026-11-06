#pragma once

#include "Config/EffectiveConfigSupport.hh"
#include "Geometry/GeometryTypes.hh"

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

class ConfigManager;
class G4Material;
class GeometryManager;
class MaterialManager;
class OutputManager;
class ScoringManager;

namespace parallel_world {

// One scored volume: either a standalone box or one cell of a regular grid.
struct VolumeSpec {
    std::string name;                      // /<world>#0/<name>#<copy>
    std::string material;                  // declared material name (aliases allowed)
    const G4Material* materialObject = nullptr;  // resolved through MaterialManager
    double sizeMm[3] = {0.0, 0.0, 0.0};    // full box size
    double centreMm[3] = {0.0, 0.0, 0.0};  // in the ghost-world frame
    double volumeMm3 = 0.0;
    double densityKgPerM3 = 0.0;
    double referenceMassKg = 0.0;
    bool fromGrid = false;
    std::string gridName;
    // Non-empty for grid cells: the real parent navigation envelope that
    // owns the whole declared grid. The envelope itself is never scored.
    std::string envelope;
    // True only when a declared mass-world box of the same actual material
    // contains this whole scoring box; a center-point or name match is not proof.
    bool materialMatchesMassWorld = false;  // true only when proven
    bool materialMatchProven = false;       // false => unknown, never a fake proof
    std::string matchedMassVolume;          // declared volume that proves the correspondence
};

// One internal navigation envelope per declared grid: a box whose bounds are
// exactly the declared grid bounds, owning the real grid cells as daughters.
// It exists so Geant4 limits steps at the grid's outer boundary (a track that
// runs exactly along an internal shared face of the cells is otherwise not
// limited by the kernel at all); its sensitive detector restores the real cell
// owner when the ghost pre-point is located on the envelope rather than on a
// cell. The envelope is not a scoring volume: it is excluded from
// volumeCount() and from the reference mass total.
struct EnvelopeSpec {
    std::string name;  // /<world>#0/<name>#<copy>
    std::string material = "G4_Galactic";
    const G4Material* materialObject = nullptr;
    double sizeMm[3] = {0.0, 0.0, 0.0};
    double centreMm[3] = {0.0, 0.0, 0.0};
    std::vector<std::size_t> volumeIndices;  // grid cells owned by this envelope
};

// Observed kernel-side facts reported after the parallel geometry has been
// constructed and validated. The config never invents these values.
struct KernelObservation {
    int volumeCount = 0;
    double totalMassKg = 0.0;
    double maxRelativeMassDeviation = 0.0;
    std::string worldName;
};

// Roadmap H3: optional parallel scoring world.
//
// [parallel_world] in the main INI:
//   enabled = false           (default: legacy behaviour, no parallel world)
//   name = ScoringWorld       (optional; unique, no '/' '#' whitespace)
//   geometry_config = file.ini (required when enabled; relative to the main INI)
//
// The geometry file is an independent, closed INI:
//   [world]                       material = G4_Galactic   (no size key)
//   [volume.<name>]               parent/size/position/material/sensitive
//   [grid.<name>]                 parent/size/position/material/bins/sensitive
// Everything else is rejected before any Geant4 geometry object is created.
class ParallelWorldConfig {
public:
    ParallelWorldConfig();

    // Parses [parallel_world] and the referenced geometry file, recording the
    // exact input bytes in the shared provenance chain. Returns a disabled
    // configuration when the section is absent (the default).
    // Throws std::runtime_error with file/line context on any invalid field.
    void Load(const ConfigManager& config, const GeometryManager& geometry,
              const MaterialManager& materials);

    bool enabled() const { return enabled_; }
    const std::string& name() const { return name_; }
    const std::string& geometryConfigFile() const { return geometryConfigFile_; }
    const std::string& geometrySha256() const { return geometrySha256_; }
    const std::vector<VolumeSpec>& volumes() const { return volumes_; }
    // Internal navigation envelopes (one per declared grid); never scoring
    // volumes, so they do not contribute to volumeCount() or totalMassKg().
    const std::vector<EnvelopeSpec>& envelopes() const { return envelopes_; }
    int gridCount() const { return gridCount_; }
    int volumeCount() const { return static_cast<int>(volumes_.size()); }
    double totalMassKg() const { return totalMassKg_; }
    bool materialsResolved() const { return materialsResolved_; }
    // G4_Galactic resolved through the material manager, so an alias or a
    // user-defined vacuum works exactly like the mass world's materials.
    const G4Material* worldMaterial() const { return worldMaterial_; }
    double worldHalfMm(int axis) const { return worldHalfMm_[axis]; }
    const std::string& worldName() const { return name_; }

    // Stage A (configuration) checks that need managers the parser does not
    // own. Returns human-readable problems; empty means accepted.
    std::vector<std::string> ValidateDependencies(const ScoringManager& scoring,
                                                  const OutputManager& output,
                                                  bool biasingEnabled,
                                                  bool fieldConfigured,
                                                  bool meshConfigured) const;
    // Stage A: the declared mass world must be a box that contains every
    // scoring box; the template must be box based.
    std::vector<std::string> ValidateDeclaredContainment(const GeometryManager& geometry);
    std::vector<std::string> ValidateMaterials(const MaterialManager& materials) const;

    // Recomputes density/reference mass from the live Geant4 material table and
    // the declared containment proof; used after Stage A succeeded.
    void ResolveMaterials(const MaterialManager& materials, const GeometryManager& geometry);

    // A PreInit /AIHL/geometry/loadConfig replaces the mass-world tree after
    // Configure(); the Configure-time material proof must not be reused for a
    // later run. Revalidates the declared containment and re-derives the
    // whole-box material proof from the current tree: anything that cannot be
    // proven again degrades to `unknown` instead of keeping a stale `true`.
    // Throws std::runtime_error when the current geometry cannot host the
    // declared scoring volumes at all.
    void RebindToCurrentGeometry(const GeometryManager& geometry, const MaterialManager& materials);

    // Effective-configuration consumer view (manager-accepted stage).
    void AcceptEffectiveConfig(const IniReader& reader);
    std::vector<effective_config::Field> ExportEffectiveConfigFields() const;
    effective_config::Value ExportEffectiveConfigEvidence() const;

    // Receipts written by the master after Stage B and at finalization.
    void RecordKernelConstruction(int runId, const KernelObservation& observation,
                                  const std::string& geometrySha256) const;
    void RecordRunValidated(int runId, long long completedEvents, int volumeCount,
                            const effective_config::Value::Object& outputSha256) const;

    // Stable diagnostic text for the failed volume, used by Stage B messages.
    const VolumeSpec* FindVolume(const std::string& name) const;

private:
    void ValidateMainKeys(const ConfigManager& config) const;
    void ValidateMainName(const std::string& name, const GeometryManager& geometry) const;
    void ValidateGeometryStructure(const IniReader& reader) const;
    void ParseGeometryFile(const IniReader& reader, const GeometryManager& geometry);
    // Stage A: expanded names, global engineering cap and interior overlap.
    void ValidateExpandedVolumes(const IniReader& reader, const GeometryManager& geometry) const;
    void AppendVolume(VolumeSpec spec);

    static std::string ResolveRelative(const std::string& mainConfigPath, const std::string& path);

    std::shared_ptr<effective_config::ConsumerState> effective_ =
        std::make_shared<effective_config::ConsumerState>();

    bool enabled_ = false;
    std::string name_;
    std::string geometryConfigFile_;
    std::string geometrySha256_;
    std::string mainConfigFile_;
    std::vector<VolumeSpec> volumes_;
    std::vector<EnvelopeSpec> envelopes_;
    int gridCount_ = 0;
    double totalMassKg_ = 0.0;
    bool materialsResolved_ = false;
    const G4Material* worldMaterial_ = nullptr;
    double worldHalfMm_[3] = {0.0, 0.0, 0.0};
};

}  // namespace parallel_world
