#include "Materials/MaterialCommandParser.hh"
#include "Config/EffectiveRuntime.hh"
#include "Materials/MaterialManager.hh"

#include "Materials/MaterialFactory.hh"
#include "Materials/MaterialIniReader.hh"
#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include "G4Element.hh"
#include "G4Isotope.hh"
#include "G4Material.hh"
#include "G4NistManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4ios.hh"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <set>
#include <stdexcept>

namespace {

bool IsVolumeFractionMaterial(const MaterialDefinition& def)
{
    return !def.components.empty()
        && def.components.front().mode == MaterialComponentMode::ByVolumeFraction;
}

std::string DensityText(double density)
{
    return std::to_string(density / (g / cm3)) + " g/cm3";
}

bool MaterialLifecycleTraceEnabled()
{
#ifdef _WIN32
    char* value = nullptr;
    std::size_t size = 0;
    const errno_t result = _dupenv_s(&value, &size, "G4USIM_TEST_MATERIAL_LIFECYCLE");
    const bool enabled = result == 0 && value != nullptr;
    std::free(value);
    return enabled;
#else
    return std::getenv("G4USIM_TEST_MATERIAL_LIFECYCLE") != nullptr;
#endif
}

}  // namespace

MaterialManager::MaterialManager() = default;
MaterialManager::~MaterialManager() = default;

void MaterialManager::LoadMaterials(const std::string& filename)
{
    EnsureUnlocked("load materials");
    MaterialIniReader reader;
    reader.Load(filename);
    effectiveLoadInProgress_ = true;
    try {
        for (const std::string& nistName : reader.GetNistMaterialNames()) nistMaterialDefinitions_.push_back(nistName);
        for (const std::string& name : reader.GetIsotopeNames()) AddIsotopeDefinition(reader.GetIsotopeDefinition(name));
        for (const std::string& name : reader.GetElementNames()) AddElementDefinition(reader.GetElementDefinition(name));
        for (const std::string& name : reader.GetMaterialNames()) AddMaterialDefinition(reader.GetMaterialDefinition(name));
        if (MaterialLifecycleTraceEnabled()) {
            G4cout << "[MaterialLifecycle] build_started" << G4endl;
        }
        BuildAll();
        loadedConfigFiles_.push_back(FileUtils::AbsolutePath(filename));
        inputReaders_.push_back(reader.GetInputReader());
        effective_->Accept(effective_->reader,ProjectEffectiveConfigFields());
        effectiveLoadInProgress_=false;
        RecordEffectiveConfigObjects();
    } catch (...) {
        effectiveLoadInProgress_=false;
        effective_->Record(effective_config::Receipt("/materials/load",filename,"material_load","MaterialManager::LoadMaterials","none","failed","Load may have constructed partial objects; no successful configuration provenance was published"));
        // BuildAll may have installed a subset of definitions/Geant4 objects.
        // An unsuccessful load must never be reported as a clean source.
        incompleteConfigLoad_ = true;
        throw;
    }
}

const std::vector<std::string>& MaterialManager::GetLoadedConfigFiles() const
{
    return loadedConfigFiles_;
}

bool MaterialManager::HasNonFileConfigMutations() const
{
    return nonFileConfigMutations_;
}

bool MaterialManager::HasIncompleteConfigLoad() const
{
    return incompleteConfigLoad_;
}

void MaterialManager::MarkNonFileConfigMutation()
{
    nonFileConfigMutations_ = true;
}

std::size_t MaterialManager::GetCommandFailureCount() const
{
    return commandFailureCount_;
}

const std::string& MaterialManager::GetLastCommandFailure() const
{
    return lastCommandFailure_;
}

void MaterialManager::RecordCommandFailure(const std::string& error)
{
    ++commandFailureCount_;
    lastCommandFailure_ = error;
}

void MaterialManager::AddIsotopeDefinition(const IsotopeDefinition& def)
{
    EnsureUnlocked("add isotope definition");
    if (def.name.empty()) throw std::runtime_error("Cannot add isotope definition with empty name");
    isotopeDefinitions_[Normalize(def.name)] = def;
}

