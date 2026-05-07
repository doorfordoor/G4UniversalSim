#include "Geometry/GeometryMessenger.hh"

#include "Geometry/GeometryManager.hh"
#include "Geometry/GeometryUtils.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4Exception.hh"
#include "G4RunManager.hh"
#include "G4UIcmdWithABool.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIcmdWithoutParameter.hh"
#include "G4UIdirectory.hh"
#include "G4ios.hh"

#include <cctype>
#include <exception>
#include <map>
#include <stdexcept>

namespace {

std::map<std::string, std::string> ParseKeyValueLine(const std::string& line)
{
    std::map<std::string, std::string> result;
    std::size_t i = 0;
    while (i < line.size()) {
        while (i < line.size() && std::isspace(static_cast<unsigned char>(line[i]))) ++i;
        if (i >= line.size()) break;

        const std::size_t keyStart = i;
        while (i < line.size() && line[i] != '=' && !std::isspace(static_cast<unsigned char>(line[i]))) ++i;
        std::string key = line.substr(keyStart, i - keyStart);
        key = StringUtils::ToLower(StringUtils::Trim(key));
        while (i < line.size() && std::isspace(static_cast<unsigned char>(line[i]))) ++i;
        if (i >= line.size() || line[i] != '=') {
            throw std::runtime_error("Expected key=value token near '" + line.substr(keyStart) + "'");
        }
        ++i;
        while (i < line.size() && std::isspace(static_cast<unsigned char>(line[i]))) ++i;

        std::string value;
        if (i < line.size() && line[i] == '"') {
            ++i;
            bool closed = false;
            while (i < line.size()) {
                if (line[i] == '"') {
                    closed = true;
                    ++i;
                    break;
                }
                value.push_back(line[i++]);
            }
            if (!closed) throw std::runtime_error("Unclosed quote in command line: '" + line + "'");
        } else {
            const std::size_t valueStart = i;
            while (i < line.size() && !std::isspace(static_cast<unsigned char>(line[i]))) ++i;
            value = line.substr(valueStart, i - valueStart);
        }

        if (key.empty()) throw std::runtime_error("Empty key in command line: '" + line + "'");
        result[key] = StringUtils::Trim(value);
    }
    return result;
}

std::string RequireValue(const std::map<std::string, std::string>& args, const std::string& key, const std::string& command)
{
    const auto it = args.find(StringUtils::ToLower(key));
    if (it == args.end() || StringUtils::Trim(it->second).empty()) {
        throw std::runtime_error(command + " missing required key '" + key + "'");
    }
    return it->second;
}

std::string OptionalValue(
    const std::map<std::string, std::string>& args,
    const std::string& key,
    const std::string& defaultValue
)
{
    const auto it = args.find(StringUtils::ToLower(key));
    return it == args.end() ? defaultValue : it->second;
}

bool OptionalBool(const std::map<std::string, std::string>& args, const std::string& key, bool defaultValue)
{
    const auto it = args.find(StringUtils::ToLower(key));
    return it == args.end() ? defaultValue : StringUtils::ToBool(it->second);
}

double OptionalDouble(const std::map<std::string, std::string>& args, const std::string& key, double defaultValue)
{
    const auto it = args.find(StringUtils::ToLower(key));
    if (it == args.end()) return defaultValue;
    return UnitParser::ParseDouble(it->second);
}

void ApplyVisualOptions(VolumeNode& node, const std::map<std::string, std::string>& args)
{
    node.visual.color = OptionalValue(args, "color", node.visual.color);
    node.visual.alpha = OptionalDouble(args, "alpha", node.visual.alpha);
    node.visual.visible = OptionalBool(args, "visible", node.visual.visible);
    node.visual.wireframe = OptionalBool(args, "wireframe", node.visual.wireframe);
}

VolumeNode MakeCommonNode(
    const std::map<std::string, std::string>& args,
    const std::string& command,
    VolumeShape shape,
    const std::string& shapeName
)
{
    VolumeNode node(RequireValue(args, "name", command));
    node.parentName = RequireValue(args, "parent", command);
    node.materialName = RequireValue(args, "material", command);
    node.shape = shape;
    node.shapeName = shapeName;
    node.position = GeometryUtils::ParseVec3(OptionalValue(args, "position", "0 mm,0 mm,0 mm"));
    node.rotation = GeometryUtils::ParseRotation3(OptionalValue(args, "rotation", "0 deg,0 deg,0 deg"));
    node.sensitive = OptionalBool(args, "sensitive", false);
    node.bias = OptionalBool(args, "bias", false);
    node.regionName = OptionalValue(args, "region", "");
    ApplyVisualOptions(node, args);
    return node;
}

}  // namespace

