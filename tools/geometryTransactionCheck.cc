// Real public-interface transaction regression. Snapshots never build a world.
#include "Geometry/GeometryManager.hh"
#include "BuildInfo.hh"
#include "G4Version.hh"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
using effective_config::Value;
using O = Value::Object;
using A = Value::Array;
namespace {
Value Vector(const Vec3& v) { return A{v.x,v.y,v.z}; }
Value Rotation(const Rotation3& v) { return A{v.x,v.y,v.z}; }
Value Properties(const std::map<std::string,std::string>& properties) {
    O result; for(const auto& p:properties) result[p.first]=p.second; return result;
}
Value Node(const VolumeNode& n) {
    A children, copies, booleans;
    for(const auto& c:n.children) children.push_back(Node(c));
    for(const auto& c:n.placement.copies) copies.emplace_back(O{{"position",Vector(c.position)},{"rotation",Rotation(c.rotation)},{"material",c.material}});
    for(const auto& b:n.booleanOperations) booleans.emplace_back(O{{"operation",static_cast<int>(b.operation)},{"name",b.name},
        {"tool",O{{"shape",static_cast<int>(b.tool.shape)},{"shape_name",b.tool.shapeName},{"size",Vector(b.tool.size)},
        {"parameters",effective_config::Numbers(b.tool.parameters)},{"position",Vector(b.tool.position)},
        {"rotation",Rotation(b.tool.rotation)},{"properties",Properties(b.tool.properties)}}}});
    return O{{"name",n.name},{"parent",n.parentName},{"shape",static_cast<int>(n.shape)},{"shape_name",n.shapeName},
        {"material",n.materialName},{"size",Vector(n.size)},{"position",Vector(n.position)},{"rotation",Rotation(n.rotation)},
        {"parameters",effective_config::Numbers(n.parameters)},{"sensitive",n.sensitive},{"bias",n.bias},{"region",n.regionName},
        {"has_cuts",n.hasProductionCuts},{"cuts",A{n.productionCuts.gamma,n.productionCuts.electron,n.productionCuts.positron,n.productionCuts.proton}},
        {"placement_type",static_cast<int>(n.placementType)},
        {"placement",O{{"axis",n.placement.replicaAxis},{"count",n.placement.replicaCount},{"width",n.placement.replicaWidth},
        {"offset",n.placement.replicaOffset},{"has_offset",n.placement.hasReplicaOffset},{"copies",copies}}},
        {"visual",O{{"visible",n.visual.visible},{"color",n.visual.color},{"alpha",n.visual.alpha},{"wireframe",n.visual.wireframe}}},
        {"booleans",booleans},{"properties",Properties(n.userProperties)},{"children",children}};
}
std::string Pointer(const void* pointer) { std::ostringstream s; s<<pointer; return s.str(); }
Value Reader(const IniReader& r) {
    A declarations, fields, sections, duplicates;
    const auto field=[](const IniFieldInfo& d)->Value {return O{{"section",d.section},{"key",d.key},{"value",d.value},
        {"line",static_cast<std::int64_t>(d.lineNumber)},{"consumed",d.consumed},{"original_section",d.originalSection},
        {"normalized_section",d.normalizedSection},{"original_key",d.originalKey},{"normalized_key",d.normalizedKey},{"raw_line",d.rawLine}};};
    for(const auto& d:r.GetDeclarations()) declarations.push_back(field(d));
    for(const auto& d:r.GetFields()) fields.push_back(field(d));
    for(const auto& s:r.GetSectionDeclarations()) sections.emplace_back(O{{"section",s.section},{"line",static_cast<std::int64_t>(s.lineNumber)},
        {"explicit",s.explicitSection},{"original",s.originalSection},{"normalized",s.normalizedSection}});
    for(const auto& d:r.GetDuplicates()) duplicates.emplace_back(O{{"section",d.section},{"key",d.key},
        {"first",static_cast<std::int64_t>(d.firstLine)},{"line",static_cast<std::int64_t>(d.lineNumber)}});
    return O{{"filename",r.GetFilename()},{"sha256",r.GetInputSha256()},{"declarations",declarations},{"fields",fields},{"sections",sections},{"duplicates",duplicates}};
}
Value Fields(const std::vector<effective_config::Field>& fields) {
    // Local serializer registry only; never a commit to any application registry.
    effective_config::Registry serializer; serializer.Commit(fields);
    return serializer.Capture("configure").ToJson();
}
Value Ledger() {
    A result; for(const auto& r:input_provenance::Snapshot()) result.emplace_back(O{{"sequence",static_cast<std::int64_t>(r.sequence)},
        {"path",r.path},{"kind",r.kind},{"role",r.role},{"capture_method",r.capture_method},{"status",r.status},
        {"sha256",r.sha256?Value(*r.sha256):Value()},{"size",r.size_bytes?Value(static_cast<std::int64_t>(*r.size_bytes)):Value()},{"reason",r.reason}});
    return result;
}
void Write(const std::filesystem::path& path,const std::string& bytes) {
    std::ofstream out(path,std::ios::binary); out<<bytes; out.close(); if(!out)throw std::runtime_error("cannot write "+path.string());
}
std::string Geometry(const std::string& child,double size=200) {
    return "[world]\nshape=box\nsize="+std::to_string(size)+" mm,200 mm,200 mm\nmaterial=G4_AIR\n[volume."+child+"]\nparent=world\nshape=box\nsize=20 mm,20 mm,20 mm\nmaterial=G4_WATER\n";
}
VolumeNode User(const std::string& name,const std::string& parent) {
    VolumeNode n(name); n.parentName=parent; n.shape=VolumeShape::Box; n.shapeName="box";
    n.materialName="G4_Si"; n.size={2,3,4}; n.position={1,2,3}; n.rotation={0.1,0.2,0.3};
    n.visual.color="red";n.userProperties["metadata.probe"]="retained"; return n;
}
}
class GeometryTransactionProbe {
public:
    static Value Snapshot(const GeometryManager& m) {
        A users, inputs, logical, physical;
        for(const auto& n:m.GetUserAddedVolumes()) users.push_back(Node(n));
        for(const auto& f:m.inputFiles_) inputs.emplace_back(O{{"path",f.path},{"bytes",f.bytes},{"sha256",f.sha256}});
        for(const auto& n:m.registry_.GetLogicalVolumeNames()) logical.emplace_back(O{{"name",n},{"pointer",Pointer(m.registry_.GetLogicalVolume(n))}});
        for(const auto& n:m.registry_.GetPhysicalVolumeNames()) physical.emplace_back(O{{"name",n},{"pointer",Pointer(m.registry_.GetPhysicalVolume(n))}});
        return O{{"template",m.GetTemplateName()},{"template_tree",m.templateRootNode_?Node(*m.templateRootNode_):Value()},
            {"final_tree",m.HasRootNode()?Node(m.GetRootNode()):Value()},{"root_identity",Pointer(m.rootNode_.get())},
            {"template_identity",Pointer(m.templateRootNode_.get())},{"users",users},{"preserve",m.GetPreserveUserVolumesOnLoad()},
            {"path",m.GetGeometryConfigFile()},{"inputs",inputs},{"reader",Reader(m.effective_->reader)},
            {"main_reader",Reader(m.mainInputReader_)},{"accepted",m.effective_->accepted},
            {"generation",static_cast<std::int64_t>(m.effective_->generation)},
            {"fields",Fields(m.ExportEffectiveConfigFields())},{"evidence",m.ExportEffectiveConfigEvidence()},
            {"dirty",m.IsDirty()},{"registry_identity",Pointer(&m.GetRegistry())},{"registry_logical",logical},{"registry_physical",physical},
            {"sensitive",effective_config::List(m.registry_.GetSensitiveVolumeNames())},{"bias",effective_config::List(m.registry_.GetBiasVolumeNames())},
            {"regions",effective_config::List(m.GetRegionNames())}};
    }
};
int main(int argc,char** argv) {
    try {
        if(argc==2 && std::string(argv[1])=="--identity") {
            std::cout<<Value(O{{"source_fingerprint",G4USIM_SOURCE_FINGERPRINT},{"probe_sha256",G4USIM_TRANSACTION_PROBE_SHA256},
                {"geant4_version_number",G4VERSION_NUMBER},{"compiler",G4USIM_COMPILER_ID},{"compiler_version",G4USIM_COMPILER_VERSION}}).ToJson()<<"\n";return 0;
        }
        if(argc!=2)throw std::runtime_error("usage: geometryTransactionCheck OUTPUT_DIR | --identity");
        std::filesystem::path dir=std::filesystem::absolute(argv[1]);std::filesystem::create_directories(dir);
        A results; int failed=0;
        for(const std::string id:{"duplicate","missing_parent","second_overlay","projection","invalid_parse","early_validation","success_preserve","success_clear"}) {
            const auto folder=dir/id;std::filesystem::create_directories(folder);
            const auto a=folder/"A.ini", b=folder/"B.ini", c=folder/"C.ini";
            Write(a,Geometry("anchor")); Write(b,Geometry(id=="missing_parent"?"other":"collision",300));Write(c,Geometry("anchor",400));
            GeometryManager m;m.SetTemplate("hierarchical");m.LoadGeometryConfig(a.string());
            IniReader main; main.LoadBytes("main-accepted.ini","[geometry]\ntemplate=hierarchical\nconfig="+a.generic_string()+"\n");m.AcceptEffectiveConfig(main);
            if(id=="success_clear")m.SetPreserveUserVolumesOnLoad(false);
            if(id=="duplicate")m.AddVolume(User("collision","world"));
            else if(id=="missing_parent")m.AddVolume(User("user","anchor"));
            else if(id=="second_overlay") {m.AddVolume(User("first","world"));m.AddVolume(User("collision","world"));}
            else { auto n=User("user","anchor");if(id=="projection")n.userProperties["copyNo"]="not-an-integer";m.AddVolume(n); }
            if(id=="invalid_parse")Write(b,"[world\nsize=bad\n");
            if(id=="early_validation")Write(b,Geometry("other",-1));
            // Empty registry: construction receipts are unavailable until a real world exists.
            m.ClearDirty();
            const auto before=GeometryTransactionProbe::Snapshot(m);const auto ledgerBefore=Ledger();
            const bool success=id.rfind("success_",0)==0;
            const auto target=success?c:((id=="projection")?c:b);
            bool threw=false;std::string error;
            try {m.LoadGeometryConfig(target.string());}catch(const std::exception& e){threw=true;error=e.what();}
            const auto after=GeometryTransactionProbe::Snapshot(m);const auto ledgerAfter=Ledger();
            const auto& bo=std::get<O>(before.data);const auto& ao=std::get<O>(after.data);
            A checks;
            auto check=[&](const std::string& name,bool ok){checks.emplace_back(O{{"name",name},{"passed",ok}});if(!ok)++failed;};
            check("throws_iff_failure",threw!=success);
            check("no_geometry_objects",VolumeBuilder::GetCreatedGeometryObjectCount()==0);
            if(!success)check("complete_accepted_state_unchanged",before.ToJson()==after.ToJson());
            else {
                check("model_and_path_updated",m.GetGeometryConfigFile()==c.string() && ao.at("template_tree").ToJson()!=bo.at("template_tree").ToJson());
                check("generation_once",std::get<std::int64_t>(ao.at("generation").data)==std::get<std::int64_t>(bo.at("generation").data)+1);
                check("dirty",m.IsDirty());check("users_policy",m.GetUserAddedVolumes().size()==(id=="success_preserve"?1u:0u));
                check("final_tree_policy",m.HasVolumeInCurrentTree("user")== (id=="success_preserve"));
                check("accepted_input",std::get<A>(ao.at("inputs").data).size()==1 && ao.at("reader").ToJson().find(input_provenance::HashFile(c.string()).sha256)!=std::string::npos);
                check("accepted_fields_updated",ao.at("fields").ToJson()!=bo.at("fields").ToJson());
                check("prior_evidence_retained",ao.at("evidence").ToJson()==bo.at("evidence").ToJson());
            }
            bool read=false;
            const auto countBefore=std::get<A>(ledgerBefore.data).size();
            auto records=input_provenance::Snapshot();
            for(std::size_t i=countBefore;i<records.size();++i) if(records[i].path==target.string() && records[i].status=="recorded" && records[i].sha256==input_provenance::HashFile(target.string()).sha256)read=true;
            check("actual_read_retained_in_ledger",read);
            Value report=O{{"case",id},{"before",before},{"after",after},{"ledger_before",ledgerBefore},{"ledger_after",ledgerAfter},
                {"target",target.string()},{"threw",threw},{"error",error},{"checks",checks},{"created_geometry_object_count",static_cast<std::int64_t>(VolumeBuilder::GetCreatedGeometryObjectCount())}};
            Write(folder/"observation.json",report.ToJson()+"\n");results.push_back(report);
        }
        Write(dir/"results.json",Value(O{{"failed_checks",failed},{"cases",results},{"source_fingerprint",G4USIM_SOURCE_FINGERPRINT},
            {"probe_sha256",G4USIM_TRANSACTION_PROBE_SHA256},{"scope","unbuilt Manager; no global application Registry exists in this component"}}).ToJson()+"\n");
        std::cout<<"geometry transaction: "<<failed<<" failed checks; "<<dir.string()<<"\n";return failed?1:0;
    } catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 2;}
}
