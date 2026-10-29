#include "Config/EffectiveRuntime.hh"
#include "Config/InputProvenance.hh"
#include "Field/FieldConfig.hh"

#include "Config/ConfigManager.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4SystemOfUnits.hh"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>

namespace {

double FieldUnit(const std::string& raw, char kind)
{
    const std::string unit = StringUtils::Trim(raw);
    if (kind == 'B') {
        static const std::map<std::string, double> units = {
            {"T", tesla}, {"tesla", tesla}, {"mT", 1e-3 * tesla}, {"uT", 1e-6 * tesla},
            {"G", gauss}, {"gauss", gauss}, {"kG", kilogauss}};
        const auto found = units.find(unit);
        if (found == units.end()) throw std::runtime_error("unknown magnetic field unit '" + unit + "' (use T, mT, uT, G or kG)");
        return found->second;
    }
    static const std::map<std::string, double> units = {
        {"V/m", volt / m}, {"kV/m", kilovolt / m}, {"MV/m", megavolt / m}, {"V/cm", volt / cm},
        {"kV/cm", kilovolt / cm}, {"MV/cm", megavolt / cm}, {"V/mm", volt / mm}, {"kV/mm", kilovolt / mm}};
    const auto found = units.find(unit);
    if (found == units.end()) {
        throw std::runtime_error("unknown electric field unit '" + unit + "' (use V/m, kV/m, MV/m, V/cm, kV/cm, MV/cm, V/mm or kV/mm)");
    }
    return found->second;
}

double LengthUnit(const std::string& unit)
{
    if (unit == "mm") return mm;
    if (unit == "cm") return cm;
    if (unit == "m") return m;
    throw std::runtime_error("unknown length unit '" + unit + "' in field map header (use mm, cm or m)");
}

std::string ResolveNextTo(const ConfigManager& config, const std::string& path)
{
    std::filesystem::path file = std::filesystem::u8path(StringUtils::Trim(path));
    if (file.is_relative()) {
        const std::string main = config.GetMainConfigPath();
        if (!main.empty()) file = std::filesystem::u8path(main).parent_path() / file;
    }
    return file.u8string();
}

std::size_t Bracket(const std::vector<double>& nodes, double value)
{
    // Index i with nodes[i] <= value <= nodes[i + 1] (caller checked the range).
    auto upper = std::upper_bound(nodes.begin(), nodes.end(), value);
    std::size_t index = static_cast<std::size_t>(upper - nodes.begin());
    if (index == 0) return 0;
    index -= 1;
    return std::min(index, nodes.size() - 2);
}

}  // namespace

G4ThreeVector FieldMap::Value(const G4ThreeVector& point) const
{
    const double p[3] = {point.x(), point.y(), point.z()};
    const std::vector<double>* axes[3] = {&x, &y, &z};
    std::size_t index[3];
    double fraction[3];
    for (int a = 0; a < 3; ++a) {
        const auto& nodes = *axes[a];
        if (p[a] < nodes.front() || p[a] > nodes.back()) return G4ThreeVector();
        index[a] = Bracket(nodes, p[a]);
        const double span = nodes[index[a] + 1] - nodes[index[a]];
        fraction[a] = (p[a] - nodes[index[a]]) / span;
    }
    const std::size_t ny = y.size();
    const std::size_t nz = z.size();
    G4ThreeVector result;
    for (int dx = 0; dx < 2; ++dx) {
        for (int dy = 0; dy < 2; ++dy) {
            for (int dz = 0; dz < 2; ++dz) {
                const double weight = (dx ? fraction[0] : 1.0 - fraction[0]) * (dy ? fraction[1] : 1.0 - fraction[1]) *
                                      (dz ? fraction[2] : 1.0 - fraction[2]);
                if (weight == 0.0) continue;
                result += weight * values[((index[0] + dx) * ny + (index[1] + dy)) * nz + (index[2] + dz)];
            }
        }
    }
    return result;
}

