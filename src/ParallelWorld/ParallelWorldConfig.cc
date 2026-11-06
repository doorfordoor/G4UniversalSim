#include "ParallelWorld/ParallelWorldConfig.hh"

#include "Config/ConfigManager.hh"
#include "Config/EffectiveRuntime.hh"
#include "Config/InputProvenance.hh"
#include "Geometry/GeometryManager.hh"
#include "Geometry/GeometryRegistry.hh"
#include "Geometry/VolumeNode.hh"
#include "Materials/MaterialManager.hh"
#include "Output/OutputManager.hh"
#include "Scoring/ScoringManager.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4Material.hh"
#include "G4SystemOfUnits.hh"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>

namespace parallel_world {

namespace {

// Engineering cap from the frozen H3 contract: at most 16x16x16 cells.
constexpr std::int64_t kMaxCells = 4096;

// Absolute error bound for one subtraction of two decimal-derived
// coordinates. A double carries ~2.2e-16 relative precision; parsing, unit
// conversion and the +/- half-extent arithmetic add at most a few ulps each.
// Scaling by the operand magnitudes keeps the bound explainable and, unlike a
// fixed 1e-9 relative slack, cannot absorb a representable positive overlap at
// large coordinates (0.0005 mm at 1,000,000 mm stays a real overlap while an
// exactly shared face still counts as contact).
double CoordinateBound(double first, double second)
{
    constexpr double kUlps = 64.0;
    return kUlps * std::numeric_limits<double>::epsilon() *
           (std::fabs(first) + std::fabs(second) + 1.0);
}

bool IsFinite(double value)
{
    return std::isfinite(value);
}

bool IsFinitePositive(double value)
{
    return std::isfinite(value) && value > 0.0;
}

std::string Join(const std::vector<std::string>& values)
{
    std::string text;
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index > 0) text += ", ";
        text += values[index];
    }
    return text;
}

std::string DescribeLocation(const std::string& file, std::size_t line)
{
    std::ostringstream stream;
    stream << file;
    if (line > 0) stream << ':' << line;
    return stream.str();
}

bool IsValidNameStart(char c)
{
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_';
}

bool IsValidNameBody(char c)
{
    return IsValidNameStart(c) || c == '-';
}

bool ParseBool(const std::string& text, const std::string& where)
{
    const std::string value = StringUtils::ToLower(StringUtils::Trim(text));
    if (value == "true" || value == "yes" || value == "on" || value == "1") return true;
    if (value == "false" || value == "no" || value == "off" || value == "0") return false;
    throw std::runtime_error(where + ": expected a boolean, got '" + text + "'");
}

}  // namespace

ParallelWorldConfig::ParallelWorldConfig() = default;

std::string ParallelWorldConfig::ResolveRelative(const std::string& mainConfigPath, const std::string& path)
{
    if (path.empty()) return path;
    const std::filesystem::path requested = std::filesystem::u8path(path);
    if (requested.is_absolute()) return path;
    const std::filesystem::path base = std::filesystem::u8path(mainConfigPath).parent_path();
    if (base.empty()) return path;
    return (base / requested).u8string();
}

void ParallelWorldConfig::Load(const ConfigManager& config, const GeometryManager& geometry,
                               const MaterialManager& materials)
{
    effective_->reader = config.GetMainReader();
    mainConfigFile_ = config.GetMainConfigPath();
    volumes_.clear();
    gridCount_ = 0;
    totalMassKg_ = 0.0;
    materialsResolved_ = false;
    for (double& half : worldHalfMm_) half = 0.0;
    enabled_ = false;
    name_.clear();
    geometryConfigFile_.clear();
    geometrySha256_.clear();
    if (!config.HasSection("parallel_world")) {
        return;
    }
    ValidateMainKeys(config);
    enabled_ = config.GetBool("parallel_world", "enabled", false);
    const bool hasName = config.HasKey("parallel_world", "name");
    const bool hasGeometry = config.HasKey("parallel_world", "geometry_config");
    if (!enabled_) {
        if (hasName || hasGeometry) {
            throw std::runtime_error(
                "[parallel_world] is disabled but declares name/geometry_config; remove those keys "
                "or set enabled = true (the legacy behaviour has no parallel world)");
        }
        return;
    }
    name_ = StringUtils::Trim(config.GetString("parallel_world", "name", "ScoringWorld"));
    if (name_.empty()) {
        throw std::runtime_error("[parallel_world]/name must name the parallel world when enabled");
    }
    ValidateMainName(name_, geometry);
    if (!hasGeometry) {
        throw std::runtime_error("[parallel_world]/geometry_config is required when enabled");
    }
    const std::string configured = StringUtils::Trim(config.GetString("parallel_world", "geometry_config"));
    if (configured.empty()) {
        throw std::runtime_error("[parallel_world]/geometry_config must not be empty when enabled");
    }
    geometryConfigFile_ = ResolveRelative(mainConfigFile_, configured);
    if (!FileUtils::IsFile(geometryConfigFile_)) {
        throw std::runtime_error("[parallel_world]/geometry_config does not name an existing file: '" +
                                 geometryConfigFile_ + "'");
    }
    // Parse exactly the bytes recorded in the provenance chain.
    const auto input =
        input_provenance::ReadFile(geometryConfigFile_, "parallel_world_geometry", "parser_input");
    geometrySha256_ = input.sha256;
    IniReader geometryReader;
    geometryReader.LoadBytes(geometryConfigFile_, input.bytes);
    ParseGeometryFile(geometryReader, geometry);
    const auto containment = ValidateDeclaredContainment(geometry);
    if (!containment.empty()) {
        throw std::runtime_error("Invalid [parallel_world] geometry: " + Join(containment));
    }
    const auto materialProblems = ValidateMaterials(materials);
    if (!materialProblems.empty()) {
        throw std::runtime_error("Invalid [parallel_world] geometry: " + Join(materialProblems));
    }
    ResolveMaterials(materials, geometry);
}

