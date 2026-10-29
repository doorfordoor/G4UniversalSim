#include "Config/ConfigSchemaTable.hh"
#include "Scoring/ScoringMeshConfig.hh"

#include "Config/ConfigManager.hh"
#include "Config/EffectiveRuntime.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4SystemOfUnits.hh"
#include "G4ScoringManager.hh"
#include "G4VScoringMesh.hh"
#include "G4VPrimitiveScorer.hh"
#include "G4PSEnergyDeposit.hh"
#include "G4PSCellFlux.hh"
#include "G4PSDoseDeposit.hh"
#include "G4PSTrackLength.hh"
#include "G4PSPassageCellFlux.hh"
#include "G4PSNofStep.hh"
#include "G4PSNofSecondary.hh"
#include "G4PSTermination.hh"
#include <typeinfo>
#include "Scoring/ScoringMeshExport.hh"

#include <cctype>
#include <cmath>
#include <map>
#include <sstream>
#include <stdexcept>

namespace {

const std::string kPrefix = "scoring.mesh.";
auto effectiveState = std::make_shared<effective_config::ConsumerState>();

struct QuantitySection {
    std::string name;      // original spelling
    std::string section;   // normalized section name
};

struct MeshSection {
    std::string name;      // original spelling
    std::string section;   // normalized section name
    std::vector<QuantitySection> quantities;
};

[[noreturn]] void Fail(const std::string& section, const std::string& message)
{
    throw std::runtime_error("Invalid [" + section + "]: " + message);
}

bool ValidName(const std::string& name)
{
    if (name.empty()) return false;
    for (const char c : name) {
        if (!(std::isalnum(static_cast<unsigned char>(c)) || c == '_' || c == '-')) return false;
    }
    return true;
}

std::string Number(double value)
{
    std::ostringstream out;
    out.precision(12);
    out << value;
    return out.str();
}

std::vector<double> Lengths(const ConfigManager& config, const std::string& section, const char* key,
                            std::size_t count)
{
    const std::string text = config.GetString(section, key);
    std::vector<double> values;
    for (const std::string& part : StringUtils::Split(text, ',')) {
        const std::string item = StringUtils::Trim(part);
        try {
            values.push_back(UnitParser::ParseLength(item));
        } catch (const std::exception& error) {
            Fail(section, std::string(key) + " = '" + text + "': " + error.what());
        }
    }
    if (values.size() != count) {
        Fail(section, std::string(key) + " needs " + std::to_string(count) + " comma-separated lengths");
    }
    for (const double value : values) {
        if (!std::isfinite(value)) Fail(section, std::string(key) + " must be finite");
    }
    return values;
}

std::vector<int> Bins(const ConfigManager& config, const std::string& section)
{
    const std::string text = config.GetString(section, "bins");
    std::vector<int> values;
    for (const std::string& part : StringUtils::Split(text, ',')) {
        const std::string item = StringUtils::Trim(part);
        std::size_t used = 0;
        int value = 0;
        try {
            value = std::stoi(item, &used);
        } catch (const std::exception&) {
            used = 0;
        }
        if (used != item.size() || value < 1) Fail(section, "bins = '" + text + "': expected three integers >= 1");
        values.push_back(value);
    }
    if (values.size() != 3) Fail(section, "bins needs three comma-separated integers");
    return values;
}

std::vector<MeshSection> FindSections(const ConfigManager& config)
{
    std::map<std::string, MeshSection> meshes;   // keyed by normalized mesh name
    std::vector<std::string> order;
    std::vector<std::pair<std::string, QuantitySection>> pending;
    for (const auto& info : config.GetSectionInfo()) {
        if (info.section.rfind(kPrefix, 0) != 0) continue;
        const std::string normalizedRest = info.section.substr(kPrefix.size());
        const std::string original = info.originalSection.size() >= kPrefix.size()
            ? info.originalSection.substr(kPrefix.size()) : normalizedRest;
        const auto dot = original.find('.');
        if (dot == std::string::npos) {
            if (!ValidName(original)) Fail(info.section, "mesh name must use letters, digits, '_' or '-'");
            if (meshes.count(normalizedRest)) Fail(info.section, "duplicate mesh section");
            meshes[normalizedRest] = {original, info.section, {}};
            order.push_back(normalizedRest);
        } else {
            const std::string meshName = original.substr(0, dot);
            const std::string quantityName = original.substr(dot + 1);
            if (!ValidName(meshName) || !ValidName(quantityName)) {
                Fail(info.section, "expected [scoring.mesh.<mesh>.<quantity>] with names of letters, digits, '_' or '-'");
            }
            pending.push_back({StringUtils::ToLower(meshName), {quantityName, info.section}});
        }
    }
    for (const auto& item : pending) {
        auto it = meshes.find(item.first);
        if (it == meshes.end()) {
            Fail(item.second.section, "no matching [scoring.mesh." + item.first + "] section");
        }
        it->second.quantities.push_back(item.second);
    }
    std::vector<MeshSection> result;
    for (const auto& name : order) result.push_back(meshes[name]);
    return result;
}

}  // namespace