void MaterialManager::AddElementDefinition(const ElementDefinition& def)
{
    EnsureUnlocked("add element definition");
    if (def.name.empty()) throw std::runtime_error("Cannot add element definition with empty name");
    elementDefinitions_[Normalize(def.name)] = def;
}

void MaterialManager::AddMaterialDefinition(const MaterialDefinition& def)
{
    EnsureUnlocked("add material definition");
    if (def.name.empty()) throw std::runtime_error("Cannot add material definition with empty name");
    if (!StringUtils::Trim(def.temperatureText).empty() || !StringUtils::Trim(def.pressureText).empty()) {
        throw std::runtime_error(
            "Material '" + def.name + "' uses unsupported temperature/pressure fields. "
            "Remove temperature and pressure; current materials support density, state, and composition only."
        );
    }
    materialDefinitions_[Normalize(def.name)] = def;
}

G4Isotope* MaterialManager::BuildIsotope(const std::string& name)
{
    const std::string key = Normalize(name);
    const auto existing = isotopes_.find(key);
    if (existing != isotopes_.end()) return existing->second;
    const auto defIt = isotopeDefinitions_.find(key);
    if (defIt == isotopeDefinitions_.end()) throw std::runtime_error("Unknown isotope definition: '" + name + "'");

    MaterialFactory factory;
    G4Isotope* isotope = factory.BuildIsotope(defIt->second);
    RegisterIsotope(defIt->second.name, isotope);
    return isotope;
}

G4Element* MaterialManager::BuildElement(const std::string& name)
{
    const std::string key = Normalize(name);
    const auto existing = elements_.find(key);
    if (existing != elements_.end()) return existing->second;

    const auto defIt = elementDefinitions_.find(key);
    if (defIt == elementDefinitions_.end()) {
        G4Element* element = G4NistManager::Instance()->FindOrBuildElement(name, false);
        if (!element && StringUtils::StartsWith(name, "G4_")) {
            element = G4NistManager::Instance()->FindOrBuildElement(name.substr(3), false);
        }
        if (!element) throw std::runtime_error("Unknown element definition or NIST element: '" + name + "'");
        RegisterElement(name, element);
        return element;
    }

    const ElementDefinition& def = defIt->second;
    if (def.useIsotopes) {
        for (const IsotopeComponent& component : def.isotopes) BuildIsotope(component.isotopeName);
    }
    MaterialFactory factory;
    G4Element* element = factory.BuildElement(def, isotopes_);
    RegisterElement(def.name, element);
    return element;
}

G4Material* MaterialManager::BuildMaterial(const std::string& name)
{
    const std::string key = Normalize(name);
    const auto existing = materials_.find(key);
    if (existing != materials_.end()) return existing->second;

    const auto defIt = materialDefinitions_.find(key);
    if (defIt == materialDefinitions_.end()) return BuildNistMaterial(name);

    if (buildingMaterials_.count(key)) {
        std::string path;
        bool inCycle = false;
        for (const std::string& stackKey : buildingMaterialStack_) {
            if (stackKey == key) inCycle = true;
            if (!inCycle) continue;
            if (!path.empty()) path += " -> ";
            const auto stackIt = materialDefinitions_.find(stackKey);
            path += stackIt == materialDefinitions_.end() ? stackKey : stackIt->second.name;
        }
        if (!path.empty()) path += " -> ";
        path += defIt->second.name;
        throw std::runtime_error("Circular material dependency detected: " + path);
    }
    buildingMaterials_.insert(key);
    buildingMaterialStack_.push_back(key);
    try {
        G4Material* material = BuildCustomMaterial(defIt->second);
        buildingMaterials_.erase(key);
        buildingMaterialStack_.pop_back();
        return material;
    } catch (...) {
        buildingMaterials_.erase(key);
        buildingMaterialStack_.pop_back();
        throw;
    }
}

