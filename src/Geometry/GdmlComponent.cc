#include "Geometry/GdmlComponent.hh"
#include <stdexcept>
#ifdef G4USIM_HAVE_GDML
#include "Geometry/GdmlAffineBox.hh"
#include "G4GDMLParser.hh"
#include "G4Box.hh"
#include "G4Para.hh"
#include "G4PVPlacement.hh"
#include "G4GDMLReadStructure.hh"
#include "G4LogicalVolumeStore.hh"
#include "G4SolidStore.hh"
#include "G4Material.hh"
#include "G4GeometryTolerance.hh"
#include "G4PhysicalConstants.hh"
#include "G4UnitsTable.hh"
#include <cmath>
#include <limits>
#include "G4VPhysicalVolume.hh"
#include "G4LogicalVolume.hh"
#include <xercesc/dom/DOM.hpp>
#include <xercesc/util/XMLString.hpp>
#include <algorithm>
#include <charconv>
#include <filesystem>
#include <functional>
#include <set>

namespace {
using Element = xercesc::DOMElement;
struct Xml {
    XMLCh* value;
    explicit Xml(const std::string& s):value(xercesc::XMLString::transcode(s.c_str())) {}
    ~Xml(){xercesc::XMLString::release(&value);}
    Xml(const Xml&) = delete;
};
std::string text(const XMLCh* s) {
    char* p=xercesc::XMLString::transcode(s);
    std::string result=p; xercesc::XMLString::release(&p);
    return result;
}
std::string tag(const Element* e){return text(e->getTagName());}
std::string attr(const Element* e,const char* key){return text(e->getAttribute(Xml(key).value));}
void set(Element* e,const char* key,const std::string& v){e->setAttribute(Xml(key).value,Xml(v).value);}
std::vector<Element*> children(const Element* e) {
    std::vector<Element*> result;
    for(auto* child=e->getFirstElementChild();child;child=child->getNextElementSibling())result.push_back(child);
    return result;
}
void require(bool condition,const std::string& message) {
    if(!condition)throw std::runtime_error("GDML component: "+message);
}
void attributes(const Element* e,std::initializer_list<const char*> allowed) {
    const auto* map=e->getAttributes();
    for(XMLSize_t i=0;i<map->getLength();++i) {
        const auto name=text(map->item(i)->getNodeName());
        require(std::find(allowed.begin(),allowed.end(),name)!=allowed.end(),"unsupported "+tag(e)+" attribute '"+name+"'");
    }
}
double unit(const Element* e,const char* field,const char* fallback,const char* category) {
    auto symbol=attr(e,field);
    if(symbol.empty())symbol=fallback;
    require(G4UnitDefinition::IsUnitDefined(symbol) && G4UnitDefinition::GetCategory(symbol)==category,
            tag(e)+" requires a "+category+" unit, got '"+symbol+"'");
    return G4UnitDefinition::GetValueOf(symbol);
}
double number(const Element* e,const char* field,double multiplier=1) {
    const auto raw=attr(e,field);
    require(!raw.empty() && raw.find_first_not_of("0123456789+-.eE")==std::string::npos,
            tag(e)+" "+field+" requires a decimal literal, got '"+raw+"'");
    // from_chars accepts a sign in the exponent but not a leading plus.
    const auto* first=raw.data();
    const auto* last=first+raw.size();
    if(*first=='+') {
        ++first;
        require(first!=last && *first!='-' && *first!='+',tag(e)+" "+field+" has an invalid sign");
    }
    double parsed=0;
    const auto conversion=std::from_chars(first,last,parsed,std::chars_format::general);
    require(conversion.ec==std::errc{} && conversion.ptr==last,
            tag(e)+" "+field+" is not a finite decimal literal");
    const double value=parsed*multiplier;
    require(std::isfinite(value),tag(e)+" "+field+" is not finite");
    return value;
}
void validateBox(const Element* e) {
    attributes(e,{"name","lunit","x","y","z"});
    require(children(e).empty(),"box cannot contain child declarations");
    const double u=unit(e,"lunit","mm","Length");
    double volume=1;
    for(const char* key:{"x","y","z"}) {
        const double length=number(e,key,u);
        require(length*0.5>2*G4GeometryTolerance::GetInstance()->GetSurfaceTolerance(),
                "box dimension "+std::string(key)+" must exceed the solid tolerance");
        volume*=length;
    }
    require(std::isfinite(volume) && volume>0,"box volume is not representable");
}
void validatePose(const Element* e) {
    attributes(e,{"name","unit","x","y","z"});
    require(children(e).empty(),"inline pose must contain only numeric attributes");
    const bool angle=tag(e)=="rotation";
    const double u=unit(e,"unit",angle?"rad":"mm",angle?"Angle":"Length");
    for(const char* key:{"x","y","z"})if(!attr(e,key).empty())number(e,key,u);
}
using Elements=std::map<std::string,Element*>;
class ComponentReader final : public G4GDMLReadStructure {
public:
    ComponentReader(std::string root,std::string instance,bool build):selector(std::move(root)),
        prefix("G4USimPart_"+std::to_string(instance.size())+"_"+instance+"_"),construct(build) {}
    std::function<void()> confirmInput;
    std::array<double,3> scales{1,1,1};
    bool overlaps=false;
    GdmlIO::Component result;
    std::string error;
    bool scaleError=false;
    void DefineRead(const Element* e) override {dispatch(e);}
    void MaterialsRead(const Element* e) override {dispatch(e);}
    void SolidsRead(const Element* e) override {dispatch(e);}
    void StructureRead(const Element* e) override {dispatch(e);}
    void SetupRead(const Element* e) override {dispatch(e);}
    void UserinfoRead(const Element* e) override {dispatch(e);}
    void ExtensionRead(const Element* e) override {dispatch(e);}
private:
    std::string selector,prefix;
    bool construct, handled=false;
    Elements volumes, solids, materials;
    std::set<std::string> visiting,selected,usedSolids,usedMaterials;
    std::vector<std::string> order;
    static void index(const Element* section,Elements& out) {
        for(auto* e:children(section)) {
            auto name=attr(e,"name");
            require(!name.empty() && out.emplace(name,e).second,"missing or ambiguous name '"+name+"' in "+tag(section));
        }
    }
    void visit(const std::string& name) {
        require(volumes.count(name),"missing logical root or daughter '"+name+"'");
        if(selected.count(name))return;
        if(scales!=std::array<double,3>{1,1,1})
            require(visiting.size()<256,"scaled subtree exceeds 256 logical levels");
        attributes(volumes.at(name),{"name"});
        require(visiting.insert(name).second,"cyclic volume reference '"+name+"'");
        std::set<std::pair<std::string,int>> placements;
        unsigned materialCount=0,solidCount=0;
        for(auto* e:children(volumes.at(name))) {
            auto t=tag(e),ref=attr(e,"ref");
            if(t=="solidref") {
                attributes(e,{"ref"});
                ++solidCount; require(solids.count(ref),"missing solid '"+ref+"'");
                require(tag(solids.at(ref))=="box","unsupported selected solid '"+tag(solids.at(ref))+"'");
                validateBox(solids.at(ref));
                usedSolids.insert(ref);
            } else if(t=="materialref") {
                attributes(e,{"ref"});
                ++materialCount; require(materials.count(ref),"missing locally declared material '"+ref+"'");
                auto* m=materials.at(ref);require(tag(m)=="material","unsupported material reference '"+ref+"'");
                attributes(m,{"name","Z"});
                const double z=number(m,"Z");
                require(z>=1 && z<=118 && std::trunc(z)==z,"material Z must identify one element (1..118)");
                require((prefix+ref).find("0x")==std::string::npos,"material or instance name contains GDML pointer marker 0x");
                unsigned density=0,atom=0;
                for(auto* x:children(m)) {
                    attributes(x,{"unit","value"});
                    require(children(x).empty(),"material scalar cannot contain nested declarations");
                    if(tag(x)=="D") {
                        ++density;
                        require(number(x,"value",unit(x,"unit","g/cm3","Volumic Mass"))>=CLHEP::universe_mean_density,
                                "material density D is lower than the native representable material density");
                    } else if(tag(x)=="atom") {
                        ++atom;
                        require(number(x,"value",unit(x,"unit","g/mole","Molar mass"))>0,"material atom molar mass must be positive");
                    }
                    else require(false,"unsupported material member '"+tag(x)+"'");
                }
                require(density==1 && atom==1 && !attr(m,"Z").empty(),"requires single-element material with D, Z and atom");
                usedMaterials.insert(ref);
            } else if(t=="auxiliary") {
                attributes(e,{"auxtype","auxvalue"});
                require(attr(e,"auxtype")=="SensDet" && children(e).empty(),"unsupported auxiliary '"+attr(e,"auxtype")+"'");
            } else if(t=="physvol") {
                attributes(e,{"name","copynumber"});
                auto n=attr(e,"name"),copy=attr(e,"copynumber");
                require(!n.empty() && n.find_first_of("/#[]")==std::string::npos,"ambiguous physical name '"+n+"'");
                int copyNumber=0;
                if(!copy.empty()) {
                    const auto parsed=std::from_chars(copy.data(),copy.data()+copy.size(),copyNumber);
                    require(parsed.ec==std::errc{} && parsed.ptr==copy.data()+copy.size(),"copynumber must be a decimal integer");
                }
                require(placements.emplace(n,copyNumber).second,"ambiguous placement '"+n+"'");
                std::set<std::string> fields;
                for(auto* x:children(e)) {
                    auto key=tag(x); require(fields.insert(key).second,"duplicate "+key+" in "+n);
                    if(key=="volumeref") {attributes(x,{"ref"});visit(attr(x,"ref"));}
                    else {
                        require(key=="position" || key=="rotation","unsupported placement member '"+key+"'");
                        validatePose(x);
                    }
                }
                require(fields.count("volumeref"),"missing volumeref in "+n);
            } else require(false,"unsupported volume member '"+t+"'");
        }
        require(solidCount==1 && materialCount==1,"volume '"+name+"' needs one materialref and solidref");
        visiting.erase(name); selected.insert(name); order.push_back(name);
    }
    void dispatch(const Element* e) {
        if(handled)return;
        handled=true;
        try {process(e->getOwnerDocument()->getDocumentElement());}
        catch(const GdmlIO::ComponentScaleError& ex){scaleError=true;error=ex.what();}
        catch(const std::exception& ex){error=ex.what();}
    }
    struct PlacedBox {
        std::string source, path, placement, material;
        int parent=-1, copy=0, depth=1;
        bool sensitive=false;
        gdml_affine::Box box;
        G4RotationMatrix rotation;
        G4ThreeVector translation;
    };
    std::vector<PlacedBox> boxes;
    std::size_t totalPathBytes=0;

