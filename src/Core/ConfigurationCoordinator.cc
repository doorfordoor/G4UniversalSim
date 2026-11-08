#include "Core/ConfigurationCoordinator.hh"
#include "Core/SimulationContext.hh"
#include "Config/ConfigManager.hh"
#include "Materials/MaterialManager.hh"
#include "Geometry/GeometryManager.hh"
#include "Physics/PhysicsManager.hh"
#include "Source/SourceManager.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/ScoringMeshConfig.hh"
#include "Biasing/BiasingManager.hh"
#include "Output/OutputManager.hh"
#include "Field/FieldConfig.hh"
#include "ParallelWorld/ParallelWorldConfig.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include <stdexcept>

namespace {

bool HasNonEmptyKey(const ConfigManager& config, const std::string& section, const std::string& key)
{
    return config.HasKey(section, key) && !StringUtils::Trim(config.GetString(section, key, "")).empty();
}

bool HasNonEmptyKeyCompat(const ConfigManager& config,
                          const std::string& section,
                          const std::vector<std::string>& keys)
{
    for (const auto& key : keys) {
        if (HasNonEmptyKey(config, section, key)) return true;
    }
    return false;
}

std::string GetStringCompat(const ConfigManager& config,
                            const std::string& section,
                            const std::vector<std::string>& keys,
                            const std::string& defaultValue = "")
{
    for (const auto& key : keys) {
        if (HasNonEmptyKey(config, section, key)) {
            return config.GetString(section, key);
        }
    }
    return defaultValue;
}

bool HasKeyCompat(const ConfigManager& config,
                  const std::string& section,
                  const std::vector<std::string>& keys)
{
    for (const auto& key : keys) {
        if (config.HasKey(section, key)) return true;
    }
    return false;
}

int GetIntCompat(const ConfigManager& config,
                 const std::string& section,
                 const std::vector<std::string>& keys,
                 int defaultValue)
{
    for (const auto& key : keys) {
        if (config.HasKey(section, key)) return config.GetInt(section, key);
    }
    return defaultValue;
}

bool GetBoolCompat(const ConfigManager& config,
                   const std::string& section,
                   const std::vector<std::string>& keys,
                   bool defaultValue)
{
    for (const auto& key : keys) {
        if (config.HasKey(section, key)) return config.GetBool(section, key);
    }
    return defaultValue;
}

}  // namespace