GeometryMessenger::GeometryMessenger(GeometryManager* manager)
    : manager_(manager)
{
    directory_ = new G4UIdirectory("/AIHL/geometry/");
    directory_->SetGuidance("Geometry configuration commands for G4UniversalSim.");

    setTemplateCmd_ = new G4UIcmdWithAString("/AIHL/geometry/setTemplate", this);
    setTemplateCmd_->SetGuidance("Set geometry template name.");
    setTemplateCmd_->SetParameterName("templateName", false);

    loadConfigCmd_ = new G4UIcmdWithAString("/AIHL/geometry/loadConfig", this);
    loadConfigCmd_->SetGuidance("Load geometry template/config ini file into GeometryManager.");
    loadConfigCmd_->SetParameterName("filename", false);

    checkOverlapsCmd_ = new G4UIcmdWithABool("/AIHL/geometry/checkOverlaps", this);
    checkOverlapsCmd_->SetGuidance("Enable or disable Geant4 overlap checks in G4PVPlacement.");
    checkOverlapsCmd_->SetParameterName("enable", false);

    setDefaultWorldMaterialCmd_ = new G4UIcmdWithAString("/AIHL/geometry/setDefaultWorldMaterial", this);
    setDefaultWorldMaterialCmd_->SetGuidance("Set fallback material used when the world node has no material.");
    setDefaultWorldMaterialCmd_->SetParameterName("materialName", false);

    addBoxCmd_ = new G4UIcmdWithAString("/AIHL/geometry/addBox", this);
    addBoxCmd_->SetGuidance("Add a user box VolumeNode to the current geometry tree.");
    addBoxCmd_->SetParameterName("keyValueLine", false);

    addTubsCmd_ = new G4UIcmdWithAString("/AIHL/geometry/addTubs", this);
    addTubsCmd_->SetGuidance("Add a user tubs/cylinder VolumeNode to the current geometry tree.");
    addTubsCmd_->SetParameterName("keyValueLine", false);

    addVolumeCmd_ = new G4UIcmdWithAString("/AIHL/geometry/addVolume", this);
    addVolumeCmd_->SetGuidance("Add a user VolumeNode. First version supports shape=box and shape=tubs.");
    addVolumeCmd_->SetParameterName("keyValueLine", false);

    removeUserVolumeCmd_ = new G4UIcmdWithAString("/AIHL/geometry/removeUserVolume", this);
    removeUserVolumeCmd_->SetGuidance("Remove a user-added volume by name. Removes the whole subtree.");
    removeUserVolumeCmd_->SetParameterName("name", false);

    printCmd_ = new G4UIcmdWithoutParameter("/AIHL/geometry/print", this);
    printCmd_->SetGuidance("Print GeometryManager summary.");

    printTreeCmd_ = new G4UIcmdWithoutParameter("/AIHL/geometry/printTree", this);
    printTreeCmd_->SetGuidance("Print current VolumeNode tree.");

    clearCmd_ = new G4UIcmdWithoutParameter("/AIHL/geometry/clear", this);
    clearCmd_->SetGuidance("Clear current GeometryManager state.");

    clearUserVolumesCmd_ = new G4UIcmdWithoutParameter("/AIHL/geometry/clearUserVolumes", this);
    clearUserVolumesCmd_->SetGuidance("Clear all user-added volumes.");

    listUserVolumesCmd_ = new G4UIcmdWithoutParameter("/AIHL/geometry/listUserVolumes", this);
    listUserVolumesCmd_->SetGuidance("List user-added volumes.");

    preserveUserVolumesOnLoadCmd_ = new G4UIcmdWithABool("/AIHL/geometry/preserveUserVolumesOnLoad", this);
    preserveUserVolumesOnLoadCmd_->SetGuidance("Preserve user-added volumes when loading a new geometry config.");
    preserveUserVolumesOnLoadCmd_->SetParameterName("preserve", false);

    markModifiedCmd_ = new G4UIcmdWithoutParameter("/AIHL/geometry/markModified", this);
    markModifiedCmd_->SetGuidance("Call G4RunManager::GeometryHasBeenModified(). Does not rebuild geometry or start a run.");
}