    void planBox(const std::string& source,const std::string& path,const std::string& pvName,int copy,int parent,
                 const G4RotationMatrix& sourceAxes,const G4ThreeVector& center,const G4ThreeVector& step) {
        require(boxes.size()<100000,"scaled subtree exceeds 100000 physical occurrences");
        constexpr std::size_t pathBudget=64*1024*1024;
        require(path.size()<=pathBudget-totalPathBytes,"expanded occurrence paths exceed 64 MiB");
        totalPathBytes+=path.size();
        PlacedBox p;
        p.depth=parent<0?1:boxes[parent].depth+1;
        require(p.depth<=256,"scaled subtree exceeds 256 occurrence levels");
        p.source=source;p.path=path;p.placement=pvName;p.copy=copy;p.parent=parent;
        auto members=children(volumes.at(source));
        for(auto* e:members) {
            if(tag(e)=="materialref")p.material=attr(e,"ref");
            if(tag(e)=="auxiliary")p.sensitive=true;
            if(tag(e)=="solidref") {
                auto* solid=solids.at(attr(e,"ref"));
                const double halfUnit=0.5*unit(solid,"lunit","mm","Length");
                const G4ThreeVector half(number(solid,"x",halfUnit),number(solid,"y",halfUnit),number(solid,"z",halfUnit));
                p.box=gdml_affine::decompose(scales,sourceAxes,half,center,
                    G4GeometryTolerance::GetInstance()->GetSurfaceTolerance(),path);
            }
        }
        if(parent>=0) {
            const auto inverse=boxes[parent].box.axes.inverse();
            p.rotation=inverse*p.box.axes;
            p.translation=inverse*step;
        }
        const int index=static_cast<int>(boxes.size());
        boxes.push_back(p);
        for(auto* e:members)if(tag(e)=="physvol") {
            std::string child;
            G4ThreeVector angles,offset;
            for(auto* entry:children(e)) {
                if(tag(entry)=="volumeref")child=attr(entry,"ref");
                if(tag(entry)=="rotation")VectorRead(entry,angles);
                if(tag(entry)=="position")VectorRead(entry,offset);
            }
            const auto name=attr(e,"name"),id=attr(e,"copynumber");
            const int childCopy=id.empty()?0:std::stoi(id);
            const auto delta=gdml_affine::scale(scales,sourceAxes*offset);
            planBox(child,path+(path=="/"?"":"/")+name+"#"+std::to_string(childCopy),name,childCopy,index,
                sourceAxes*GetRotationMatrix(angles).inverse(),center+delta,delta);
        }
    }
    std::string occurrenceName(std::size_t i) const {
        return prefix+"occ"+std::to_string(i)+"_"+boxes[i].source;
    }
    void buildBoxes() {
        std::vector<G4LogicalVolume*> logicals;
        for(std::size_t i=0;i<boxes.size();++i) {
            const auto& p=boxes[i];const auto& box=p.box;
            const auto name=occurrenceName(i);
            G4VSolid* solid;
            if(box.rectangular)solid=new G4Box(name,box.half.x(),box.half.y(),box.half.z());
            else solid=new G4Para(name,box.half.x(),box.half.y(),box.half.z(),box.alpha,box.theta,box.phi);
            auto* material=G4Material::GetMaterial(prefix+p.material,false);
            require(material!=nullptr,"missing accepted component material "+p.material);
            auto* lv=new G4LogicalVolume(solid,material,name);
            logicals.push_back(lv);
            if(p.parent<0)result.root=lv;
            else new G4PVPlacement(G4Transform3D(p.rotation,p.translation),lv,p.placement,
                                   logicals.at(p.parent),false,p.copy,overlaps);
            result.occurrences.push_back({p.source,p.path,lv});
            if(p.sensitive)result.sensitive.push_back(lv);
        }
    }
    void process(const Element* document) {
        std::set<std::string> sections;
        for(auto* e:children(document)) {
            auto t=tag(e);require(sections.insert(t).second,"duplicate "+t);
            if(t=="structure") {
                for(auto* v:children(e))require(tag(v)=="volume","unsupported structure declaration '"+tag(v)+"'");
                index(e,volumes);
            } else if(t=="solids")index(e,solids);
            else if(t=="materials")index(e,materials);
            else if(t=="define")require(children(e).empty(),"nonempty define section outside the inline-transform component profile");
            else require(t=="setup","unsupported section '"+t+"'");
        }
        for(const auto& v:volumes)result.choices.push_back(v.first);
        if(!volumes.count(selector)) {
            std::string candidates;for(const auto& v:result.choices)candidates+=(candidates.empty()?"":", ")+v;
            require(false,"logical root '"+selector+"' not found; available: "+candidates);
        }
        visit(selector);
        confirmInput();
        const bool scaled=scales!=std::array<double,3>{1,1,1};
        if(scaled)planBox(selector,"/",{},0,-1,G4RotationMatrix{},G4ThreeVector{},G4ThreeVector{});
        if(!construct)return;
        for(std::size_t i=0;i<boxes.size();++i) {
            const auto name=occurrenceName(i);
            require(!G4SolidStore::GetInstance()->GetSolid(name,false) &&
                    !G4LogicalVolumeStore::GetInstance()->GetVolume(name,false),"existing object conflicts with "+name);
        }
        for(const auto& n:usedSolids)require(!G4SolidStore::GetInstance()->GetSolid(prefix+n,false),"existing solid conflicts with "+prefix+n);
        for(const auto& n:usedMaterials)require(!G4Material::GetMaterial(prefix+n,false),"existing material conflicts with "+prefix+n);
        for(const auto& n:order)require(!G4LogicalVolumeStore::GetInstance()->GetVolume(prefix+n,false),"existing logical conflicts with "+prefix+n);
        // Clones belong to the same parser-owned DOM. Only private clones receive instance names.
        auto clone=[&](Element* e) {
            auto* copy=static_cast<Element*>(e->cloneNode(true));
            set(copy,"name",prefix+attr(e,"name"));return copy;
        };
        for(const auto& name:usedMaterials)MaterialRead(clone(materials.at(name)));
        if(scaled) {buildBoxes();return;}
        for(const auto& name:usedSolids)BoxRead(clone(solids.at(name)));
        for(const auto& name:order) {
            auto* v=clone(volumes.at(name));
            for(auto* e:children(v)) {
                auto t=tag(e);
                if(t=="materialref" || t=="solidref")set(e,"ref",prefix+attr(e,"ref"));
                if(t=="physvol") {
                    for(auto* x:children(e))if(tag(x)=="volumeref")set(x,"ref",prefix+attr(x,"ref"));
                }
            }
            G4GDMLReadStructure::VolumeRead(v);
            auto* lv=pMotherLogical;
            require(lv && lv->GetName()==prefix+name,"native logical identity mismatch for "+name);
            result.logicals.emplace(name,lv);
            if(!GetVolumeAuxiliaryInformation(lv).empty())result.sensitive.push_back(lv);
        }
        result.root=result.logicals.at(selector);
    }
};
}
#endif