void MaterialManager::BuildAll()
{
    for (const std::string& nistName : nistMaterialDefinitions_) BuildNistMaterial(nistName);
    for (const auto& item : isotopeDefinitions_) BuildIsotope(item.second.name);
    for (const auto& item : elementDefinitions_) BuildElement(item.second.name);

    for (const auto& item : materialDefinitions_) BuildMaterial(item.second.name);
}

G4Material* MaterialManager::GetMaterial(const std::string& name) const
{
    const auto it = materials_.find(Normalize(name));
    if (it != materials_.end()) return it->second;
    G4Material* nist = G4NistManager::Instance()->FindOrBuildMaterial(name, false);
    if (nist) {
        const_cast<MaterialManager*>(this)->RegisterMaterial(name, nist);
        return nist;
    }
    throw std::runtime_error("Material not found: '" + name + "'");
}

G4Element* MaterialManager::GetElement(const std::string& name) const
{
    const auto it = elements_.find(Normalize(name));
    if (it != elements_.end()) return it->second;
    throw std::runtime_error("Element not found: '" + name + "'");
}

G4Isotope* MaterialManager::GetIsotope(const std::string& name) const
{
    const auto it = isotopes_.find(Normalize(name));
    if (it != isotopes_.end()) return it->second;
    throw std::runtime_error("Isotope not found: '" + name + "'");
}

bool MaterialManager::HasMaterial(const std::string& name) const
{
    return materials_.count(Normalize(name)) || materialDefinitions_.count(Normalize(name))
        || G4NistManager::Instance()->FindOrBuildMaterial(name, false) != nullptr;
}

bool MaterialManager::HasElement(const std::string& name) const
{
    return elements_.count(Normalize(name)) || elementDefinitions_.count(Normalize(name));
}

bool MaterialManager::HasIsotope(const std::string& name) const
{
    return isotopes_.count(Normalize(name)) || isotopeDefinitions_.count(Normalize(name));
}

G4Material* MaterialManager::BuildNistMaterial(const std::string& name)
{
    MaterialFactory factory;
    G4Material* material = factory.BuildNistMaterial(name);
    RegisterMaterial(name, material);
    return material;
}

G4Material* MaterialManager::BuildCustomMaterial(const MaterialDefinition& desc)
{
    if (desc.source == MaterialSourceType::Nist) {
        G4Material* material = BuildNistMaterial(desc.nistName.empty() ? desc.name : desc.nistName);
        RegisterMaterial(desc.name, material);
        return material;
    }
    for (const MaterialComponent& component : desc.components) {
        const std::string key = Normalize(component.name);
        if (component.mode == MaterialComponentMode::ByVolumeFraction) {
            if (materialDefinitions_.count(key)) BuildMaterial(component.name);
            else if (elementDefinitions_.count(key)) BuildElement(component.name);
        } else {
            if (elementDefinitions_.count(key)) BuildElement(component.name);
            else if (materialDefinitions_.count(key)) BuildMaterial(component.name);
        }
    }
    MaterialFactory factory;
    G4Material* material = factory.BuildCustomMaterial(desc, elements_, materials_);
    RegisterMaterial(desc.name, material);
    return material;
}

void MaterialManager::RegisterMaterial(const std::string& name, G4Material* material)
{
    if (!material) throw std::runtime_error("Cannot register null material: '" + name + "'");
    materials_[Normalize(name)] = material;
    if(!effectiveLoadInProgress_) RecordEffectiveConfigObjects();
}

void MaterialManager::RegisterElement(const std::string& name, G4Element* element)
{
    if (!element) throw std::runtime_error("Cannot register null element: '" + name + "'");
    elements_[Normalize(name)] = element;
    if(!effectiveLoadInProgress_) RecordEffectiveConfigObjects();
}

void MaterialManager::RegisterIsotope(const std::string& name, G4Isotope* isotope)
{
    if (!isotope) throw std::runtime_error("Cannot register null isotope: '" + name + "'");
    isotopes_[Normalize(name)] = isotope;
    if(!effectiveLoadInProgress_) RecordEffectiveConfigObjects();
}