std::string FieldSpec::Describe() const
{
    std::ostringstream out;
    out << "name=" << (IsGlobal() ? "global" : name);
    if (hasMagnetic) {
        if (magneticMap) out << " magnetic_map=" << magneticMap->file;
        else out << " magnetic=(" << magnetic.x() / tesla << "," << magnetic.y() / tesla << "," << magnetic.z() / tesla << ")T";
    }
    if (hasElectric) {
        if (electricMap) out << " electric_map=" << electricMap->file;
        else out << " electric=(" << electric.x() / (kilovolt / cm) << "," << electric.y() / (kilovolt / cm) << ","
                 << electric.z() / (kilovolt / cm) << ")kV/cm";
    }
    if (!volumes.empty()) {
        out << " volumes=";
        for (std::size_t i = 0; i < volumes.size(); ++i) out << (i ? "," : "") << volumes[i];
    }
    out << " delta_chord=" << deltaChord / mm << "mm";
    return out.str();
}

G4ThreeVector FieldConfig::ParseFieldVector(const std::string& text, char kind)
{
    const auto parts = StringUtils::Split(text, ',');
    if (parts.size() != 3) throw std::runtime_error("expected 3 field components, e.g. '0, 0, 1 T': '" + text + "'");
    double values[3];
    std::string units[3];
    for (int i = 0; i < 3; ++i) {
        const std::string part = StringUtils::Trim(parts[static_cast<std::size_t>(i)]);
        std::istringstream in(part);
        if (!(in >> values[i])) throw std::runtime_error("invalid field component '" + part + "'");
        std::string rest;
        std::getline(in, rest);
        units[i] = StringUtils::Trim(rest);
        if (!std::isfinite(values[i])) throw std::runtime_error("field components must be finite");
    }
    if (units[2].empty()) throw std::runtime_error("field vector needs a unit: '" + text + "'");
    G4ThreeVector result;
    for (int i = 0; i < 3; ++i) {
        const double unit = FieldUnit(units[i].empty() ? units[2] : units[i], kind);
        result[i] = values[i] * unit;
    }
    return result;
}