void ParallelWorldConfig::ValidateMainKeys(const ConfigManager& config) const
{
    static const std::vector<std::string> allowed{"enabled", "name", "geometry_config"};
    for (const auto& field : config.GetMainReader().GetDeclarations()) {
        if (field.normalizedSection != "parallel_world") continue;
        if (std::find(allowed.begin(), allowed.end(), field.normalizedKey) == allowed.end()) {
            throw std::runtime_error(
                DescribeLocation(config.GetMainConfigPath(), field.lineNumber) +
                ": unsupported [parallel_world] key '" + field.originalKey +
                "'; supported keys are enabled, name and geometry_config");
        }
    }
}

void ParallelWorldConfig::ValidateMainName(const std::string& name, const GeometryManager& geometry) const
{
    if (name.empty()) {
        throw std::runtime_error("[parallel_world]/name must not be empty");
    }
    if (!IsValidNameStart(name.front())) {
        throw std::runtime_error("[parallel_world]/name must start with a letter, digit or '_': '" + name + "'");
    }
    for (char c : name) {
        if (!IsValidNameBody(c)) {
            throw std::runtime_error(
                "[parallel_world]/name may only contain letters, digits, '_' and '-': '" + name + "'");
        }
    }
    if (geometry.HasRootNode()) {
        const auto& root = geometry.GetRootNode();
        if (root.name == name) {
            throw std::runtime_error("[parallel_world]/name '" + name +
                                     "' collides with the mass world volume name");
        }
    }
    const auto& registry = geometry.GetRegistry();
    if (registry.HasLogicalVolume(name) || registry.HasPhysicalVolume(name)) {
        throw std::runtime_error("[parallel_world]/name '" + name +
                                 "' collides with a mass-world volume name");
    }
    // Registered physical volumes only exist after construction; the configuration
    // tree is authoritative before the kernel is built.
    if (geometry.HasRootNode() && geometry.HasConfiguredVolume(name)) {
        throw std::runtime_error("[parallel_world]/name '" + name +
                                 "' collides with a configured mass-world volume name");
    }
}

void ParallelWorldConfig::ValidateGeometryStructure(const IniReader& reader) const
{
    if (!reader.GetDuplicates().empty()) {
        const auto& duplicate = reader.GetDuplicates().front();
        throw std::runtime_error(
            DescribeLocation(reader.GetFilename(), duplicate.lineNumber) + ": duplicate declaration" +
            (duplicate.key.empty() ? " of section [" + duplicate.section + "]"
                                   : " of key '" + duplicate.key + "'"));
    }
    bool hasWorld = false;
    for (const auto& field : reader.GetDeclarations()) {
        const std::string& section = field.normalizedSection;
        if (section == "world") {
            hasWorld = true;
        } else if (section.rfind("volume.", 0) == 0) {
            if (section.size() == 7) {
                throw std::runtime_error(DescribeLocation(reader.GetFilename(), field.lineNumber) +
                                         ": empty volume name in [" + field.originalSection + "]");
            }
        } else if (section.rfind("grid.", 0) == 0) {
            if (section.size() == 5) {
                throw std::runtime_error(DescribeLocation(reader.GetFilename(), field.lineNumber) +
                                         ": empty grid name in [" + field.originalSection + "]");
            }
        } else {
            throw std::runtime_error(
                DescribeLocation(reader.GetFilename(), field.lineNumber) + ": unknown section [" +
                field.originalSection + "]; supported sections are [world], [volume.<name>] and [grid.<name>]");
        }
    }
    if (!hasWorld) {
        throw std::runtime_error(reader.GetFilename() +
                                 ": parallel geometry requires a [world] section with material = G4_Galactic");
    }
    for (const auto& key : reader.GetKeys("world")) {
        if (key != "material") {
            throw std::runtime_error(
                reader.GetFilename() + ": [world] only supports material = G4_Galactic; '" + key +
                "' is not supported (the ghost world reuses the mass-world dimensions)");
        }
    }
    const std::string worldMaterial = reader.GetString("world", "material");
    if (worldMaterial != "G4_Galactic") {
        throw std::runtime_error(
            reader.GetFilename() +
            ": [world]/material must be G4_Galactic; the parallel world reuses the mass-world dimensions");
    }
}