std::vector<std::string> MaterialManager::GetMaterialNames() const
{
    std::vector<std::string> names;
    for (const auto& item : materials_) names.push_back(item.first);
    return names;
}

std::vector<std::string> MaterialManager::GetElementNames() const
{
    std::vector<std::string> names;
    for (const auto& item : elements_) names.push_back(item.first);
    return names;
}

std::vector<std::string> MaterialManager::GetIsotopeNames() const
{
    std::vector<std::string> names;
    for (const auto& item : isotopes_) names.push_back(item.first);
    return names;
}

void MaterialManager::PrintMaterials() const
{
    G4cout << "[MaterialManager] Materials:" << G4endl;
    for (const auto& item : materials_) {
        G4cout << "  " << item.first << " -> " << item.second->GetName();
        const auto defIt = materialDefinitions_.find(item.first);
        if (defIt != materialDefinitions_.end() && IsVolumeFractionMaterial(defIt->second)) {
            const MaterialDefinition& def = defIt->second;
            double idealDensity = 0.0;
            struct PrintComponent {
                std::string name;
                double volumeFraction = 0.0;
                double density = 0.0;
                double massFraction = 0.0;
            };
            std::vector<PrintComponent> components;
            bool printable = true;
            for (const auto& component : def.components) {
                G4Material* subMaterial = nullptr;
                const auto subIt = materials_.find(Normalize(component.name));
                if (subIt != materials_.end()) subMaterial = subIt->second;
                else subMaterial = G4NistManager::Instance()->FindOrBuildMaterial(component.name, false);
                if (!subMaterial || subMaterial->GetDensity() <= 0.0 || !std::isfinite(subMaterial->GetDensity())) {
                    printable = false;
                    break;
                }
                PrintComponent pc;
                pc.name = component.name;
                pc.volumeFraction = component.fraction;
                pc.density = subMaterial->GetDensity();
                components.push_back(pc);
                idealDensity += pc.volumeFraction * pc.density;
            }
            G4cout << " (mode=volume_fraction";
            if (def.HasExplicitDensity()) G4cout << ", configuredDensity=" << DensityText(def.density);
            else G4cout << ", configuredDensity=auto";
            if (printable && idealDensity > 0.0) {
                G4cout << ", idealDensity=" << DensityText(idealDensity)
                       << ", finalDensity=" << DensityText(item.second->GetDensity());
            }
            G4cout << ")";
            if (printable && idealDensity > 0.0) {
                G4cout << G4endl;
                for (auto& component : components) {
                    component.massFraction = component.volumeFraction * component.density / idealDensity;
                    G4cout << "    " << component.name
                           << ": v=" << component.volumeFraction
                           << ", rho=" << DensityText(component.density)
                           << ", w=" << component.massFraction << G4endl;
                }
                continue;
            }
        }
        G4cout << G4endl;
    }
}

void MaterialManager::PrintElements() const
{
    G4cout << "[MaterialManager] Elements:" << G4endl;
    for (const auto& item : elements_) G4cout << "  " << item.first << " -> " << item.second->GetName() << G4endl;
}

void MaterialManager::PrintIsotopes() const
{
    G4cout << "[MaterialManager] Isotopes:" << G4endl;
    for (const auto& item : isotopes_) G4cout << "  " << item.first << " -> " << item.second->GetName() << G4endl;
}

void MaterialManager::PrintAll() const
{
    PrintIsotopes();
    PrintElements();
    PrintMaterials();
}

void MaterialManager::Clear()
{
    nonFileConfigMutations_ = true;
    isotopeDefinitions_.clear();
    elementDefinitions_.clear();
    materialDefinitions_.clear();
    nistMaterialDefinitions_.clear();
    isotopes_.clear();
    elements_.clear();
    materials_.clear();
    buildingMaterials_.clear();
    buildingMaterialStack_.clear();
    inputReaders_.clear();effectiveNistAliases_.clear();
    effective_->Accept(effective_->reader,ProjectEffectiveConfigFields());
}

