#include "BuildInfo.hh"
#include "Config/ConfigManager.hh"
#include "Config/InputProvenance.hh"
#include "Geometry/GeometryConfig.hh"
#include "Materials/MaterialIniReader.hh"
#include "Materials/MaterialManager.hh"
#include "Source/SourceManager.hh"
#include "G4Material.hh"
#include "G4SystemOfUnits.hh"
#include "G4Version.hh"
#include <algorithm>
#include <sstream>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <stdexcept>
using effective_config::Value;
using O = Value::Object;
using A = Value::Array;
namespace {
A checks, observations;
int failures = 0;
void Check(const std::string& name, bool ok) {
    checks.emplace_back(O{{"name", name}, {"passed", ok}});
    if (!ok) ++failures;
}
void Write(const std::filesystem::path& path, const std::string& bytes) {
    std::ofstream out(path, std::ios::binary); out << bytes; out.close();
    if (!out) throw std::runtime_error("cannot write " + path.string());
}
std::string Read(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot read " + path.string());
    return {std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
}
template<class F> void Reject(const std::string& name, F action, const std::string& diagnostic = "") {
    std::string error;
    try { action(); } catch (const std::exception& e) { error = e.what(); }
    Check(name + ":reject", !error.empty());
    if (!diagnostic.empty()) Check(name + ":diagnostic", error.find(diagnostic) != std::string::npos);
    observations.emplace_back(O{{"case", name}, {"error", error}});
}
O Identity() {
    return {{"source_fingerprint", G4USIM_SOURCE_FINGERPRINT},
        {"probe_sha256", G4USIM_INI_READER_CONTRACT_PROBE_SHA256},
        {"geant4_version_number", G4VERSION_NUMBER},
        {"compiler", G4USIM_COMPILER_ID}, {"compiler_version", G4USIM_COMPILER_VERSION}};
}
void ReaderEvidence(const IniReader& reader, const std::string& bytes, const std::string& name, int sectionLine) {
    Check(name + ":sha", reader.GetInputSha256() == input_provenance::Sha256(bytes));
    const auto declarations = reader.GetSectionDeclarations();
    Check(name + ":line", !declarations.empty() && declarations.front().lineNumber == std::size_t(sectionLine));
    for (const auto& field : reader.GetDeclarations()) {
        std::istringstream input(bytes); std::string raw;
        for (std::size_t i = 0; i < field.lineNumber; ++i) std::getline(input, raw);
        Check(name + ":raw:" + std::to_string(field.lineNumber), raw == field.rawLine);
    }
}
const std::string geometry = "[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_AIR\n";
const std::string rectangle = "[source]\nparticle=proton\nenergy=10 MeV\nposition_type=plane\nshape=rectangle\ncenter=1 mm,2 mm,3 mm\nhalfx=2 mm\nhalfy=3 mm\ndirection=0,0,1\n";
void ObserveSource(const std::string& bytes, const std::string& name, double x, double y) {
    ConfigManager config; config.LoadMainConfigBytes(name, bytes);
    SourceManager source; source.LoadFromConfig(config);
    const auto& sources = source.GetSources();
    Check(name + ":count", sources.size() == 1);
    if (sources.size() != 1) return;
    const auto& s = sources.front();
    Check(name + ":rectangle", s.positionType == "Plane" && s.positionShape == "Rectangle");
    Check(name + ":params", s.positionParams.size() == 5);
    if (s.positionParams.size() == 5) {
        Check(name + ":halfwidths", std::isfinite(s.positionParams[3]) && std::isfinite(s.positionParams[4]) &&
            std::abs(s.positionParams[3] - x) <= 1e-12*std::max(1.,x) && std::abs(s.positionParams[4] - y) <= 1e-12*std::max(1.,y));
        Check(name + ":center", s.positionParams[0] == mm && s.positionParams[1] == 2*mm && s.positionParams[2] == 3*mm);
        observations.emplace_back(O{{"case", name}, {"position_type", s.positionType}, {"shape", s.positionShape},
            {"halfx_mm", s.positionParams[3]/mm}, {"halfy_mm", s.positionParams[4]/mm}});
    }
    Check(name + ":no_gps", !source.HasGPS());
}
std::string Replace(std::string text, const std::string& from, const std::string& to) {
    const auto at = text.find(from); if (at == std::string::npos) throw std::runtime_error("fixture replacement missing");
    text.replace(at, from.size(), to); return text;
}
}
int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--identity") { std::cout << Value(Identity()).ToJson() << '\n'; return 0; }
        if (argc != 2) throw std::runtime_error("usage: iniReaderContractCheck NEW_OUTPUT_DIR | --identity (no BeamOn)");
        const auto dir = std::filesystem::absolute(argv[1]);
        if (!std::filesystem::create_directory(dir)) throw std::runtime_error("output directory must be new");
        const std::string bom = "\xEF\xBB\xBF";
        for (int hasBom=0; hasBom<2; ++hasBom) for (int comment=0; comment<2; ++comment) for (int crlf=0; crlf<2; ++crlf) {
            const std::string id = std::to_string(hasBom)+std::to_string(comment)+std::to_string(crlf);
            auto bytes = [&](std::string text) {
                if (comment) text = "; comment\n" + text;
                if (crlf) { std::string converted; for(char c:text) { if(c=='\n') converted+='\r'; converted+=c; } text=converted; }
                return (hasBom ? bom : "") + text;
            };
            const auto material = dir/("material-"+id+".ini"); const auto geo = dir/("geometry-"+id+".ini");
            Write(material, bytes("[Water]\nmaterial=G4_WATER\n")); Write(geo, bytes(geometry));
            MaterialIniReader mr; mr.Load(material.string());
            Check(id+":target", mr.GetMaterialDefinition("water").nistName == "G4_WATER");
            ReaderEvidence(mr.GetInputReader(), Read(material), id+":material", comment+1);
            GeometryConfig gc; gc.Load(geo.string()); Check(id+":world", gc.HasVolume("world"));
            ReaderEvidence(gc.GetInputReader(), Read(geo), id+":geometry", comment+1);
            ConfigManager cm; cm.LoadMainConfigBytes("main-"+id, bytes(rectangle));
            ReaderEvidence(cm.GetMainReader(), bytes(rectangle), id+":main", comment+1);
            ObserveSource(bytes(rectangle), id+":source",2*mm,3*mm);
        }
        IniReader raw; raw.LoadBytes("first-field.ini", bom+"x=1\r\n");
        Check("first_field_raw_BOM", raw.GetDeclarations().at(0).rawLine == bom+"x=1\r");
        int bomNegative = 0;
        for (const auto& bad : {" "+bom+"[x]\na=1\n", bom+bom+"[x]\na=1\n", "\n"+bom+"[x]\na=1\n"})
            Reject("nonleading_or_multiple_BOM_"+std::to_string(bomNegative++), [&]{ IniReader r;r.LoadBytes("bad.ini",bad); });
        Reject("physical_line", [&]{IniReader r;r.LoadBytes("bad-line.ini",bom+"; comment\n[x]\nnot a field\n");}, "3");
        for (const auto& item : std::vector<std::pair<std::string,std::string>>{
            {"version",bom+"[global]\nversion=2\nversion=2\n"+geometry},
            {"section",bom+"[world]\nshape=box\n[world]\nsize=1,1,1\nmaterial=G4_AIR\n[global]\nversion=2\n"},
            {"key",bom+"[world]\nshape=box\nshape=box\nsize=1,1,1\nmaterial=G4_AIR\n[global]\nversion=2\n"}}) {
            const auto f=dir/(item.first+".ini");Write(f,item.second);
            Reject("geometry_duplicate_"+item.first,[&]{GeometryConfig g;g.Load(f.string());}, "duplicate");
        }
        const auto good=dir/"good-material.ini";Write(good,"[Water]\nmaterial=G4_WATER\n");
        MaterialIniReader reader;reader.Load(good.string());const auto oldSha=reader.GetInputReader().GetInputSha256();
        MaterialManager manager;manager.LoadMaterials(good.string());auto* water=manager.GetMaterial("Water");
        Check("nist_target",water && water->GetName()=="G4_WATER");
        Check("alias_case",water==manager.GetMaterial("water") && water==manager.GetMaterial("WATER"));
        const auto evidence=manager.ExportEffectiveConfigEvidence().ToJson(); const auto files=manager.GetLoadedConfigFiles();
        int duplicate=0;
        for (const auto& second : {"Water", "water", " Water "}) for (const auto& target : {"G4_WATER","G4_AIR"}) for (int reverse=0; reverse<2; ++reverse) {
            const std::string id="duplicate-"+std::to_string(duplicate++);const auto f=dir/(id+".ini");
            const std::string first="[Water]\r\nmaterial=G4_WATER\r\n";
            const std::string other=std::string("[")+second+"]\r\nmaterial="+target+"\r\n";
            Write(f,bom+(reverse ? other+first : first+other));
            Reject(id+":reader",[&]{reader.Load(f.string());},"duplicate legacy material alias");
            Check(id+":reader_unchanged",reader.GetInputReader().GetInputSha256()==oldSha && reader.GetMaterialDefinition("water").nistName=="G4_WATER");
            const auto count=G4Material::GetMaterialTable()->size();
            Reject(id+":manager",[&]{manager.LoadMaterials(f.string());},"line 3");
            Check(id+":manager_unchanged",manager.GetMaterial("Water")==water && manager.GetLoadedConfigFiles()==files && !manager.HasIncompleteConfigLoad() && manager.ExportEffectiveConfigEvidence().ToJson()==evidence);
            Check(id+":no_materials_created",G4Material::GetMaterialTable()->size()==count);
        }
        const auto schema=dir/"schema-first.ini";Write(schema,"[Water]\nmaterial=G4_WATER\nbad=1\n[Water]\nmaterial=G4_AIR\n");
        Reject("schema_before_duplicate",[&]{reader.Load(schema.string());},"unknown material configuration key");
        const auto modern=dir/"modern.ini";Write(modern,"[material.Coating]\ndensity=1 g/cm3\ndensity=2 g/cm3\ncomponents=G4_C:1\n[material.Coating]\nstate=solid\n");
        MaterialIniReader modernReader;modernReader.Load(modern.string());
        Check("modern_duplicates_preserved",modernReader.GetMaterialDefinition("Coating").densityText=="2 g/cm3" && modernReader.GetInputReader().GetDuplicates().size()==2);
        const auto secondFile=dir/"second-file.ini";Write(secondFile,"[WATER]\nmaterial=G4_WATER\n");manager.LoadMaterials(secondFile.string());
        Check("cross_file_load_preserved",manager.GetLoadedConfigFiles().size()==files.size()+1);
        MaterialDefinition definition;definition.name="Direct";definition.source=MaterialSourceType::Nist;definition.nistName="G4_WATER";
        manager.AddMaterialDefinition(definition);definition.name="direct";manager.AddMaterialDefinition(definition);
        Check("direct_add_preserved",manager.HasMaterial("DIRECT"));
        for(const auto& unit : std::vector<std::pair<std::string,double>>{{"nm",1e-6*mm},{"um",1e-3*mm},{"mm",mm},{"cm",cm},{"m",m}}) {
            for(const auto& field : {"halfx","halfy"}) {
                auto text=Replace(rectangle,std::string(field)+ (std::string(field)=="halfx"?"=2 mm":"=3 mm"),std::string(field)+"=2 "+unit.first);
                ObserveSource(text,std::string(field)+unit.first,std::string(field)=="halfx"?2*unit.second:2*mm,std::string(field)=="halfy"?2*unit.second:3*mm);
            }
        }
        for(const auto& value : {"2 km","2 MM","0 mm","-1 mm","nan mm","inf mm","1e309 mm","1e308 m"}) for(const auto& field : {"halfx","halfy"}) {
            const auto text=Replace(rectangle,std::string(field)+(std::string(field)=="halfx"?"=2 mm":"=3 mm"),std::string(field)+"="+value);
            Reject(std::string(field)+value,[&]{ConfigManager c;c.LoadMainConfigBytes("source-bad.ini",text);SourceManager s;s.LoadFromConfig(c);});
        }
        const std::string point="[source]\nparticle=proton\nenergy=10 MeV\nposition_type=point\nposition=0,0,0 mm\n";
        {ConfigManager c;c.LoadMainConfigBytes("point.ini",point);SourceManager s;s.LoadFromConfig(c);Check("point_positive",s.GetSources().at(0).positionType=="Point");}
        for(const auto& value : {"","point","rectangle","circle","POINT"})
            Reject(std::string("point_shape_")+value,[&]{ConfigManager c;c.LoadMainConfigBytes("point-bad.ini",point+"shape="+value+"\n");SourceManager s;s.LoadFromConfig(c);},"conflicts");
        auto result=Identity();result["checks"]=checks;result["observations"]=observations;result["failed_checks"]=failures;
        result["check_count"]=static_cast<int>(checks.size());result["no_transport"]=true;
        Write(dir/"results.json",Value(result).ToJson());
        std::cout<<checks.size()<<" checks; "<<failures<<" failed\n";return failures?1:0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 2;}
}
