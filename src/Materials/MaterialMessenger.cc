#include "Materials/MaterialMessenger.hh"

#include "Materials/MaterialCommandParser.hh"
#include "Materials/MaterialManager.hh"

#include "G4Exception.hh"
#include "G4UIcmdWithABool.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIcmdWithoutParameter.hh"
#include "G4UIdirectory.hh"
#include "G4ios.hh"

#include <cstdlib>
#include <stdexcept>

namespace {

int ParseIntValue(const std::string& text, const std::string& key, const std::string& original)
{
    char* end = nullptr;
    const long value = std::strtol(text.c_str(), &end, 10);
    if (end == text.c_str() || *end != '\0') {
        throw std::runtime_error("Invalid integer for key '" + key + "' in command: " + original);
    }
    return static_cast<int>(value);
}

void Warn(const std::string& message)
{
    G4Exception("MaterialMessenger", "AIHL_Material_001", JustWarning, message.c_str());
}

}  // namespace

MaterialMessenger::MaterialMessenger(MaterialManager* manager)
    : manager_(manager)
{
    materialDir_ = std::make_unique<G4UIdirectory>("/AIHL/material/");
    materialDir_->SetGuidance("Material management commands for AIHL.");

    loadCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/material/load", this);
    printCmd_ = std::make_unique<G4UIcmdWithoutParameter>("/AIHL/material/print", this);
    listCmd_ = std::make_unique<G4UIcmdWithoutParameter>("/AIHL/material/list", this);
    addNistCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/material/addNist", this);
    addIsotopeCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/material/addIsotope", this);
    addElementCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/material/addElement", this);
    addElementFromIsotopesCmd_ =
        std::make_unique<G4UIcmdWithAString>("/AIHL/material/addElementFromIsotopes", this);
    addMaterialCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/material/addMaterial", this);
    buildAllCmd_ = std::make_unique<G4UIcmdWithoutParameter>("/AIHL/material/buildAll", this);
    setLockedCmd_ = std::make_unique<G4UIcmdWithABool>("/AIHL/material/setLocked", this);
    clearCmd_ = std::make_unique<G4UIcmdWithoutParameter>("/AIHL/material/clear", this);
}

MaterialMessenger::~MaterialMessenger() = default;

void MaterialMessenger::SetNewValue(G4UIcommand* command, G4String newValue)
{
    if (!manager_) {
        Warn("MaterialManager pointer is null.");
        return;
    }
    const std::string value = newValue;

    if (command == loadCmd_.get()) {
        ExecuteWithWarning(value, [&]() {
            manager_->LoadMaterials(value);
            G4cout << "[MaterialMessenger] Loaded " << manager_->GetMaterialNames().size()
                   << " materials from " << value << G4endl;
        });
    } else if (command == printCmd_.get()) {
        ExecuteWithWarning("/AIHL/material/print", [&]() { manager_->PrintAll(); });
    } else if (command == listCmd_.get()) {
        ExecuteWithWarning("/AIHL/material/list", [&]() { manager_->PrintAll(); });
    } else if (command == addNistCmd_.get()) {
        ExecuteWithWarning(value, [&]() {
            const auto args = MaterialCommandParser::ParseKeyValueLine(value);
            const std::string nist = MaterialCommandParser::Require(args, "nist", value);
            const auto nameIt = args.find("name");
            const std::string alias = (nameIt == args.end() || nameIt->second.empty()) ? nist : nameIt->second;
            manager_->RegisterMaterial(alias, manager_->BuildNistMaterial(nist));
        });
    } else if (command == addIsotopeCmd_.get()) {
        ExecuteWithWarning(value, [&]() {
            const auto args = MaterialCommandParser::ParseKeyValueLine(value);
            IsotopeDefinition def;
            def.name = MaterialCommandParser::Require(args, "name", value);
            def.symbol = MaterialCommandParser::Require(args, "symbol", value);
            def.z = ParseIntValue(MaterialCommandParser::Require(args, "z", value), "z", value);
            def.n = ParseIntValue(MaterialCommandParser::Require(args, "n", value), "n", value);
            def.aText = MaterialCommandParser::Require(args, "a", value);
            def.a = MaterialCommandParser::ParseMolarMass(def.aText);
            manager_->AddIsotopeDefinition(def);
            manager_->BuildIsotope(def.name);
        });
    } else if (command == addElementCmd_.get()) {
        ExecuteWithWarning(value, [&]() {
            const auto args = MaterialCommandParser::ParseKeyValueLine(value);
            ElementDefinition def;
            def.name = MaterialCommandParser::Require(args, "name", value);
            def.symbol = MaterialCommandParser::Require(args, "symbol", value);
            def.z = ParseIntValue(MaterialCommandParser::Require(args, "z", value), "z", value);
            def.aText = MaterialCommandParser::Require(args, "a", value);
            def.a = MaterialCommandParser::ParseMolarMass(def.aText);
            manager_->AddElementDefinition(def);
            manager_->BuildElement(def.name);
        });
    } else if (command == addElementFromIsotopesCmd_.get()) {
        ExecuteWithWarning(value, [&]() {
            const auto args = MaterialCommandParser::ParseKeyValueLine(value);
            ElementDefinition def;
            def.name = MaterialCommandParser::Require(args, "name", value);
            def.symbol = MaterialCommandParser::Require(args, "symbol", value);
            def.useIsotopes = true;
            def.isotopes = MaterialCommandParser::ParseIsotopeComponents(
                MaterialCommandParser::Require(args, "isotopes", value)
            );
            manager_->AddElementDefinition(def);
            manager_->BuildElement(def.name);
        });
    } else if (command == addMaterialCmd_.get()) {
        ExecuteWithWarning(value, [&]() {
            const auto args = MaterialCommandParser::ParseKeyValueLine(value);
            MaterialDefinition def;
            def.name = MaterialCommandParser::Require(args, "name", value);
            def.densityText = MaterialCommandParser::Require(args, "density", value);
            def.density = MaterialCommandParser::ParseDensity(def.densityText);
            const std::string modeText = args.count("mode") ? args.at("mode") : "mass_fraction";
            def.components = MaterialCommandParser::ParseMaterialComponents(
                MaterialCommandParser::Require(args, "components", value),
                MaterialCommandParser::ParseMode(modeText)
            );
            manager_->AddMaterialDefinition(def);
            manager_->BuildMaterial(def.name);
        });
    } else if (command == buildAllCmd_.get()) {
        ExecuteWithWarning("/AIHL/material/buildAll", [&]() { manager_->BuildAll(); });
    } else if (command == setLockedCmd_.get()) {
        ExecuteWithWarning(value, [&]() { manager_->SetLocked(setLockedCmd_->GetNewBoolValue(newValue)); });
    } else if (command == clearCmd_.get()) {
        ExecuteWithWarning("/AIHL/material/clear", [&]() { manager_->Clear(); });
    }
}

void MaterialMessenger::ExecuteWithWarning(
    const std::string& commandText,
    const std::function<void()>& action
)
{
    try {
        action();
    } catch (const std::exception& ex) {
        Warn("Material command failed: '" + commandText + "': " + ex.what());
    }
}