void ParallelWorldConfig::ParseGeometryFile(const IniReader& reader, const GeometryManager& geometry)
{
    ValidateGeometryStructure(reader);
    static const std::vector<std::string> commonKeys{"parent", "shape", "material", "size", "position",
                                                     "sensitive"};
    static const std::vector<std::string> gridKeys{"bins"};
    std::vector<std::string> names;
    for (const auto& sectionInfo : reader.GetSectionDeclarations()) {
        const std::string& section = sectionInfo.normalizedSection;
        if (section == "world") continue;
        const bool volume = section.rfind("volume.", 0) == 0;
        const bool grid = section.rfind("grid.", 0) == 0;
        if (!volume && !grid) continue;
        // Geant4 object names keep the declared spelling: [volume.Slab] must
        // produce the touchable path segment 'Slab', not the lowercase key.
        const std::string& declared = sectionInfo.originalSection;
        const std::string object = StringUtils::Trim(declared.substr(volume ? 7 : 5));
        if (object.empty() || !IsValidNameStart(object.front())) {
            throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                     ": [" + sectionInfo.originalSection +
                                     "] name must start with a letter, digit or '_'");
        }
        for (char c : object) {
            if (!IsValidNameBody(c)) {
                throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                         ": [" + sectionInfo.originalSection +
                                         "] name may only contain letters, digits, '_' and '-' (no path "
                                         "separators, '#' or whitespace)");
            }
        }
        if (std::find(names.begin(), names.end(), object) != names.end()) {
            throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                     ": duplicate " + (volume ? "volume" : "grid") + " name '" + object + "'");
        }
        names.push_back(object);
        // Closed key set: anything not in the supported list is rejected here.
        for (const auto& key : reader.GetKeys(section)) {
            const bool knownCommon =
                std::find(commonKeys.begin(), commonKeys.end(), key) != commonKeys.end();
            const bool knownGrid =
                grid && std::find(gridKeys.begin(), gridKeys.end(), key) != gridKeys.end();
            if (!knownCommon && !knownGrid) {
                throw std::runtime_error(
                    DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) + ": unsupported key '" +
                    key + "' in [" + sectionInfo.originalSection +
                    "]; rotation, placement, replica, parameterised, boolean, region, cuts, visual and "
                    "bias settings are not supported");
            }
        }
        const auto require = [&](const char* key) -> std::string {
            if (!reader.HasKey(section, key)) {
                throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                         ": [" + sectionInfo.originalSection + "] requires '" + key + "'");
            }
            return StringUtils::Trim(reader.GetString(section, key));
        };
        const std::string parent = require("parent");
        if (parent != "world") {
            throw std::runtime_error(
                DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) + ": [" +
                sectionInfo.originalSection + "]/parent must be 'world'; nested parallel volumes are not supported");
        }
        const std::string material = require("material");
        if (material.empty()) {
            throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                     ": [" + sectionInfo.originalSection + "]/material must not be empty");
        }
        // v1 supports only box scoring volumes and regular box grids. The
        // [volume.<name>] form spells shape=box explicitly; [grid.<name>]
        // derives box cells and may omit the key.
        const bool hasShape = reader.HasKey(section, "shape");
        if (hasShape && StringUtils::Trim(reader.GetString(section, "shape")) != "box") {
            throw std::runtime_error(
                DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) + ": [" +
                sectionInfo.originalSection +
                "]/shape must be box; ellipsoid, torus, polycone, tessellated and other shapes are not "
                "supported in a parallel scoring world");
        }
        if (volume && !hasShape) {
            throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) + ": [" +
                                     sectionInfo.originalSection + "] requires 'shape'");
        }
        const bool sensitive = reader.HasKey(section, "sensitive")
            ? ParseBool(reader.GetString(section, "sensitive"),
                        DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) + ": [" +
                            sectionInfo.originalSection + "]/sensitive")
            : false;
        if (!sensitive) {
            throw std::runtime_error(
                DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) + ": [" +
                sectionInfo.originalSection +
                "]/sensitive must be true; non-sensitive parallel volumes are not supported");
        }
        const auto parsedSize = UnitParser::ParseVectorWithUnit(require("size"));
        if (parsedSize.size() != 3) {
            throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                     ": [" + sectionInfo.originalSection + "]/size needs three lengths");
        }
        double size[3] = {0.0, 0.0, 0.0};
        for (int axis = 0; axis < 3; ++axis) {
            size[axis] = parsedSize[axis];
            if (!IsFinitePositive(size[axis])) {
                throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                         ": [" + sectionInfo.originalSection +
                                         "]/size components must be finite and positive");
            }
        }
        double centre[3] = {0.0, 0.0, 0.0};
        if (reader.HasKey(section, "position")) {
            const auto parsedPosition = UnitParser::ParseVectorWithUnit(require("position"));
            if (parsedPosition.size() != 3) {
                throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                         ": [" + sectionInfo.originalSection + "]/position needs three lengths");
            }
            for (int axis = 0; axis < 3; ++axis) {
                centre[axis] = parsedPosition[axis];
                if (!IsFinite(centre[axis])) {
                    throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                             ": [" + sectionInfo.originalSection + "]/position must be finite");
                }
            }
        }
        if (volume) {
            VolumeSpec spec;
            spec.name = object;
            spec.material = material;
            for (int axis = 0; axis < 3; ++axis) {
                spec.sizeMm[axis] = size[axis];
                spec.centreMm[axis] = centre[axis];
            }
            spec.volumeMm3 = size[0] * size[1] * size[2];
            if (!IsFinitePositive(spec.volumeMm3)) {
                throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                         ": [" + sectionInfo.originalSection + "] volume overflows");
            }
            AppendVolume(std::move(spec));
            continue;
        }
        // Regular grid: one geometry per cell, ix fastest then iy then iz.
        const auto parsedBins = StringUtils::Split(require("bins"), ',', true);
        if (parsedBins.size() != 3) {
            throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                     ": [" + sectionInfo.originalSection + "]/bins needs nx,ny,nz");
        }
        std::int64_t binCount[3] = {0, 0, 0};
        std::int64_t total = 1;
        for (int axis = 0; axis < 3; ++axis) {
            double value = 0.0;
            try {
                value = UnitParser::ParseDouble(StringUtils::Trim(parsedBins[axis]));
            } catch (const std::exception&) {
                throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                         ": [" + sectionInfo.originalSection +
                                         "]/bins must be positive integers");
            }
            if (!std::isfinite(value) || value != std::floor(value) || value < 1.0 || value > 4096.0) {
                throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                         ": [" + sectionInfo.originalSection +
                                         "]/bins components must be integers in [1, 4096]");
            }
            binCount[axis] = static_cast<std::int64_t>(value);
            if (total > kMaxCells / binCount[axis]) {
                throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                         ": [" + sectionInfo.originalSection + "] requests more than " +
                                         std::to_string(kMaxCells) + " cells");
            }
            total *= binCount[axis];
        }
        ++gridCount_;
        // Real navigation envelope for this grid: exactly the declared grid
        // bounds. It is not a scoring volume; the cells keep their declared
        // global size/position/material and become its daughters.
        EnvelopeSpec envelope;
        envelope.name = object;
        envelope.material = "G4_Galactic";
        for (int axis = 0; axis < 3; ++axis) {
            envelope.sizeMm[axis] = size[axis];
            envelope.centreMm[axis] = centre[axis];
        }
        for (std::int64_t iz = 0; iz < binCount[2]; ++iz) {
            for (std::int64_t iy = 0; iy < binCount[1]; ++iy) {
                for (std::int64_t ix = 0; ix < binCount[0]; ++ix) {
                    VolumeSpec cell;
                    std::ostringstream cellName;
                    cellName << object << '_' << ix << '_' << iy << '_' << iz;
                    cell.name = cellName.str();
                    cell.material = material;
                    cell.fromGrid = true;
                    cell.gridName = object;
                    cell.envelope = object;
                    for (int axis = 0; axis < 3; ++axis) {
                        const double cellSize = size[axis] / static_cast<double>(binCount[axis]);
                        if (!IsFinitePositive(cellSize)) {
                            throw std::runtime_error(
                                DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) + ": [" +
                                sectionInfo.originalSection + "] grid cell size is not positive");
                        }
                        const std::int64_t index = axis == 0 ? ix : (axis == 1 ? iy : iz);
                        cell.sizeMm[axis] = cellSize;
                        cell.centreMm[axis] = centre[axis] +
                                              (static_cast<double>(index) + 0.5) * cellSize -
                                              size[axis] / 2.0;
                    }
                    cell.volumeMm3 = cell.sizeMm[0] * cell.sizeMm[1] * cell.sizeMm[2];
                    if (!IsFinitePositive(cell.volumeMm3)) {
                        throw std::runtime_error(DescribeLocation(reader.GetFilename(), sectionInfo.lineNumber) +
                                                 ": [" + sectionInfo.originalSection +
                                                 "] grid cell volume overflows");
                    }
                    AppendVolume(std::move(cell));
                    envelope.volumeIndices.push_back(volumes_.size() - 1);
                }
            }
        }
        envelopes_.push_back(std::move(envelope));
    }
    if (volumes_.empty()) {
        throw std::runtime_error(reader.GetFilename() +
                                 ": parallel geometry must declare at least one [volume.<name>] or [grid.<name>]");
    }
    ValidateExpandedVolumes(reader, geometry);
}