std::shared_ptr<const FieldMap> FieldConfig::LoadMap(const std::string& path, char kind)
{
    const auto acceptedInput = input_provenance::ReadFile(path);
    std::istringstream input(acceptedInput.bytes);
    auto map = std::make_shared<FieldMap>();
    map->file = path;
    map->inputSha256 = acceptedInput.sha256;
    std::string line;
    int lineNumber = 0;
    std::vector<std::string> header;
    double lengthUnits[3] = {0, 0, 0};
    double valueUnits[3] = {0, 0, 0};
    struct Row { double p[3]; G4ThreeVector v; };
    std::vector<Row> rows;
    const char letter = kind;
    while (std::getline(input, line)) {
        ++lineNumber;
        const auto hash = line.find('#');
        if (hash != std::string::npos) line = line.substr(0, hash);
        line = StringUtils::Trim(line);
        if (line.empty()) continue;
        std::vector<std::string> cells;
        for (const auto& cell : StringUtils::Split(line, ',')) cells.push_back(StringUtils::Trim(cell));
        const std::string where = "field map '" + path + "' line " + std::to_string(lineNumber);
        if (header.empty()) {
            header = cells;
            const char* axes[3] = {"x_", "y_", "z_"};
            const std::string components[3] = {std::string(1, letter) + "x_", std::string(1, letter) + "y_",
                                               std::string(1, letter) + "z_"};
            if (header.size() != 6) throw std::runtime_error(where + ": header must have 6 columns");
            for (int a = 0; a < 3; ++a) {
                if (header[a].rfind(axes[a], 0) != 0) {
                    throw std::runtime_error(where + ": column " + std::to_string(a + 1) + " must be " + axes[a] + "<mm|cm|m>");
                }
                lengthUnits[a] = LengthUnit(header[a].substr(2));
                if (header[a + 3].rfind(components[a], 0) != 0) {
                    throw std::runtime_error(where + ": column " + std::to_string(a + 4) + " must be " + components[a] + "<unit>");
                }
                valueUnits[a] = FieldUnit(header[a + 3].substr(3), kind);
            }
            continue;
        }
        if (cells.size() != 6) throw std::runtime_error(where + ": expected 6 values");
        Row row;
        try {
            for (int a = 0; a < 3; ++a) {
                row.p[a] = UnitParser::ParseDouble(cells[a]) * lengthUnits[a];
                row.v[a] = UnitParser::ParseDouble(cells[a + 3]) * valueUnits[a];
            }
        } catch (const std::exception& error) {
            throw std::runtime_error(where + ": " + error.what());
        }
        rows.push_back(row);
    }
    if (header.empty() || rows.empty()) throw std::runtime_error("field map '" + path + "' has no data");
    std::set<double> xs, ys, zs;
    for (const Row& row : rows) {
        xs.insert(row.p[0]);
        ys.insert(row.p[1]);
        zs.insert(row.p[2]);
    }
    map->x.assign(xs.begin(), xs.end());
    map->y.assign(ys.begin(), ys.end());
    map->z.assign(zs.begin(), zs.end());
    if (map->x.size() < 2 || map->y.size() < 2 || map->z.size() < 2) {
        throw std::runtime_error("field map '" + path + "' needs at least 2 distinct values on each axis");
    }
    const std::size_t nx = map->x.size(), ny = map->y.size(), nz = map->z.size();
    if (rows.size() != nx * ny * nz) {
        throw std::runtime_error("field map '" + path + "' is not a complete regular grid: " + std::to_string(rows.size()) +
                                 " rows for " + std::to_string(nx) + " x " + std::to_string(ny) + " x " +
                                 std::to_string(nz) + " nodes");
    }
    map->values.assign(nx * ny * nz, G4ThreeVector());
    std::vector<bool> seen(nx * ny * nz, false);
    for (const Row& row : rows) {
        const auto ix = static_cast<std::size_t>(std::lower_bound(map->x.begin(), map->x.end(), row.p[0]) - map->x.begin());
        const auto iy = static_cast<std::size_t>(std::lower_bound(map->y.begin(), map->y.end(), row.p[1]) - map->y.begin());
        const auto iz = static_cast<std::size_t>(std::lower_bound(map->z.begin(), map->z.end(), row.p[2]) - map->z.begin());
        const std::size_t index = (ix * ny + iy) * nz + iz;
        if (seen[index]) throw std::runtime_error("field map '" + path + "' lists a grid node twice");
        seen[index] = true;
        map->values[index] = row.v;
    }
    return map;
}

void FieldConfig::LoadFromConfig(const ConfigManager& config)
{
    FieldConfig candidate;
    candidate.LoadFromConfigImpl(config);
    candidate.effective_->reader = config.GetMainReader();
    candidate.effective_->Accept(config.GetMainReader(),candidate.ProjectEffectiveConfigFields());
    fields_.swap(candidate.fields_);
    effective_.swap(candidate.effective_);
}

