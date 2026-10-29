#include "Geometry/GdmlIO.hh"

#include <filesystem>
#include <memory>
#include <set>
#include <stdexcept>
#include <map>

#ifdef G4USIM_HAVE_GDML
#include "G4GDMLParser.hh"
#include "G4LogicalVolume.hh"
#include "G4LogicalVolumeStore.hh"
#include "G4VPhysicalVolume.hh"
#endif

namespace GdmlIO {

#ifdef G4USIM_HAVE_GDML

bool Available()
{
    return true;
}

ImportResult Read(const std::string& path, bool validate, bool checkOverlaps)
{
    if (!std::filesystem::is_regular_file(std::filesystem::u8path(path))) {
        throw std::runtime_error("GDML file does not exist: '" + path + "'");
    }
    std::unique_lock<std::recursive_mutex> nativeLock(GdmlInputCapture::NativeMutex());
    static std::unique_ptr<G4GDMLParser> parser;
    parser = std::make_unique<G4GDMLParser>();
    parser->SetOverlapCheck(checkOverlaps);
    ImportResult result;
    {
        GdmlInputCapture capture;
        parser->Read(path, validate);
        result.acceptedInputs = capture.AcceptedInputs();
        result.untrackedInputs = capture.UntrackedInputs();
    }
    result.world = parser->GetWorldVolume();
    if (!result.world) throw std::runtime_error("GDML file '" + path + "' does not define a world volume");
    std::vector<G4LogicalVolume*> pending{result.world->GetLogicalVolume()};
    std::set<G4LogicalVolume*> visited;
    while (!pending.empty()) {
        G4LogicalVolume* logical = pending.back();
        pending.pop_back();
        if (!logical || !visited.insert(logical).second) continue;
        std::map<std::pair<std::string, int>, G4VPhysicalVolume*> ordinaryPlacements;
        for (int i = 0; i < logical->GetNoDaughters(); ++i) {
            auto* placement = logical->GetDaughter(i);
            const std::string name = placement->GetName();
            if (name.find('/') != std::string::npos) {
                throw std::runtime_error("GDML ambiguous touchable path: placement '" + name + "' in mother logical volume '" +
                                         std::string(logical->GetName()) + "' contains the path separator '/'; rename the placement before importing");
            }
            if (!placement->IsReplicated() && !placement->IsParameterised()) {
                const auto key = std::make_pair(name, placement->GetCopyNo());
                const auto inserted = ordinaryPlacements.emplace(key, placement);
                if (!inserted.second && inserted.first->second != placement) {
                    throw std::runtime_error("GDML ambiguous touchable path: different ordinary placements in mother logical volume '" +
                                             std::string(logical->GetName()) + "' share name '" + name + "' and copy number " +
                                             std::to_string(placement->GetCopyNo()) + "; use unique names or copy numbers before importing");
                }
            }
            pending.push_back(placement->GetLogicalVolume());
        }
        for (const G4GDMLAuxStructType& aux : parser->GetVolumeAuxiliaryInformation(logical)) {
            if (aux.type == "SensDet") {
                result.auxSensitive.push_back(logical);
                break;
            }
        }
    }
    return result;
}

void Write(const std::string& path, G4VPhysicalVolume* world)
{
    if (!world) throw std::runtime_error("GDML export: no world volume; run /run/initialize first");
    const std::filesystem::path file = std::filesystem::u8path(path);
    if (std::filesystem::exists(file)) {
        throw std::runtime_error("GDML export refuses to overwrite existing file '" + path + "'");
    }
    if (file.has_parent_path()) std::filesystem::create_directories(file.parent_path());
    std::unique_lock<std::recursive_mutex> nativeLock(GdmlInputCapture::NativeMutex());
    G4GDMLParser parser;
    parser.Write(path, world, false);
    if (!std::filesystem::is_regular_file(file)) throw std::runtime_error("GDML export failed to write '" + path + "'");
}

#else

namespace {
[[noreturn]] void Unavailable()
{
    throw std::runtime_error(
        "Geometry capability 'GDML' is not available: this build uses a Geant4 installation without GDML "
        "(Geant4_gdml_FOUND=OFF, needs XercesC). Rebuild Geant4 with GEANT4_USE_GDML=ON, or use a supported "
        "geometry template and regular volume definitions instead.");
}
}  // namespace

bool Available()
{
    return false;
}

ImportResult Read(const std::string&, bool, bool)
{
    Unavailable();
}

void Write(const std::string&, G4VPhysicalVolume*)
{
    Unavailable();
}

#endif

}  // namespace GdmlIO