namespace ScoringMeshConfig {

const std::vector<std::string>& MeshKeys()
{
    static const auto keys = ConfigSchema::Keys("main_ini", "scoring.mesh.<name>");
    return keys;
}

const std::vector<std::string>& QuantityKeys()
{
    static const auto keys = ConfigSchema::Keys("main_ini", "scoring.mesh.<name>.<quantity>");
    return keys;
}

std::vector<std::string> BuildCommands(const ConfigManager& config)
{
    std::vector<std::string> commands;
    effective_config::ConsumerState candidate;
    candidate.reader = config.GetMainReader();
    std::vector<effective_config::Field> fields;
    const auto add = [&](const std::string& object, const char* key, effective_config::Value value,
                         const std::string& section, const std::string& unit = "") {
        auto field = candidate.Make(effective_config::ObjectFieldPath("mesh", object, key), std::move(value), unit, section, {key});
        if (field.requested_known) field.requested = field.resolved;
        fields.push_back(std::move(field));
    };
    for (const MeshSection& mesh : FindSections(config)) {
        const std::string& s = mesh.section;
        for (const auto& key : MeshKeys()) config.MarkKeyConsumed(s, key);
        if (!config.HasKey(s, "shape") || !config.HasKey(s, "size") || !config.HasKey(s, "bins")) {
            Fail(s, "shape, size and bins are required");
        }
        const std::string shape = StringUtils::ToLower(StringUtils::Trim(config.GetString(s, "shape")));
        const std::vector<int> bins = Bins(config, s);
        add(mesh.name, "shape", shape, s);
        add(mesh.name, "bins", effective_config::Value::Array{bins[0], bins[1], bins[2]}, s);
        if (shape == "box") {
            const auto size = Lengths(config, s, "size", 3);
            add(mesh.name, "size", effective_config::Numbers(size, mm), s, "mm");
            for (const double v : size) if (v <= 0.0) Fail(s, "size half-lengths must be > 0");
            commands.push_back("/score/create/boxMesh " + mesh.name);
            commands.push_back("/score/mesh/boxSize " + Number(size[0] / mm) + " " + Number(size[1] / mm) + " " +
                               Number(size[2] / mm) + " mm");
        } else if (shape == "cylinder") {
            const auto size = Lengths(config, s, "size", 2);
            add(mesh.name, "size", effective_config::Numbers(size, mm), s, "mm");
            for (const double v : size) if (v <= 0.0) Fail(s, "cylinder radius and half-length must be > 0");
            commands.push_back("/score/create/cylinderMesh " + mesh.name);
            commands.push_back("/score/mesh/cylinderSize " + Number(size[0] / mm) + " " + Number(size[1] / mm) + " mm");
        } else {
            Fail(s, "shape = '" + shape + "': expected box or cylinder");
        }
        commands.push_back("/score/mesh/nBin " + std::to_string(bins[0]) + " " + std::to_string(bins[1]) + " " +
                           std::to_string(bins[2]));
        if (config.HasKey(s, "center")) {
            const auto center = Lengths(config, s, "center", 3);
            add(mesh.name, "center", effective_config::Numbers(center, mm), s, "mm");
            commands.push_back("/score/mesh/translate/xyz " + Number(center[0] / mm) + " " + Number(center[1] / mm) +
                               " " + Number(center[2] / mm) + " mm");
        }
        if (!config.HasKey(s, "center")) add(mesh.name, "center", effective_config::Value::Array{0.0, 0.0, 0.0}, s, "mm");
        if (mesh.quantities.empty()) Fail(s, "define at least one [" + s + ".<quantity>] section");

        for (const QuantitySection& quantity : mesh.quantities) {
            const std::string& q = quantity.section;
            for (const auto& key : QuantityKeys()) config.MarkKeyConsumed(q, key);
            if (!config.HasKey(q, "type")) Fail(q, "type is required (a Geant4 primitive scorer, e.g. energyDeposit)");
            const std::string type = StringUtils::Trim(config.GetString(q, "type"));
            if (!ValidName(type)) Fail(q, "type = '" + type + "' is not a scorer command name");
            const std::string identity = mesh.name + "/quantities/" + quantity.name;
            add(identity, "type", type, q);
            if (config.HasKey(q, "unit")) add(identity, "unit", StringUtils::Trim(config.GetString(q, "unit")), q);
            std::string command = "/score/quantity/" + type + " " + quantity.name;
            if (config.HasKey(q, "unit")) command += " " + StringUtils::Trim(config.GetString(q, "unit"));
            commands.push_back(command);

            const bool hasParticles = config.HasKey(q, "particles");
            const bool hasEnergy = config.HasKey(q, "energy_min") || config.HasKey(q, "energy_max");
            std::string particles;
            if (hasParticles) {
                for (const std::string& part : StringUtils::Split(config.GetString(q, "particles"), ',')) {
                    const std::string name = StringUtils::Trim(part);
                    if (!name.empty()) particles += " " + name;
                }
                if (particles.empty()) Fail(q, "particles is empty");
                effective_config::Value::Array names;
                std::istringstream words(particles); std::string name;
                while (words >> name) names.emplace_back(name);
                add(identity, "particles", std::move(names), q);
            }
            std::string energies;
            if (hasEnergy) {
                double low = 0.0;
                double high = 1.0e30;
                try {
                    if (config.HasKey(q, "energy_min")) low = UnitParser::ParseEnergy(config.GetString(q, "energy_min"));
                    if (config.HasKey(q, "energy_max")) high = UnitParser::ParseEnergy(config.GetString(q, "energy_max"));
                } catch (const std::exception& error) {
                    Fail(q, std::string("energy_min/energy_max: ") + error.what());
                }
                if (!(low >= 0.0) || !(high > low)) Fail(q, "need 0 <= energy_min < energy_max");
                add(identity, "energy_min", low / MeV, q, "MeV");
                add(identity, "energy_max", high / MeV, q, "MeV");
                energies = " " + Number(low / MeV) + " " + Number(high / MeV) + " MeV";
            }
            const std::string filterName = quantity.name + "_filter";
            if (hasParticles && hasEnergy) {
                commands.push_back("/score/filter/particleWithKineticEnergy " + filterName + energies + particles);
            } else if (hasParticles) {
                commands.push_back("/score/filter/particle " + filterName + particles);
            } else if (hasEnergy) {
                commands.push_back("/score/filter/kineticEnergy " + filterName + energies);
            }
        }
        commands.push_back("/score/close");
    }
    // Publish only after all meshes and quantities validate.
    effectiveState->Accept(config.GetMainReader(), std::move(fields));
    return commands;
}

std::vector<effective_config::Field> ExportEffectiveConfigFields() { return effectiveState->fields; }
effective_config::Value ExportEffectiveConfigEvidence() { return effectiveState->Evidence(); }
void ConfirmEffectiveConfigMutation(const std::string& command, effective_config::Origin origin)
{
    if (command.rfind("/score/", 0) != 0) return;
    effectiveState->Confirm(effectiveState->fields, command, origin, true);
    for (auto& field : effectiveState->fields) field.reason = "Native score command accepted; INI mesh projection is no longer verified kernel state";
}
void RecordEffectiveConfigDispatch()
{
    for (const auto& field : effectiveState->fields)
        effectiveState->Record(effective_config::Receipt(field.path, field.resolved, "mesh_commands_dispatched",
            "Successful generated /score command dispatch", "manager_accepted", "unknown",
            "Command acceptance does not independently observe constructed meshes or worker mesh inventories"));
}
void ObserveEffectiveConfigMeshes()
{
    using namespace effective_config;
    auto* manager=G4ScoringManager::GetScoringManagerIfExist();
    if(!manager)return;
    for(const auto& info:ScoringMeshExport::DescribeMeshes()) {
        auto* mesh=manager->FindMesh(info.name);if(!mesh)continue;
        const bool constructed=mesh->GetMeshElementLogical()!=nullptr && mesh->GetParallelWorldProcess()!=nullptr;
        const auto observe=[&](const std::string& object,const char* key,Value value) {
            const auto path=ObjectFieldPath("mesh",object,key);
            const auto known=std::find_if(effectiveState->fields.begin(),effectiveState->fields.end(),[&](const Field& f){return f.path==path;});
            const bool attributed=known!=effectiveState->fields.end() && known->application_status!=ApplicationStatus::Unknown;
            auto receipt=Receipt(path,std::move(value),"run_begin","Actual thread G4ScoringManager mesh readback",
                "thread_applied",constructed && attributed ? "applied":"unknown",
                "Mesh logical volume and parallel-world process observed independently; no physical validation claim");
            auto& detail=std::get<Value::Object>(receipt.data);
            detail["mesh_constructed"]=constructed;detail["mesh_active"]=mesh->IsActive();
            effectiveState->Record(std::move(receipt));
        };
        observe(info.name,"shape",info.shape);
        observe(info.name,"bins",Value::Array{info.bins[0],info.bins[1],info.bins[2]});
        observe(info.name,"center",Value::Array{info.centerMm[0],info.centerMm[1],info.centerMm[2]});
        if(info.shape=="box")observe(info.name,"size",Value::Array{info.sizeMm[0],info.sizeMm[1],info.sizeMm[2]});
        else if(info.shape=="cylinder") {
            // Native G4ScoringCylinder stores (Rmin,Rmax,Dz). INI takes
            // (outer radius,half length); never compare Rmin to the radius.
            const auto size=mesh->GetSize();
            observe(info.name,"size",Value::Array{size[1]/mm,size[2]/mm});
        }
        for(const auto& quantity:info.quantities) {
            const auto* primitive=mesh->GetPrimitiveScorer(quantity);if(!primitive)continue;
            const std::string identity=info.name+"/quantities/"+quantity;
            observe(identity,"unit",std::string(primitive->GetUnit()));
            std::string type;
            if(dynamic_cast<const G4PSEnergyDeposit*>(primitive))type="energyDeposit";
            else if(dynamic_cast<const G4PSCellFlux*>(primitive))type="cellFlux";
            else if(dynamic_cast<const G4PSDoseDeposit*>(primitive))type="doseDeposit";
            else if(dynamic_cast<const G4PSTrackLength*>(primitive))type="trackLength";
            else if(dynamic_cast<const G4PSPassageCellFlux*>(primitive))type="passageCellFlux";
            else if(dynamic_cast<const G4PSNofStep*>(primitive))type="nOfStep";
            else if(dynamic_cast<const G4PSNofSecondary*>(primitive))type="nOfSecondary";
            else if(dynamic_cast<const G4PSTermination*>(primitive))type="termination";
            if(!type.empty())observe(identity,"type",type);
            // Xerces/Geant4 filter classes expose no particle-list or energy
            // limit getters in supported 11.3/11.4. Report the actual filter
            // identity separately without presenting cached INI as readback.
            for(const auto* key:{"type","particles","energy_min","energy_max"}) {
                if(std::string(key)=="type" && !type.empty())continue;
                const auto path=ObjectFieldPath("mesh",identity,key);
                if(std::none_of(effectiveState->fields.begin(),effectiveState->fields.end(),[&](const Field& field){return field.path==path;}))continue;
                const auto* filter=primitive->GetFilter();
                Value::Object receipt{{"path",path},{"stage","run_begin"},
                    {"thread_id",G4Threading::G4GetThreadId()},
                    {"run_id",G4RunManager::GetRunManager() && G4RunManager::GetRunManager()->GetCurrentRun()?
                        Value(G4RunManager::GetRunManager()->GetCurrentRun()->GetRunID()):Value()},
                    {"application_status","unknown"},{"evidence_level","none"},
                    {"evidence_source","Actual primitive scorer/filter identity; configuration getter unavailable"},
                    {"reason",std::string(key)=="type"?"Primitive scorer class has no canonical command-type mapping":"Native filter provides no public particle-list or energy-limit readback"},
                    {"native_scorer_type",typeid(*primitive).name()},
                    {"filter_present",filter!=nullptr}};
                if(filter){receipt["native_filter_type"]=typeid(*filter).name();receipt["filter_name"]=filter->GetName();}
                effectiveState->Record(std::move(receipt));
            }
        }
    }
}
}  // namespace ScoringMeshConfig