void FieldConfig::LoadFromConfigImpl(const ConfigManager& config)
{
    fields_.clear();
    static const std::set<std::string> keys = {"magnetic", "electric", "magnetic_map", "electric_map", "volumes",
                                               "min_step", "delta_chord", "delta_one_step", "delta_intersection"};
    for (const auto& info : config.GetSectionInfo()) {
        const std::string section = info.section;
        const std::string lower = StringUtils::ToLower(section);
        if (lower != "field" && lower.rfind("field.", 0) != 0) continue;
        const std::string original = info.originalSection.empty() ? section : StringUtils::Trim(info.originalSection);
        FieldSpec spec;
        if (lower != "field") {
            spec.name = original.substr(std::string("field.").size());
            if (spec.name.empty() || spec.name.find('.') != std::string::npos) {
                throw std::runtime_error("[" + original + "] must be [field.<name>]");
            }
        }
        const std::string context = "[" + original + "]";
        for (const auto& key : config.GetKeys(section)) {
            if (!keys.count(StringUtils::ToLower(key))) {
                throw std::runtime_error("unknown key " + context + "/" + key + "; supported: magnetic, electric, "
                                         "magnetic_map, electric_map, volumes, min_step, delta_chord, delta_one_step, "
                                         "delta_intersection");
            }
        }
        auto has = [&](const char* key) { return config.HasKey(section, key); };
        try {
            if (has("magnetic") && has("magnetic_map")) throw std::runtime_error("give magnetic or magnetic_map, not both");
            if (has("electric") && has("electric_map")) throw std::runtime_error("give electric or electric_map, not both");
            if (has("magnetic")) {
                spec.hasMagnetic = true;
                spec.magnetic = ParseFieldVector(config.GetString(section, "magnetic"), 'B');
            }
            if (has("magnetic_map")) {
                spec.hasMagnetic = true;
                spec.magneticMap = LoadMap(ResolveNextTo(config, config.GetString(section, "magnetic_map")), 'B');
            }
            if (has("electric")) {
                spec.hasElectric = true;
                spec.electric = ParseFieldVector(config.GetString(section, "electric"), 'E');
            }
            if (has("electric_map")) {
                spec.hasElectric = true;
                spec.electricMap = LoadMap(ResolveNextTo(config, config.GetString(section, "electric_map")), 'E');
            }
            if (!spec.hasMagnetic && !spec.hasElectric) {
                throw std::runtime_error("needs magnetic, electric, magnetic_map or electric_map");
            }
            if (has("volumes")) {
                if (spec.IsGlobal()) throw std::runtime_error("volumes is only valid in [field.<name>] (local fields)");
                for (const auto& part : StringUtils::Split(config.GetString(section, "volumes"), ',')) {
                    const std::string volume = StringUtils::Trim(part);
                    if (!volume.empty()) spec.volumes.push_back(volume);
                }
            }
            if (!spec.IsGlobal() && spec.volumes.empty()) throw std::runtime_error("local fields need volumes = <logical volumes>");
            const auto length = [&](const char* key, double& target) {
                if (!has(key)) {
                    target *= mm;
                    return;
                }
                target = UnitParser::ParseLength(config.GetString(section, key));
                if (!(target > 0.0)) throw std::runtime_error(std::string(key) + " must be > 0");
            };
            length("min_step", spec.minStep);
            length("delta_chord", spec.deltaChord);
            length("delta_one_step", spec.deltaOneStep);
            length("delta_intersection", spec.deltaIntersection);
        } catch (const std::exception& error) {
            throw std::runtime_error(context + ": " + error.what());
        }
        fields_.push_back(spec);
    }
}