void MaterialManager::SetLocked(bool locked)
{
    locked_ = locked;
    if (locked_) G4cout << "[MaterialManager] Locked. New definitions will be rejected." << G4endl;
}

bool MaterialManager::IsLocked() const
{
    return locked_;
}

std::string MaterialManager::Normalize(const std::string& name)
{
    return StringUtils::ToLower(StringUtils::Trim(name));
}

void MaterialManager::EnsureUnlocked(const std::string& action) const
{
    if (locked_) {
        throw std::runtime_error(
            "MaterialManager is locked; cannot " + action
            + ". Existing geometry will not update automatically after material changes."
        );
    }
}

std::vector<effective_config::Field> MaterialManager::ProjectEffectiveConfigFields() const
{
 using namespace effective_config;std::vector<Field> result;
 const auto field=[&](const std::string& type,const std::string& name,const char* key,Value value,const char* unit,std::initializer_list<const char*> keys){
  const auto path=ObjectFieldPath("materials",type+":"+name,key);ConsumerState fallback;
  Field f=fallback.Make(path,std::move(value),unit,Normalize(type+"."+name),{});
  f.origins.front().kind="runtime_unattributed";
  const auto section=Normalize(type+"."+name);
  for(const auto& reader:inputReaders_){ConsumerState source;source.reader=reader;
   auto fragment=source.Make(path,f.resolved,unit,section,keys);
   if(fragment.origins.size()==1 && type=="material")fragment=source.Make(path,f.resolved,unit,Normalize(name),{"material"});
   if(fragment.origins.size()>1){
    // MaterialIniReader processes its case-preserving section map in lexical
    // order. Preserve that existing behavior even when differently cased
    // declarations normalize to one definition; do not invent last-line wins.
    const auto declarations=reader.GetDeclarations();std::string selectedSection;
    const auto normalizedSection=Normalize(fragment.origins.back().section);
    for(const auto& d:declarations)if(d.normalizedSection==normalizedSection && d.originalSection>selectedSection)selectedSection=d.originalSection;
    for(auto& origin:fragment.origins)if(origin.kind=="main_ini")origin.disposition="shadowed";
    for(const char* key:keys){const IniFieldInfo* winner=nullptr;
     for(const auto& d:declarations)if(d.originalSection==selectedSection && d.normalizedKey==key)winner=&d;
     if(winner){fragment.requested=winner->value;fragment.requested_known=true;
      for(auto& origin:fragment.origins)if(origin.kind=="main_ini" && origin.line==winner->lineNumber)origin.disposition="accepted";}
    }
    if(f.origins.size()==1 && f.origins.front().kind=="runtime_unattributed")f.origins.clear();
    for(auto& o:f.origins)if(o.disposition!="shadowed")o.disposition="shadowed";
    f.origins.insert(f.origins.end(),fragment.origins.begin()+1,fragment.origins.end());f.requested=fragment.requested;f.requested_known=fragment.requested_known;}
  }
  result.push_back(std::move(f));
 };
 for(const auto& entry:isotopeDefinitions_){const auto& d=entry.second;
  field("isotope",d.name,"symbol",d.symbol,"",{"symbol"});field("isotope",d.name,"z",d.z,"",{"z"});
  field("isotope",d.name,"n",d.n,"",{"n"});field("isotope",d.name,"a",d.a/(g/mole),"g/mole",{"a"});
 }
 for(const auto& entry:elementDefinitions_){const auto& d=entry.second;
  field("element",d.name,"symbol",d.symbol,"",{"symbol"});field("element",d.name,"use_isotopes",d.useIsotopes,"",{"isotopes"});
  if(d.useIsotopes){Value::Array isotopes;for(const auto& c:d.isotopes)isotopes.emplace_back(Value::Object{{"name",c.isotopeName},{"abundance",c.abundance}});field("element",d.name,"isotopes",isotopes,"fraction",{"isotopes"});}
  else {field("element",d.name,"z",d.z,"",{"z"});field("element",d.name,"a",d.a/(g/mole),"g/mole",{"a"});}
 }
 for(const auto& entry:materialDefinitions_){const auto& d=entry.second;
  field("material",d.name,"source",d.source==MaterialSourceType::Nist?"nist":"custom","",{"material"});
  if(d.source==MaterialSourceType::Nist){field("material",d.name,"nist_name",d.nistName,"",{"material"});continue;}
  field("material",d.name,"density_auto",d.densityAuto,"",{"density","mode"});
  if(d.HasExplicitDensity())field("material",d.name,"density",d.density/(g/cm3),"g/cm3",{"density"});
  if(!d.state.empty())field("material",d.name,"state",StringUtils::ToLower(d.state),"",{"state"});
  Value::Array components;
  for(const auto& c:d.components){const char* mode=c.mode==MaterialComponentMode::ByAtomCount?"atom_count":(c.mode==MaterialComponentMode::ByVolumeFraction?"volume_fraction":"mass_fraction");
   components.emplace_back(Value::Object{{"name",c.name},{"mode",mode},{"amount",c.mode==MaterialComponentMode::ByAtomCount?Value(c.atomCount):Value(c.fraction)}});}
  field("material",d.name,"components",components,"",{"mode","components"});
  if(d.isElement){field("material",d.name,"element_symbol",d.element.symbol,"",{});field("material",d.name,"element_z",d.element.z,"",{});field("material",d.name,"element_a",d.element.a/(g/mole),"g/mole",{});}
 }
 for(const auto& alias:effectiveNistAliases_)if(!materialDefinitions_.count(Normalize(alias.first))){
  field("material",alias.first,"source","nist","",{});field("material",alias.first,"nist_name",alias.second,"",{});
 }
 Field lock;lock.path=FieldPath("materials","edit_locked");lock.resolved=locked_;lock.requested_known=false;lock.evidence_level=EvidenceLevel::ManagerAccepted;result.push_back(std::move(lock));
 Field nist; nist.path=FieldPath("materials","nist_requests");nist.resolved=List(nistMaterialDefinitions_);nist.requested_known=false;nist.evidence_level=EvidenceLevel::ManagerAccepted;
 for(const auto& reader:inputReaders_){ConsumerState state;state.reader=reader;auto f=state.Make(nist.path,nist.resolved,"","nist",{"materials"});if(f.origins.size()>1){nist.origins.insert(nist.origins.end(),f.origins.begin()+1,f.origins.end());nist.requested=f.requested;nist.requested_known=true;}}
 result.push_back(std::move(nist));
 Value::Array inputs;for(const auto& reader:inputReaders_)inputs.emplace_back(Value::Object{{"path",reader.GetFilename()},{"sha256",reader.GetInputSha256()}});
 Field input;input.path=FieldPath("materials","input_files");input.resolved=inputs;input.requested_known=false;input.evidence_level=EvidenceLevel::ManagerAccepted;result.push_back(std::move(input));
 return result;
}
std::vector<effective_config::Field> MaterialManager::ExportEffectiveConfigFields() const {return effective_->accepted?effective_->fields:ProjectEffectiveConfigFields();}
effective_config::Value MaterialManager::ExportEffectiveConfigEvidence() const {return effective_->Evidence();}
void MaterialManager::ConfirmEffectiveConfigMutation(const std::string& command,const effective_config::Origin& origin)
{
 const auto space=command.find_first_of(" \t");
 const auto name=StringUtils::ToLower(command.substr(0,space));
 const auto arguments=space==std::string::npos?std::string():command.substr(space+1);
 std::map<std::string,std::string> values;
 if(name.find("/add")!=std::string::npos)values=MaterialCommandParser::ParseKeyValueLine(arguments);
 std::string object=values.count("name")?values.at("name"):std::string();
 if(name.find("addnist")!=std::string::npos && values.count("nist")) {
  if(object.empty())object=values.at("nist");effectiveNistAliases_[object]=values.at("nist");
 }
 auto fields=ProjectEffectiveConfigFields();std::vector<std::string> targets;
 const std::string type=name.find("addelement")!=std::string::npos?"element":(name.find("addisotope")!=std::string::npos?"isotope":"material");
 const auto prefix=object.empty()?std::string():"/materials/objects/"+effective_config::EscapePointerToken(type+":"+object)+"/";
 for(const auto& f:fields){
  if((!prefix.empty() && f.path.compare(0,prefix.size(),prefix)==0) ||
     (name.find("load")!=std::string::npos) ||
     (name.find("setlocked")!=std::string::npos && f.path=="/materials/edit_locked"))targets.push_back(f.path);
 }
 effective_->Confirm(std::move(fields),command,origin,false,targets);
 RecordEffectiveConfigObjects();
}
void MaterialManager::RecordEffectiveConfigObjects() const
{
 using namespace effective_config;
 const auto record=[&](const std::string& path,Value observed){
  const auto found=std::find_if(effective_->fields.begin(),effective_->fields.end(),[&](const Field& f){return f.path==path;});
  const bool matches=found==effective_->fields.end() || found->resolved.ToJson()==observed.ToJson();
  effective_->Record(Receipt(path,std::move(observed),"material_construct","Actual registered Geant4 material/element/isotope readback","kernel_constructed",matches?"applied":"unknown",matches?"":"Existing Geant4 object differs from current definition; no redefinition is claimed"));
 };
 Value::Array nistObserved;
 for(const auto& name:nistMaterialDefinitions_){const auto found=materials_.find(Normalize(name));nistObserved.emplace_back(found!=materials_.end() && found->second?Value(found->second->GetName()):Value());}
 if(!nistMaterialDefinitions_.empty())record(FieldPath("materials","nist_requests"),nistObserved);
 for(const auto& entry:isotopes_){const auto* object=entry.second;if(!object)continue;const auto found=isotopeDefinitions_.find(entry.first);const auto name=found==isotopeDefinitions_.end()?entry.first:found->second.name;
  record(ObjectFieldPath("materials","isotope:"+name,"z"),object->GetZ());record(ObjectFieldPath("materials","isotope:"+name,"n"),object->GetN());record(ObjectFieldPath("materials","isotope:"+name,"a"),object->GetA()/(g/mole));}
 for(const auto& entry:elements_){const auto* object=entry.second;if(!object)continue;const auto found=elementDefinitions_.find(entry.first);const auto name=found==elementDefinitions_.end()?entry.first:found->second.name;
  record(ObjectFieldPath("materials","element:"+name,"z"),object->GetZ());record(ObjectFieldPath("materials","element:"+name,"a"),object->GetA()/(g/mole));
  record(ObjectFieldPath("materials","element:"+name,"symbol"),object->GetSymbol());
  if(found!=elementDefinitions_.end() && found->second.useIsotopes){Value::Array isotopes;
   const auto* abundances=object->GetRelativeAbundanceVector();const auto* vector=object->GetIsotopeVector();
   if(vector && abundances)for(std::size_t i=0;i<object->GetNumberOfIsotopes();++i)isotopes.emplace_back(Value::Object{{"name",(*vector)[i]->GetName()},{"abundance",abundances[i]}});
   record(ObjectFieldPath("materials","element:"+name,"isotopes"),isotopes);
  }
 }
 for(const auto& entry:materials_){const auto* object=entry.second;if(!object)continue;const auto found=materialDefinitions_.find(entry.first);const auto name=found==materialDefinitions_.end()?entry.first:found->second.name;
  record(ObjectFieldPath("materials","material:"+name,"density"),object->GetDensity()/(g/cm3));
  Value::Array elements;const auto* fractions=object->GetFractionVector();for(std::size_t i=0;i<object->GetNumberOfElements();++i)elements.emplace_back(Value::Object{{"element",(*object->GetElementVector())[i]->GetName()},{"mass_fraction",fractions?Value(fractions[i]):Value()}});
  effective_->Record(Receipt(ObjectFieldPath("materials","material:"+name,"composition_observed"),elements,"material_construct","Actual G4Material element mass fractions"));
 }
}