GdmlIO::Component GdmlIO::ReadComponent(const std::string& path,const std::string& selector,
    const std::string& instance,bool construct,bool checkOverlaps,const std::string& acceptedSha,const std::array<double,3>& scales) {
#ifdef G4USIM_HAVE_GDML
    for(double factor:scales)require(std::isfinite(factor) && factor>0,"scales must be finite and positive");
    require(instance.find_first_of("/#[]")==std::string::npos,"ambiguous instance name '"+instance+"'");
    require(std::filesystem::is_regular_file(std::filesystem::u8path(path)),"file does not exist: "+path);
    std::unique_lock<std::recursive_mutex> lock(GdmlInputCapture::NativeMutex());
    ComponentReader reader(selector,instance,construct);
    reader.scales=scales;
    reader.overlaps=checkOverlaps;
    G4GDMLParser parser(&reader);
    parser.SetOverlapCheck(checkOverlaps);
    GdmlInputCapture capture;
    reader.confirmInput=[&] {
        const auto captured=capture.AcceptedInputs();
        require(captured.size()==1 && capture.UntrackedInputs().empty(),"requires a single captured local GDML input");
        require(acceptedSha.empty() || acceptedSha==captured.front().sha256,"file changed after configuration: "+path);
    };
    parser.ReadModule(path,false);
    auto inputs=capture.AcceptedInputs();
    if(reader.scaleError)throw ComponentScaleError(reader.error+" ("+path+")");
    if(!reader.error.empty())throw std::runtime_error(reader.error+" ("+path+")");
    require(!reader.result.choices.empty(),"no logical root candidates in "+path);
    require(inputs.size()==1 && capture.UntrackedInputs().empty(),"component requires one completely captured local GDML file");
    require(acceptedSha.empty() || inputs.front().sha256==acceptedSha,"file changed after configuration: "+path);
    reader.result.inputs=std::move(inputs);
    return std::move(reader.result);
#else
    throw std::runtime_error("GDML component unavailable: rebuild Geant4 with GDML and XercesC");
#endif
}