std::vector<effective_config::Field> FieldConfig::ProjectEffectiveConfigFields() const
{
 using namespace effective_config;std::vector<Field> result;
 result.push_back(effective_->Make(FieldPath("field","module_enabled"),moduleEnabled_,"","modules",{"field"}));
 for(const auto& spec:fields_) {
  const std::string section=spec.IsGlobal()?"field":"field."+StringUtils::ToLower(spec.name);
  const auto path=[&](const char* key){return spec.IsGlobal()?FieldPath("field",key):ObjectFieldPath("field",spec.name,key);};
  const auto add=[&](const char* key,Value value,const char* unit,std::initializer_list<const char*> keys){result.push_back(effective_->Make(path(key),std::move(value),unit,section,keys));};
  add("scope",spec.IsGlobal()?"global":"local","",{});
  if(!spec.IsGlobal())add("volumes",List(spec.volumes),"",{"volumes"});
  const auto vector=[](const G4ThreeVector& v,double unit){return Value::Array{v.x()/unit,v.y()/unit,v.z()/unit};};
  if(spec.hasMagnetic && !spec.magneticMap)add("magnetic",vector(spec.magnetic,tesla),"T",{"magnetic"});
  if(spec.hasElectric && !spec.electricMap)add("electric",vector(spec.electric,volt/m),"V/m",{"electric"});
  const auto map=[&](const char* key,const std::shared_ptr<const FieldMap>& input){if(input){
   add(key,Value::Object{{"path",input->file},{"sha256",input->inputSha256},
       {"grid_shape",Value::Array{static_cast<std::int64_t>(input->x.size()),static_cast<std::int64_t>(input->y.size()),static_cast<std::int64_t>(input->z.size())}},
       {"coordinate_unit","mm"},{"x",Numbers(input->x,mm)},{"y",Numbers(input->y,mm)},{"z",Numbers(input->z,mm)},
       {"interpolation","trilinear_global"},{"outside","zero"}},"",{key});
   Value::Array values;const double fieldUnit=std::string(key)=="magnetic_map"?tesla:volt/m;
   for(const auto& value:input->values)values.emplace_back(vector(value,fieldUnit));
   auto& object=std::get<Value::Object>(result.back().resolved.data);
   object["values"]=std::move(values);object["field_unit"]=std::string(key)=="magnetic_map"?"T":"V/m";
   Origin origin;origin.kind="field_map";origin.file=input->file;origin.input_sha256=input->inputSha256;
   origin.disposition="derived";result.back().origins.push_back(std::move(origin));
  }};
  map("magnetic_map",spec.magneticMap);map("electric_map",spec.electricMap);
  add("min_step",spec.minStep/mm,"mm",{"min_step"});add("delta_chord",spec.deltaChord/mm,"mm",{"delta_chord"});
  add("delta_one_step",spec.deltaOneStep/mm,"mm",{"delta_one_step"});add("delta_intersection",spec.deltaIntersection/mm,"mm",{"delta_intersection"});
 }
 return result;
}
std::vector<effective_config::Field> FieldConfig::ExportEffectiveConfigFields() const {return effective_->accepted?effective_->fields:ProjectEffectiveConfigFields();}
effective_config::Value FieldConfig::ExportEffectiveConfigEvidence() const {return effective_->Evidence();}
void FieldConfig::ConfirmEffectiveConfigMutation(const std::string& command,const effective_config::Origin& origin) {effective_->Confirm(ProjectEffectiveConfigFields(),command,origin);}
void FieldConfig::SetModuleEnabled(bool enabled)
{
    moduleEnabled_=enabled;
    effective_config::Origin origin;origin.kind="module_policy";origin.file=effective_->reader.GetFilename();
    origin.input_sha256=effective_->reader.GetInputSha256();origin.section="modules";origin.key="field";
    origin.raw=enabled?"on":"off";origin.disposition="derived";
    for(const auto& declaration:effective_->reader.GetFields())
        if(declaration.normalizedSection=="modules" && declaration.normalizedKey=="field")origin.line=declaration.lineNumber;
    effective_->Confirm(ProjectEffectiveConfigFields(),enabled?"[modules]/field = on":"[modules]/field = off",origin,false,{"/field/module_enabled"});
}
void FieldConfig::RecordEffectiveConfigBinding(const std::string& name,const std::string& logicalVolume,bool applied,const FieldSpec* observed) const
{
    using namespace effective_config;
    if(!moduleEnabled_)return;
    const auto scope=name.empty()?FieldPath("field","scope"):ObjectFieldPath("field",name,"scope");
    auto binding=Receipt(scope,name.empty()?"global":"local","field_construct",
        "FieldSetup actual logical-volume/transport field manager readback","thread_applied",
        applied && observed?"applied":(applied?"unknown":"failed"));
    auto& details=std::get<Value::Object>(binding.data);
    details["logical_volume"]=logicalVolume;details["field_manager_bound"]=applied;
    effective_->Record(std::move(binding));
    if(!applied || !observed)return;
    // Read back the immutable specification stored by the actual installed
    // field object. This is distinct from copying the Manager configuration.
    FieldConfig actual;actual.fields_.push_back(*observed);
    for(const auto& field:actual.ProjectEffectiveConfigFields()) {
        if(field.path=="/field/module_enabled" || field.path==scope ||
           field.path.substr(field.path.find_last_of('/')+1)=="volumes" ||
           field.path.substr(field.path.find_last_of('/')+1)=="min_step")continue;
        auto receipt=Receipt(field.path,field.resolved,"field_construct",
            "FieldSetup installed field object and integration manager readback","thread_applied");
        std::get<Value::Object>(receipt.data)["logical_volume"]=logicalVolume;
        effective_->Record(std::move(receipt));
    }
}