void ParallelWorldConfig::AppendVolume(VolumeSpec spec)
{
    volumes_.push_back(std::move(spec));
}

void ParallelWorldConfig::ValidateExpandedVolumes(const IniReader& reader, const GeometryManager&) const
{
    std::vector<std::string> problems;
    if (volumes_.size() > static_cast<std::size_t>(kMaxCells)) {
        problems.push_back("the parallel geometry expands to " + std::to_string(volumes_.size()) +
                           " scoring volumes; the engineering cap is " + std::to_string(kMaxCells) +
                           " (spread across all [grid.*] sections)");
    }
    std::map<std::string, std::size_t> seen;
    for (std::size_t index = 0; index < volumes_.size(); ++index) {
        const auto found = seen.emplace(volumes_[index].name, index);
        if (!found.second) {
            problems.push_back("declared volume and/or derived grid cell name '" + volumes_[index].name +
                               "' is not unique");
            continue;
        }
        const auto& volume = volumes_[index];
        for (int axis = 0; axis < 3; ++axis) {
            const double low = volume.centreMm[axis] - volume.sizeMm[axis] / 2.0;
            const double high = volume.centreMm[axis] + volume.sizeMm[axis] / 2.0;
            if (!IsFinite(low) || !IsFinite(high)) {
                problems.push_back("volume '" + volume.name + "' derives a non-finite centre or boundary");
                break;
            }
        }
    }
    for (std::size_t first = 0; first < volumes_.size(); ++first) {
        const auto& a = volumes_[first];
        for (std::size_t second = first + 1; second < volumes_.size(); ++second) {
            const auto& b = volumes_[second];
            bool interiorOverlap = true;
            for (int axis = 0; axis < 3; ++axis) {
                const double low = std::max(a.centreMm[axis] - a.sizeMm[axis] / 2.0,
                                            b.centreMm[axis] - b.sizeMm[axis] / 2.0);
                const double high = std::min(a.centreMm[axis] + a.sizeMm[axis] / 2.0,
                                             b.centreMm[axis] + b.sizeMm[axis] / 2.0);
                const double tolerance = CoordinateBound(low, high);
                if (!(high - low > tolerance)) {
                    // Face/edge/point contact is allowed; only a positive-volume
                    // intersection would make ghost navigation ambiguous.
                    interiorOverlap = false;
                    break;
                }
            }
            if (interiorOverlap) {
                problems.push_back("scoring volumes '" + a.name + "' and '" + b.name +
                                   "' overlap in their interior; only face/edge/point contact is allowed");
            }
        }
    }
    if (!problems.empty()) {
        throw std::runtime_error(DescribeLocation(reader.GetFilename(), 0) +
                                 ": invalid parallel geometry: " + Join(problems));
    }
}