namespace configuration {

void ConfigureLoadedInputs(const ConfigManager& config, SimulationContext& context,
                           ConfigurationTargets targets)
{
    const int threads = config.GetInt("run", "threads", context.GetNumThreads());
    context.SetNumThreads(threads);

    if (HasKeyCompat(config, "run", {"seed", "randomSeed"}) ||
        HasKeyCompat(config, "general", {"seed", "randomSeed"})) {
        const int seed = HasKeyCompat(config, "run", {"seed", "randomSeed"})
            ? GetIntCompat(config, "run", {"seed", "randomSeed"}, 0)
            : GetIntCompat(config, "general", {"seed", "randomSeed"}, 0);
        if (seed < 0) throw std::runtime_error("Invalid config value run/seed: seed must be >= 0");
        context.SetSeed(static_cast<unsigned long>(seed));
    }

    context.SetInteractive(config.GetBool("run", "interactive", context.IsInteractive()));
    context.SetMacroFile(config.GetString("run", "macro", context.GetMacroFile()));
    context.SetDryRun(GetBoolCompat(config, "run", {"dry_run", "dryRun"}, context.IsDryRun()));
    context.SetVerboseLevel(HasKeyCompat(config, "run", {"verbose"})
        ? config.GetInt("run", "verbose", context.GetVerboseLevel())
        : config.GetInt("general", "verbose", context.GetVerboseLevel()));
    context.SetCheckOverlaps(GetBoolCompat(config, "run", {"check_overlaps", "checkOverlaps"}, context.GetCheckOverlaps()));
    context.SetRunName(GetStringCompat(config, "run", {"name", "run_name", "runName"}, context.GetRunName()));
    context.SetOutputDir(GetStringCompat(config, "output", {"dir", "outputDir"}, context.GetOutputDir()));
    if (HasKeyCompat(config, "output", {"format"})) {
        targets.output.SetFormat(OutputManager::ParseFormat(
            GetStringCompat(config, "output", {"format"}, "csv")));
    }

    if (HasNonEmptyKeyCompat(config, "materials", {"file", "materialFile", "config", "configFile"})) {
        targets.materialsFile = GetStringCompat(config, "materials", {"file", "materialFile", "config", "configFile"});
        if (!FileUtils::IsFile(targets.materialsFile)) {
            throw std::runtime_error("Materials config file does not exist: '" + targets.materialsFile + "'");
        }
        targets.materials.LoadMaterials(targets.materialsFile);
    }

    if (HasNonEmptyKeyCompat(config, "geometry", {"template", "templateName"})) {
        targets.geometryTemplate = GetStringCompat(config, "geometry", {"template", "templateName"});
        targets.geometry.SetTemplate(targets.geometryTemplate);
    }

    if (HasKeyCompat(config, "geometry", {"check_overlaps", "checkOverlaps"})) {
        context.SetCheckOverlaps(GetBoolCompat(config, "geometry", {"check_overlaps", "checkOverlaps"}, context.GetCheckOverlaps()));
    }

    if (HasNonEmptyKeyCompat(config, "geometry", {"default_world_material", "defaultWorldMaterial"})) {
        targets.defaultWorldMaterial = GetStringCompat(config, "geometry", {"default_world_material", "defaultWorldMaterial"});
        targets.geometry.SetDefaultWorldMaterial(targets.defaultWorldMaterial);
    }

    if (HasNonEmptyKeyCompat(config, "geometry", {"config", "configFile"})) {
        targets.geometryConfigFile = GetStringCompat(config, "geometry", {"config", "configFile"});
        if (!FileUtils::IsFile(targets.geometryConfigFile)) {
            throw std::runtime_error("Geometry config file does not exist: '" + targets.geometryConfigFile + "'");
        }
        targets.geometry.LoadGeometryConfig(targets.geometryConfigFile);
    }

    targets.physics.SetBiasingManager(&targets.biasing);
    targets.physics.LoadFromConfig(config);
    targets.geometry.ValidateRegionPhysicsNames();
    targets.field.LoadFromConfig(config);
    for (const FieldSpec& field : targets.field.GetFields()) {
        for (const std::string& volume : field.volumes) {
            if (!targets.geometry.HasConfiguredVolume(volume)) {
                throw std::runtime_error("[field." + field.name + "]/volumes names '" + volume +
                                         "', which is not a volume of the geometry");
            }
        }
    }
    targets.source.LoadFromConfig(config);
    targets.scoring.LoadFromConfig(config);
    targets.meshCommands = ScoringMeshConfig::BuildCommands(config);
    targets.biasing.LoadFromConfig(config);
    if (targets.biasing.IsEnabled()) {
        targets.physics.EnableBiasingPhysics(true);
    }

    // Roadmap H3: optional parallel scoring world. Parsed only after every
    // dependency (materials, geometry, scoring, output format, field, mesh,
    // biasing) is configured, so Stage A can reject unsupported combinations
    // before any Geant4 geometry object exists.
    targets.parallelWorld = std::make_shared<parallel_world::ParallelWorldConfig>();
    targets.parallelWorld->Load(config, targets.geometry, targets.materials);
    for (const char* key : {"enabled", "name", "geometry_config"}) {
        if (config.HasKey("parallel_world", key)) {
            config.MarkKeyConsumed("parallel_world", key);
        }
    }
    if (targets.parallelWorld->enabled()) {
        const auto dependencies = targets.parallelWorld->ValidateDependencies(
            targets.scoring, targets.output, targets.biasing.IsEnabled(),
            !targets.field.Empty(), !targets.meshCommands.empty());
        if (!dependencies.empty()) {
            throw std::runtime_error("[parallel_world] " + dependencies.front());
        }
        const auto containment = targets.parallelWorld->ValidateDeclaredContainment(targets.geometry);
        if (!containment.empty()) {
            throw std::runtime_error("[parallel_world] " + containment.front());
        }
        const auto materialProblems = targets.parallelWorld->ValidateMaterials(targets.materials);
        if (!materialProblems.empty()) {
            throw std::runtime_error("[parallel_world] " + materialProblems.front());
        }
        targets.parallelWorld->ResolveMaterials(targets.materials, targets.geometry);
    }

    // These aliases are intentionally accepted for compatibility.  A canonical
    // spelling may win, but a shadowed legacy spelling is still a consumed field.
    for (const auto& alias : {"seed", "randomSeed", "dry_run", "dryRun",
                              "check_overlaps", "checkOverlaps", "name",
                              "run_name", "runName"}) {
        config.MarkKeyConsumed("run", alias);
    }
    for (const auto& alias : {"seed", "randomSeed", "verbose"}) {
        config.MarkKeyConsumed("general", alias);
    }
    for (const auto& alias : {"dir", "outputDir", "format"}) {
        config.MarkKeyConsumed("output", alias);
    }
    for (const auto& alias : {"file", "materialFile", "config", "configFile"}) {
        config.MarkKeyConsumed("materials", alias);
        config.MarkKeyConsumed("geometry", alias);
    }
    for (const auto& alias : {"template", "templateName", "check_overlaps",
                              "checkOverlaps", "default_world_material",
                              "defaultWorldMaterial"}) {
        config.MarkKeyConsumed("geometry", alias);
    }
}

}  // namespace configuration
