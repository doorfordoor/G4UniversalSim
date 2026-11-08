#include "Geometry/ShapeParameters.hh"
#include "Geometry/SolidRegistry.hh"

#include "Geometry/VolumeBuilder.hh"
#include "Geometry/VolumeNode.hh"
#include "G4VSolid.hh"

#include <algorithm>
#include <cctype>
#include <stdexcept>

namespace {
template <G4VSolid* (VolumeBuilder::*Method)(const VolumeNode&)>
G4VSolid* Build(VolumeBuilder& builder, const VolumeNode& node)
{
    return (builder.*Method)(node);
}

std::string Normalize(const std::string& name)
{
    const auto begin = name.find_first_not_of(" \t\n\r\f\v");
    if (begin == std::string::npos) return {};
    std::string value = name.substr(begin, name.find_last_not_of(" \t\n\r\f\v") - begin + 1);
    std::transform(value.begin(), value.end(), value.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return value;
}

// Preserve the existing direct-builder boolean checks (the INI parser has
// stronger, source-aware exact-count checks before any Geant4 object is made).
void ValidateBooleanTool(const VolumeNode& node)
{
    switch (node.shape) {
        case VolumeShape::Box:
            (void)ShapeParameters::NormalizeBox(node.size);
            break;
        case VolumeShape::Tubs:
            (void)ShapeParameters::ResolveTubs(node.size, node.parameters,
                                              ShapeParameters::TubsInput::CppBooleanTool);
            break;
        case VolumeShape::Sphere:
            if (node.parameters.size() < 6)
                throw std::runtime_error("sphere requires 6 parameters: rMin,rMax,startPhi,deltaPhi,startTheta,deltaTheta");
            break;
        case VolumeShape::Orb:
            if (node.parameters.empty() && node.size.x <= 0.0)
                throw std::runtime_error("orb requires parameters=radius or positive size.x shorthand");
            break;
        case VolumeShape::Cone:
            if (node.parameters.size() < 7)
                throw std::runtime_error("cone requires 7 parameters: rMin1,rMax1,rMin2,rMax2,halfZ,startPhi,deltaPhi");
            break;
        default: break;
    }
}

effective_config::Value Fields(const std::vector<SolidRegistry::Field>& fields)
{
    effective_config::Value::Array result;
    for (const auto& field : fields) {
        effective_config::Value::Object item{{"name", field.name}, {"dimension", field.dimension},
                                              {"required", field.required}};
        if (!field.defaultValue.empty()) item["default"] = field.defaultValue;
        result.emplace_back(std::move(item));
    }
    return result;
}
} // namespace

const std::vector<SolidRegistry::Entry>& SolidRegistry::Entries()
{
    // Each capability and its actual factory share ONE record. No new solids,
    // runtime registration, Geant4 object ownership or mutable global registry.
    static const std::vector<Entry> entries{
        {VolumeShape::Box, "box", {"cube"}, "G4Box", {}, {}, {}, true, true, false, false,
         "size is full x,y,z; constructor uses half lengths", &Build<&VolumeBuilder::CreateBoxSolid>},
        {VolumeShape::Tubs, "tubs", {"tube", "cylinder"}, "G4Tubs",
         {{"rMin", "length"}, {"rMax", "length"}, {"halfZ", "length"}, {"startPhi", "angle"}, {"deltaPhi", "angle"}},
         {5}, {}, false, true, false, false,
         "builder accepts >=5 parameters, else positive size x,y,z: rMax=x/2,halfZ=z/2; INI forbids size",
         &Build<&VolumeBuilder::CreateTubsSolid>},
        {VolumeShape::Sphere, "sphere", {}, "G4Sphere",
         {{"rMin", "length"}, {"rMax", "length"}, {"startPhi", "angle"}, {"deltaPhi", "angle"},
          {"startTheta", "angle"}, {"deltaTheta", "angle"}}, {6}, {}, false, true, false, false,
         "builder accepts >=6 parameters; INI requires exactly 6", &Build<&VolumeBuilder::CreateSphereSolid>},
        {VolumeShape::Orb, "orb", {}, "G4Orb", {{"radius", "length"}}, {1}, {}, false, true, false, false,
         "builder uses first parameter or size.x/2; INI requires exactly 1 parameter and forbids size",
         &Build<&VolumeBuilder::CreateOrbSolid>},
        {VolumeShape::Cone, "cone", {"cons"}, "G4Cons",
         {{"rMin1", "length"}, {"rMax1", "length"}, {"rMin2", "length"}, {"rMax2", "length"},
          {"halfZ", "length"}, {"startPhi", "angle"}, {"deltaPhi", "angle"}}, {7}, {}, false, true, false, false,
         "builder accepts >=7 parameters; INI requires exactly 7", &Build<&VolumeBuilder::CreateConeSolid>},
        {VolumeShape::Trd, "trd", {"trapezoid"}, "G4Trd", {}, {},
         {{"dx1", "length"}, {"dx2", "length"}, {"dy1", "length"}, {"dy2", "length"}, {"dz", "length"}},
         false, true, false, false, "explicit half lengths", &Build<&VolumeBuilder::CreateTrdSolid>},
        {VolumeShape::Trap, "trap", {}, "G4Trap", {}, {},
         {{"dz", "length"}, {"theta", "angle"}, {"phi", "angle"}, {"dy1", "length"}, {"dx1", "length"},
          {"dx2", "length"}, {"alpha1", "angle"}, {"dy2", "length"}, {"dx3", "length"},
          {"dx4", "length"}, {"alpha2", "angle"}}, false, true, false, false,
         "explicit half lengths and angles", &Build<&VolumeBuilder::CreateTrapSolid>},
        {VolumeShape::Ellipsoid, "ellipsoid", {}, "G4Ellipsoid",
         {{"ax", "length"}, {"by", "length"}, {"cz", "length"},
          {"zBottomCut", "length", false, "0"}, {"zTopCut", "length", false, "0"}},
         {3, 5}, {}, false, false, true, true, "3 axes or 3 axes + both cuts; omitted cuts use Geant4 defaults",
         &Build<&VolumeBuilder::CreateEllipsoidSolid>},
        {VolumeShape::EllipticalTube, "eltube", {"elliptical_tube"}, "G4EllipticalTube",
         {{"dx", "length"}, {"dy", "length"}, {"dz", "length"}}, {3}, {}, false, false, true, true,
         "half lengths", &Build<&VolumeBuilder::CreateEllipticalTubeSolid>},
        {VolumeShape::Torus, "torus", {}, "G4Torus",
         {{"rMin", "length"}, {"rMax", "length"}, {"rTor", "length"}, {"startPhi", "angle"}, {"deltaPhi", "angle"}},
         {5}, {}, false, false, true, true, "", &Build<&VolumeBuilder::CreateTorusSolid>},
        {VolumeShape::Para, "para", {"parallelepiped"}, "G4Para",
         {{"dx", "length"}, {"dy", "length"}, {"dz", "length"}, {"alpha", "angle"}, {"theta", "angle"}, {"phi", "angle"}},
         {6}, {}, false, false, true, true, "half lengths and angles", &Build<&VolumeBuilder::CreateParaSolid>},
        {VolumeShape::Hype, "hype", {}, "G4Hype",
         {{"innerRadius", "length"}, {"outerRadius", "length"}, {"innerStereo", "angle"},
          {"outerStereo", "angle"}, {"halfZ", "length"}}, {5}, {}, false, false, true, true,
         "", &Build<&VolumeBuilder::CreateHypeSolid>},
        {VolumeShape::Polycone, "polycone", {}, "G4Polycone",
         {{"startPhi", "angle"}, {"deltaPhi", "angle"}}, {2},
         {{"z_planes", "length_list"}, {"r_inner", "length_list"}, {"r_outer", "length_list"}},
         false, false, true, true, "matching lists of >=2 planes; existing relational checks remain in GeometryConfig",
         [](VolumeBuilder& b, const VolumeNode& n) { return b.CreatePolyconeSolid(n, false); }},
        {VolumeShape::Polyhedra, "polyhedra", {}, "G4Polyhedra",
         {{"startPhi", "angle"}, {"deltaPhi", "angle"}, {"numSide", "integer"}}, {3},
         {{"z_planes", "length_list"}, {"r_inner", "length_list"}, {"r_outer", "length_list"}},
         false, false, true, true, "matching lists of >=2 planes; integer numSide>=3",
         [](VolumeBuilder& b, const VolumeNode& n) { return b.CreatePolyconeSolid(n, true); }},
        {VolumeShape::Tessellated, "tessellated", {"stl"}, "G4TessellatedSolid", {}, {},
         {{"file", "path"}, {"file_unit", "length_unit", false, "mm"}}, false, false, true, true,
         "closed consistently oriented manifold STL; file.resolved is internal captured input",
         &Build<&VolumeBuilder::CreateTessellatedSolid>}
    };
    return entries;
}

const SolidRegistry::Entry* SolidRegistry::Find(VolumeShape shape)
{
    for (const auto& entry : Entries()) if (entry.shape == shape) return &entry;
    return nullptr;
}

const SolidRegistry::Entry* SolidRegistry::Find(const std::string& name)
{
    const std::string value = Normalize(name);
    for (const auto& entry : Entries()) {
        if (entry.name == value || std::find(entry.aliases.begin(), entry.aliases.end(), value) != entry.aliases.end())
            return &entry;
    }
    return nullptr;
}

bool SolidRegistry::Supports(VolumeShape shape, Context context)
{
    const auto* entry = Find(shape);
    return entry && (context == Context::Volume || entry->booleanTool);
}

G4VSolid* SolidRegistry::Create(VolumeBuilder& builder, const VolumeNode& node, Context context)
{
    const auto* entry = Find(node.shape);
    if (context == Context::BooleanTool) {
        if (!entry || !entry->booleanTool) throw std::runtime_error("unsupported or missing boolean tool shape");
        ValidateBooleanTool(node);
    } else if (!entry) {
        throw std::runtime_error("Unsupported shape for volume '" + node.name + "': shapeName='" + node.shapeName
                                 + "', parsed='unknown'");
    }
    G4VSolid* solid = entry->factory(builder, node);
    // Exactly the former A5-only PrecomputeVolume policy. Never warm old solids
    // or boolean composites: their estimates may consume the random stream.
    if (entry->precomputeVolume && solid) (void)solid->GetCubicVolume();
    return solid;
}

effective_config::Value SolidRegistry::Describe()
{
    using V = effective_config::Value;
    V::Array solids;
    for (const auto& entry : Entries()) {
        V::Array aliases, counts;
        for (const auto& alias : entry.aliases) aliases.emplace_back(alias);
        for (int count : entry.parameterCounts) counts.emplace_back(count);
        solids.emplace_back(V::Object{
            {"name", entry.name}, {"aliases", std::move(aliases)}, {"geant4_class", entry.geant4Class},
            {"parameters", Fields(entry.parameters)}, {"parameter_counts", std::move(counts)},
            {"properties", Fields(entry.properties)}, {"uses_size", entry.usesSize},
            {"boolean_tool", entry.booleanTool}, {"experimental", entry.experimental},
            {"precompute_volume", entry.precomputeVolume}, {"builder_compatibility", entry.builderCompatibility}
        });
    }
    return V::Object{{"schema", "g4usim_solid_registry_v1"}, {"scope", "hierarchical_primitive_solids"},
                     {"internal_units", V::Object{{"length", "mm"}, {"angle", "rad"}}},
                     {"validation", "GeometryConfig source-aware checks plus existing constructors; metadata is not full numeric validation"},
                     {"solids", std::move(solids)}};
}