std::vector<std::string> ParallelWorldConfig::ValidateDeclaredContainment(const GeometryManager& geometry)
{
    std::vector<std::string> problems;
    const std::string& templateName = geometry.GetTemplateName();
    if (templateName == "gdml") {
        return {"mass-world template 'gdml' is not a proven box and cannot host a parallel scoring world"};
    }
    if (!geometry.HasRootNode()) {
        return {"mass-world geometry has no root node"};
    }
    const auto& root = geometry.GetRootNode();
    if (root.shape != VolumeShape::Box) {
        return {"mass-world root shape '" + root.ShapeAsString() +
                "' is not a box; the parallel scoring world reuses the mass-world dimensions and requires a box"};
    }
    const double half[3] = {root.size.x / 2.0, root.size.y / 2.0, root.size.z / 2.0};
    for (int axis = 0; axis < 3; ++axis) {
        if (!IsFinitePositive(half[axis])) {
            return {"mass-world box size is not finite/positive"};
        }
        worldHalfMm_[axis] = half[axis];
    }
    for (const auto& volume : volumes_) {
        for (int axis = 0; axis < 3; ++axis) {
            const double low = volume.centreMm[axis] - volume.sizeMm[axis] / 2.0;
            const double high = volume.centreMm[axis] + volume.sizeMm[axis] / 2.0;
            const double tolerance = std::max(CoordinateBound(low, half[axis]),
                                              CoordinateBound(high, half[axis]));
            if (low < -half[axis] - tolerance || high > half[axis] + tolerance) {
                std::ostringstream message;
                message << "volume '" << volume.name << "' extends outside the declared mass world box along "
                        << (axis == 0 ? "x" : axis == 1 ? "y" : "z") << " (world half extent " << half[axis]
                        << " mm, volume [" << low << ", " << high << "] mm)";
                problems.push_back(message.str());
                break;
            }
        }
    }
    return problems;
}

std::vector<std::string> ParallelWorldConfig::ValidateMaterials(const MaterialManager& materials) const
{
    std::vector<std::string> problems;
    for (const auto& volume : volumes_) {
        if (!materials.HasMaterial(volume.material)) {
            problems.push_back("volume '" + volume.name + "' declares unknown material '" + volume.material + "'");
            continue;
        }
        G4Material* material = materials.GetMaterial(volume.material);
        const double density = material->GetDensity() / (kg / m3);
        if (!std::isfinite(density) || density <= 0.0) {
            problems.push_back("volume '" + volume.name + "' material '" + volume.material +
                               "' has a non-finite or non-positive density");
        }
    }
    return problems;
}

