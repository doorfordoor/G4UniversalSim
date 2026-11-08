#pragma once

#include <memory>
#include <string>
#include <vector>

class ConfigManager;
class SimulationContext;
class MaterialManager;
class GeometryManager;
class PhysicsManager;
class SourceManager;
class ScoringManager;
class BiasingManager;
class OutputManager;
class FieldConfig;
namespace parallel_world { class ParallelWorldConfig; }

namespace configuration {

// Borrowed existing owners/storage slots, valid only for this synchronous call.
// No copied configuration, retained references, or independent lifecycle state.
struct ConfigurationTargets {
    MaterialManager& materials;
    GeometryManager& geometry;
    PhysicsManager& physics;
    SourceManager& source;
    ScoringManager& scoring;
    BiasingManager& biasing;
    OutputManager& output;
    FieldConfig& field;
    std::string& materialsFile;
    std::string& geometryTemplate;
    std::string& geometryConfigFile;
    std::string& defaultWorldMaterial;
    std::vector<std::string>& meshCommands;
    std::shared_ptr<parallel_world::ParallelWorldConfig>& parallelWorld;
};

// Consume an already loaded INI in the existing dependency order. Exceptions
// propagate immediately; prior side effects are not rolled back. The caller
// owns loading, CLI overrides, module modes, effective evidence and publication.
void ConfigureLoadedInputs(const ConfigManager& config, SimulationContext& context,
                           ConfigurationTargets targets);

}  // namespace configuration