GeometryMessenger::~GeometryMessenger()
{
    delete markModifiedCmd_;
    delete preserveUserVolumesOnLoadCmd_;
    delete listUserVolumesCmd_;
    delete clearUserVolumesCmd_;
    delete clearCmd_;
    delete printTreeCmd_;
    delete printCmd_;
    delete removeUserVolumeCmd_;
    delete addVolumeCmd_;
    delete addTubsCmd_;
    delete addBoxCmd_;
    delete setDefaultWorldMaterialCmd_;
    delete checkOverlapsCmd_;
    delete loadConfigCmd_;
    delete setTemplateCmd_;
    delete directory_;
}

void GeometryMessenger::SetNewValue(G4UIcommand* command, G4String newValue)
{
    try {
        if (command == setTemplateCmd_) {
            EnsureManager("/AIHL/geometry/setTemplate");
            manager_->SetTemplate(newValue);
            PrintChangedMessage();
            return;
        }
        if (command == loadConfigCmd_) {
            EnsureManager("/AIHL/geometry/loadConfig");
            manager_->LoadGeometryConfig(newValue);
            PrintChangedMessage();
            return;
        }
        if (command == checkOverlapsCmd_) {
            EnsureManager("/AIHL/geometry/checkOverlaps");
            manager_->SetCheckOverlaps(checkOverlapsCmd_->GetNewBoolValue(newValue));
            PrintChangedMessage();
            return;
        }
        if (command == setDefaultWorldMaterialCmd_) {
            EnsureManager("/AIHL/geometry/setDefaultWorldMaterial");
            manager_->SetDefaultWorldMaterial(newValue);
            PrintChangedMessage();
            return;
        }
        if (command == addBoxCmd_) {
            EnsureManager("/AIHL/geometry/addBox");
            const auto args = ParseKeyValueLine(newValue);
            VolumeNode node = MakeCommonNode(args, "/AIHL/geometry/addBox", VolumeShape::Box, "box");
            node.size = GeometryUtils::ParseVec3(RequireValue(args, "size", "/AIHL/geometry/addBox"));
            manager_->AddVolume(node);
            PrintTreeModifiedMessage();
            return;
        }
        if (command == addTubsCmd_) {
            EnsureManager("/AIHL/geometry/addTubs");
            const auto args = ParseKeyValueLine(newValue);
            VolumeNode node = MakeCommonNode(args, "/AIHL/geometry/addTubs", VolumeShape::Tubs, "tubs");
            node.parameters = {
                UnitParser::ParseLength(OptionalValue(args, "rmin", "0 mm")),
                UnitParser::ParseLength(RequireValue(args, "rmax", "/AIHL/geometry/addTubs")),
                UnitParser::ParseLength(RequireValue(args, "halfz", "/AIHL/geometry/addTubs")),
                UnitParser::ParseAngle(OptionalValue(args, "startphi", "0 deg")),
                UnitParser::ParseAngle(OptionalValue(args, "deltaphi", "360 deg"))
            };
            manager_->AddVolume(node);
            PrintTreeModifiedMessage();
            return;
        }
        if (command == addVolumeCmd_) {
            EnsureManager("/AIHL/geometry/addVolume");
            const auto args = ParseKeyValueLine(newValue);
            const std::string shapeText = RequireValue(args, "shape", "/AIHL/geometry/addVolume");
            const VolumeShape shape = GeometryUtils::ParseShape(shapeText);
            if (shape != VolumeShape::Box && shape != VolumeShape::Tubs) {
                throw std::runtime_error("/AIHL/geometry/addVolume currently supports only box and tubs; got shape='" + shapeText + "'");
            }
            VolumeNode node = MakeCommonNode(args, "/AIHL/geometry/addVolume", shape, shapeText);
            if (shape == VolumeShape::Box) {
                node.size = GeometryUtils::ParseVec3(RequireValue(args, "size", "/AIHL/geometry/addVolume"));
            } else {
                node.parameters = GeometryUtils::ParseParameterList(RequireValue(args, "parameters", "/AIHL/geometry/addVolume"));
                if (node.parameters.size() < 5) {
                    throw std::runtime_error("/AIHL/geometry/addVolume shape=tubs requires parameters='rMin,rMax,halfZ,startPhi,deltaPhi'");
                }
            }
            manager_->AddVolume(node);
            PrintTreeModifiedMessage();
            return;
        }
        if (command == removeUserVolumeCmd_) {
            EnsureManager("/AIHL/geometry/removeUserVolume");
            if (!manager_->RemoveUserVolume(newValue)) {
                throw std::runtime_error("/AIHL/geometry/removeUserVolume target is not a user-added volume: '" + std::string(newValue) + "'");
            }
            PrintTreeModifiedMessage();
            return;
        }
        if (command == printCmd_) {
            EnsureManager("/AIHL/geometry/print");
            manager_->PrintSummary();
            return;
        }
        if (command == printTreeCmd_) {
            EnsureManager("/AIHL/geometry/printTree");
            manager_->PrintTree();
            return;
        }
        if (command == clearCmd_) {
            EnsureManager("/AIHL/geometry/clear");
            manager_->Clear();
            PrintChangedMessage();
            return;
        }
        if (command == clearUserVolumesCmd_) {
            EnsureManager("/AIHL/geometry/clearUserVolumes");
            manager_->ClearUserAddedVolumes();
            PrintTreeModifiedMessage();
            return;
        }
        if (command == listUserVolumesCmd_) {
            EnsureManager("/AIHL/geometry/listUserVolumes");
            manager_->PrintUserAddedVolumes();
            return;
        }
        if (command == preserveUserVolumesOnLoadCmd_) {
            EnsureManager("/AIHL/geometry/preserveUserVolumesOnLoad");
            manager_->SetPreserveUserVolumesOnLoad(preserveUserVolumesOnLoadCmd_->GetNewBoolValue(newValue));
            PrintChangedMessage();
            return;
        }
        if (command == markModifiedCmd_) {
            G4RunManager* runManager = G4RunManager::GetRunManager();
            if (!runManager) {
                throw std::runtime_error("/AIHL/geometry/markModified failed: G4RunManager does not exist");
            }
            runManager->GeometryHasBeenModified();
            G4cout << "[GeometryMessenger] Geometry marked modified. Use /run/reinitializeGeometry for full geometry replacement." << G4endl;
            return;
        }
    } catch (const std::exception& e) {
        ReportCommandError("GeometryMessenger::SetNewValue", newValue, e);
        return;
    }

    G4Exception(
        "GeometryMessenger::SetNewValue",
        "AIHLGeometryCmd000",
        JustWarning,
        "Unknown /AIHL/geometry command object."
    );
}

void GeometryMessenger::EnsureManager(const char* commandName) const
{
    if (!manager_) {
        throw std::runtime_error(std::string(commandName) + " failed: GeometryManager pointer is null");
    }
}

void GeometryMessenger::PrintChangedMessage() const
{
    G4cout << "[GeometryMessenger] Geometry state changed. Use /run/reinitializeGeometry before the next run if the run manager was already initialized." << G4endl;
}

void GeometryMessenger::PrintTreeModifiedMessage() const
{
    G4cout << "[GeometryMessenger] Geometry tree was modified. Use /run/reinitializeGeometry before the next run if the run manager was already initialized." << G4endl;
}

void GeometryMessenger::ReportCommandError(const char* commandName, const G4String& value, const std::exception& error) const
{
    const std::string message = std::string(commandName) + " failed for input '" + value + "': " + error.what();
    G4Exception("GeometryMessenger", "AIHLGeometryCmd001", JustWarning, message.c_str());
}