namespace {

bool IsIdentityRotation(const Rotation3& rotation)
{
    return rotation.x == 0.0 && rotation.y == 0.0 && rotation.z == 0.0;
}

struct WorldBox {
    std::string name;
    const G4Material* material = nullptr;
    double low[3] = {0.0, 0.0, 0.0};
    double high[3] = {0.0, 0.0, 0.0};
    bool valid = false;
};

// Conservative world-frame projection used only for the material-correspondence
// proof: axis-aligned boxes whose whole ancestor chain is unrotated and normally
// placed. Anything else stays invalid and is never used as evidence.
void CollectWorldBoxes(const VolumeNode& node, const double parentOffset[3], bool transformProven,
                       const MaterialManager& materials, std::vector<WorldBox>& boxes)
{
    const double offset[3] = {parentOffset[0] + node.position.x,
                              parentOffset[1] + node.position.y,
                              parentOffset[2] + node.position.z};
    WorldBox box;
    box.name = node.name;
    box.material = materials.HasMaterial(node.materialName) ? materials.GetMaterial(node.materialName) : nullptr;
    const double half[3] = {node.size.x / 2.0, node.size.y / 2.0, node.size.z / 2.0};
    // A rotated box cannot be projected with the unrotated offset±half formula,
    // so it is never valid evidence even when every ancestor transform is proven.
    bool valid = transformProven && node.shape == VolumeShape::Box &&
                 node.placementType == PlacementType::Normal &&
                 IsIdentityRotation(node.rotation) && box.material != nullptr &&
                 IsFinitePositive(node.size.x) && IsFinitePositive(node.size.y) &&
                 IsFinitePositive(node.size.z) && IsFinite(offset[0]) && IsFinite(offset[1]) &&
                 IsFinite(offset[2]);
    for (int axis = 0; axis < 3 && valid; ++axis) {
        box.low[axis] = offset[axis] - half[axis];
        box.high[axis] = offset[axis] + half[axis];
        if (!IsFinite(box.low[axis]) || !IsFinite(box.high[axis])) valid = false;
    }
    box.valid = valid;
    boxes.push_back(box);
    const bool childrenProven = transformProven && IsIdentityRotation(node.rotation) &&
                                node.placementType == PlacementType::Normal;
    for (const auto& child : node.children) CollectWorldBoxes(child, offset, childrenProven, materials, boxes);
}

bool ContainsWholeBox(const WorldBox& container, const VolumeSpec& volume)
{
    for (int axis = 0; axis < 3; ++axis) {
        const double low = volume.centreMm[axis] - volume.sizeMm[axis] / 2.0;
        const double high = volume.centreMm[axis] + volume.sizeMm[axis] / 2.0;
        const double tolerance = std::max(CoordinateBound(container.low[axis], low),
                                          CoordinateBound(container.high[axis], high));
        if (low < container.low[axis] - tolerance || high > container.high[axis] + tolerance) return false;
    }
    return true;
}

bool IntersectsInterior(const WorldBox& box, const VolumeSpec& volume)
{
    for (int axis = 0; axis < 3; ++axis) {
        const double volumeLow = volume.centreMm[axis] - volume.sizeMm[axis] / 2.0;
        const double volumeHigh = volume.centreMm[axis] + volume.sizeMm[axis] / 2.0;
        const double low = std::max(box.low[axis], volumeLow);
        const double high = std::min(box.high[axis], volumeHigh);
        const double tolerance = CoordinateBound(low, high);
        if (!(high - low > tolerance)) return false;
    }
    return true;
}

void BuildParentMap(const VolumeNode& node, const std::string& parent,
                    std::map<std::string, std::string>& parents)
{
    if (!node.name.empty()) parents[node.name] = parent;
    for (const auto& child : node.children) BuildParentMap(child, node.name, parents);
}

bool IsDescendantOf(const std::string& name, const std::string& ancestor,
                    const std::map<std::string, std::string>& parents)
{
    for (std::string current = name; !current.empty();) {
        const auto found = parents.find(current);
        if (found == parents.end()) return false;
        current = found->second;
        if (current == ancestor) return true;
    }
    return false;
}

}  // namespace

void ParallelWorldConfig::ResolveMaterials(const MaterialManager& materials, const GeometryManager& geometry)
{
    totalMassKg_ = 0.0;
    worldMaterial_ = materials.GetMaterial("G4_Galactic");
    if (worldMaterial_ == nullptr) {
        throw std::runtime_error("[parallel_world] the ghost world material G4_Galactic is not defined");
    }
    for (auto& envelope : envelopes_) {
        envelope.materialObject = materials.GetMaterial(envelope.material);
        if (envelope.materialObject == nullptr) {
            throw std::runtime_error("[parallel_world] navigation envelope '" + envelope.name +
                                     "' material '" + envelope.material + "' could not be resolved");
        }
    }
    std::vector<WorldBox> boxes;
    std::map<std::string, std::string> parents;
    if (geometry.HasRootNode()) {
        const auto& root = geometry.GetRootNode();
        const double origin[3] = {0.0, 0.0, 0.0};
        const bool rootProven = IsIdentityRotation(root.rotation) && root.shape == VolumeShape::Box &&
                                root.placementType == PlacementType::Normal;
        CollectWorldBoxes(root, origin, rootProven, materials, boxes);
        BuildParentMap(root, std::string(), parents);
    }
    for (auto& volume : volumes_) {
        G4Material* material = materials.HasMaterial(volume.material) ? materials.GetMaterial(volume.material)
                                                                      : nullptr;
        if (material == nullptr) {
            throw std::runtime_error("[parallel_world] volume '" + volume.name + "' material '" +
                                     volume.material + "' could not be resolved");
        }
        volume.materialObject = material;
        const double density = material->GetDensity();  // Geant4 mass/volume units (kg/mm^3)
        volume.densityKgPerM3 = density / (kg / m3);
        if (!IsFinitePositive(density) || !IsFinitePositive(volume.densityKgPerM3)) {
            throw std::runtime_error("[parallel_world] volume '" + volume.name +
                                     "' has a non-finite or non-positive material density");
        }
        volume.referenceMassKg = density * static_cast<double>(volume.volumeMm3) / kg;
        if (!IsFinitePositive(volume.referenceMassKg)) {
            throw std::runtime_error("[parallel_world] volume '" + volume.name +
                                     "' reference mass is not finite/positive");
        }
        totalMassKg_ += volume.referenceMassKg;
        if (!IsFinitePositive(totalMassKg_)) {
            throw std::runtime_error("[parallel_world] the total reference mass is not finite/positive");
        }
        volume.materialMatchesMassWorld = false;
        volume.materialMatchProven = false;
        volume.matchedMassVolume.clear();
        // Whole-box correspondence proof. A centre point or a matching material
        // name is never enough: pick a projected mass-world box of the same
        // resolved material that contains the scoring box and prove the scoring
        // interior is not covered by a different-material descendant.
        const WorldBox* candidate = nullptr;
        for (const auto& box : boxes) {
            if (box.valid && box.material == material && ContainsWholeBox(box, volume)) {
                candidate = &box;
                break;
            }
        }
        if (candidate != nullptr) {
            std::set<std::string> ancestors;
            for (std::string name = candidate->name; !name.empty();) {
                const auto parent = parents.find(name);
                if (parent == parents.end() || parent->second.empty()) break;
                ancestors.insert(parent->second);
                name = parent->second;
            }
            bool consistent = true;
            for (const auto& other : boxes) {
                if (other.name == candidate->name) continue;
                if (ancestors.count(other.name) != 0) continue;  // ancestor region, overridden here
                if (!other.valid) {
                    // A descendant that cannot be projected (rotated, non-box,
                    // unproven transform, unknown material) may still override the
                    // material inside the scoring box. Treating it as absent would
                    // sign a proof that is not actually established, so any
                    // descendant with a non-matching/unknown material fails it.
                    if (IsDescendantOf(other.name, candidate->name, parents) &&
                        other.material != material) {
                        consistent = false;
                        break;
                    }
                    continue;
                }
                if (other.material == material) continue;
                if (IntersectsInterior(other, volume)) {
                    consistent = false;
                    break;
                }
            }
            if (consistent) {
                volume.materialMatchesMassWorld = true;
                volume.materialMatchProven = true;
                volume.matchedMassVolume = candidate->name;
            }
        }
    }
    materialsResolved_ = true;
}

std::vector<std::string> ParallelWorldConfig::ValidateDependencies(const ScoringManager& scoring,
                                                                   const OutputManager& output,
                                                                   bool biasingEnabled,
                                                                   bool fieldConfigured,
                                                                   bool meshConfigured) const
{
    std::vector<std::string> problems;
    if (!enabled_) return problems;
    if (output.WritesRoot()) {
        problems.push_back(
            "ROOT output is not supported with a parallel scoring world; use [output] format = csv");
    }
    if (biasingEnabled) {
        problems.push_back("[biasing] enabled is not supported with a parallel scoring world");
    }
    if (fieldConfigured) {
        problems.push_back("[field] is not supported with a parallel scoring world");
    }
    if (meshConfigured) {
        problems.push_back(
            "[scoring.mesh.*] is not supported with a parallel scoring world "
            "(the native /score mesh cannot share the user parallel world)");
    }
    if (scoring.IsLETScoringEnabled()) {
        problems.push_back("[scoring] let is not supported with a parallel scoring world");
    }
    if (scoring.IsDisplacementScoringEnabled()) {
        problems.push_back("[scoring] displacement is not supported with a parallel scoring world");
    }
    if (!scoring.IsDoseScoringEnabled() && !scoring.IsFluenceScoringEnabled()) {
        problems.push_back(
            "a parallel scoring world requires [scoring] dose and/or fluence; neither is enabled");
    }
    return problems;
}

void ParallelWorldConfig::RebindToCurrentGeometry(const GeometryManager& geometry,
                                                  const MaterialManager& materials)
{
    if (!enabled_) return;
    // The world-name constraint was checked when the configuration was loaded.
    // A PreInit /AIHL/geometry/loadConfig can replace the mass-world tree, so the
    // same existing check has to hold for the live tree before any proof is
    // re-derived. This only reuses ValidateMainName; it adds no new rule.
    ValidateMainName(name_, geometry);
    const auto containment = ValidateDeclaredContainment(geometry);
    if (!containment.empty()) {
        throw std::runtime_error("the current mass-world geometry does not host the declared scoring "
                                 "volumes: " + Join(containment));
    }
    const auto materialProblems = ValidateMaterials(materials);
    if (!materialProblems.empty()) {
        throw std::runtime_error("the current material table cannot resolve the declared parallel "
                                 "materials: " + Join(materialProblems));
    }
    // Recompute density/reference mass and every whole-box correspondence proof
    // against the tree the kernel is using. ResolveMaterials resets each volume's
    // proof before it re-derives it, so a proof that cannot be repeated becomes
    // `unknown` rather than inheriting the Configure-time answer.
    ResolveMaterials(materials, geometry);
    using namespace effective_config;
    effective_->Record(Value::Object{
        {"event", "parallel_world_geometry_rebinding"},
        {"mass_geometry_config", geometry.GetGeometryConfigFile()},
        {"parallel_geometry_config", geometryConfigFile_},
        {"volume_count", static_cast<std::int64_t>(volumeCount())}});
}

void ParallelWorldConfig::AcceptEffectiveConfig(const IniReader& reader)
{
    effective_->reader = reader;
    effective_->Accept(reader, ExportEffectiveConfigFields());
}

std::vector<effective_config::Field> ParallelWorldConfig::ExportEffectiveConfigFields() const
{
    using namespace effective_config;
    std::vector<Field> fields;
    const auto make = [&](const std::string& path, Value value, const std::string& unit,
                          std::initializer_list<const char*> keys) {
        auto field = effective_->Make(path, std::move(value), unit, "parallel_world", keys);
        fields.push_back(std::move(field));
    };
    make(FieldPath("parallel_world", "enabled"), enabled_, "", {"enabled"});
    make(FieldPath("parallel_world", "name"), name_, "", {"name"});
    make(FieldPath("parallel_world", "geometry_config"), geometryConfigFile_, "", {"geometry_config"});
    {
        auto field = effective_->Make(FieldPath("parallel_world", "geometry_sha256"), geometrySha256_, "",
                                      "parallel_world", {"geometry_config"});
        field.evidence_source = "ParallelWorldConfig read exactly these bytes once for parsing";
        field.reason = geometrySha256_.empty()
            ? "No parallel geometry file was read (parallel world disabled)"
            : "SHA-256 of the exact parallel geometry bytes handed to the parser";
        if (!geometrySha256_.empty()) {
            Origin origin;
            origin.kind = "main_ini";
            origin.file = mainConfigFile_;
            origin.section = "parallel_world";
            origin.key = "geometry_config";
            origin.input_sha256 = geometrySha256_;
            origin.disposition = "derived";
            field.origins.push_back(origin);
        }
        fields.push_back(std::move(field));
    }
    {
        auto field = effective_->Make(FieldPath("parallel_world", "volume_count"),
                                      static_cast<std::int64_t>(volumes_.size()), "", "parallel_world", {});
        field.evidence_source = "ParallelWorldConfig declared volume/cell inventory";
        fields.push_back(std::move(field));
    }
    {
        auto field = effective_->Make(FieldPath("parallel_world", "total_mass_kg"), totalMassKg_, "kg",
                                      "parallel_world", {});
        field.evidence_source =
            "ParallelWorldConfig reference mass from live material density times declared volume";
        fields.push_back(std::move(field));
    }
    for (const auto& volume : volumes_) {
        const std::string object = "volume:" + volume.name;
        const auto addGeometryOrigin = [&](Field& field) {
            Origin origin;
            origin.kind = "geometry_config";
            origin.file = geometryConfigFile_;
            origin.section = "volume." + volume.name;
            origin.input_sha256 = geometrySha256_;
            origin.disposition = "accepted";
            field.origins.push_back(origin);
        };
        {
            auto field = effective_->Make(ObjectFieldPath("parallel_world", object, "material"),
                                          volume.material, "", "parallel_world", {});
            addGeometryOrigin(field);
            fields.push_back(std::move(field));
        }
        const auto add = [&](const std::string& name, Value value, const std::string& unit) {
            auto field = effective_->Make(ObjectFieldPath("parallel_world", object, name), std::move(value),
                                          unit, "parallel_world", {});
            field.evidence_source = "ParallelWorldConfig declared volume readback";
            addGeometryOrigin(field);
            fields.push_back(std::move(field));
        };
        add("density_kg_m3", volume.densityKgPerM3, "kg/m3");
        add("volume_mm3", volume.volumeMm3, "mm3");
        add("mass_kg", volume.referenceMassKg, "kg");
        add("sensitive", true, "");
        {
            const effective_config::Value proof = volume.materialMatchProven
                ? effective_config::Value(volume.materialMatchesMassWorld)
                : effective_config::Value(std::string("unknown"));
            auto field = effective_->Make(
                ObjectFieldPath("parallel_world", object, "material_matches_mass_world"),
                proof, "", "parallel_world", {});
            field.evidence_source = volume.materialMatchProven
                ? "Whole scoring box is covered by one projected mass-world box of the same resolved material"
                : "unknown: no complete axis-aligned material correspondence could be proven";
            field.reason = volume.materialMatchProven
                ? "matched by declared mass-world box '" + volume.matchedMassVolume + "'"
                : "unknown: a centre point or material-name match is not proof";
            fields.push_back(std::move(field));
        }
    }
    return fields;
}

void ParallelWorldConfig::RecordKernelConstruction(int runId, const KernelObservation& observation,
                                                   const std::string& geometrySha256) const
{
    using namespace effective_config;
    Value::Object observed{{"scope", "parallel_world_kernel_construction"},
                           {"run_id", static_cast<std::int64_t>(runId)},
                           {"world_name", observation.worldName},
                           {"volume_count", static_cast<std::int64_t>(observation.volumeCount)},
                           {"total_mass_kg", observation.totalMassKg},
                           {"max_relative_mass_deviation", observation.maxRelativeMassDeviation},
                           {"geometry_sha256", geometrySha256}};
    effective_->Record(Receipt(FieldPath("parallel_world", "volume_count"), Value(std::move(observed)),
                               "kernel_constructed",
                               "ParallelWorldConfig::RecordKernelConstruction", "kernel_constructed"));
}

void ParallelWorldConfig::RecordRunValidated(int runId, long long completedEvents, int volumeCount,
                                             const effective_config::Value::Object& outputSha256) const
{
    using namespace effective_config;
    Value::Object observed{{"scope", "parallel_world_run"},
                           {"run_id", static_cast<std::int64_t>(runId)},
                           {"completed_events", static_cast<std::int64_t>(completedEvents)},
                           {"volume_count", static_cast<std::int64_t>(volumeCount)},
                           {"output_sha256", Value(outputSha256)}};
    effective_->Record(Receipt(FieldPath("parallel_world", "enabled"), Value(std::move(observed)), "run_end",
                               "SimulationManager::FinalizeRunSummary", "run_validated"));
}

effective_config::Value ParallelWorldConfig::ExportEffectiveConfigEvidence() const
{
    return effective_->Evidence();
}

const VolumeSpec* ParallelWorldConfig::FindVolume(const std::string& name) const
{
    for (const auto& volume : volumes_) {
        if (volume.name == name) return &volume;
    }
    return nullptr;
}

}  // namespace parallel_world
