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
#include <functional>
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
    G4Exception(
        "MaterialMessenger",
        "AIHL_Material_001",
        JustWarning,
        message.c_str()
    );
}

}  // namespace

MaterialMessenger::MaterialMessenger(MaterialManager* manager)
    : manager_(manager)
{
    materialDir_ = std::make_unique<G4UIdirectory>("/AIHL/material/");
    materialDir_->SetGuidance("Material management commands for AIHL Geant4 simulation.");

    loadCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/material/load", this);
    loadCmd_->SetGuidance("Load materials from material.ini.");

    printCmd_ = std::make_unique<G4UIcmdWithoutParameter>("/AIHL/material/print", this);
    printCmd_->SetGuidance("Print materials, elements, and isotopes.");

    listCmd_ = std::make_unique<G4UIcmdWithoutParameter>("/AIHL/material/list", this);
    listCmd_->SetGuidance("List registered material manager names.");

    addNistCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/material/addNist", this);
    addNistCmd_->SetGuidance("Add NIST material: name=<alias> nist=<G4_NAME>.");

    addIsotopeCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/material/addIsotope", this);
    addIsotopeCmd_->SetGuidance("Add isotope: name=<name> symbol=<symbol> z=<Z> n=<N> a=\"<mass>\".");

    addElementCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/material/addElement", this);
    addElementCmd_->SetGuidance("Add simple element: name=<name> symbol=<symbol> z=<Z> a=\"<mass>\".");

    addElementFromIsotopesCmd_ =
        std::make_unique<G4UIcmdWithAString>("/AIHL/material/addElementFromIsotopes", this);
    addElementFromIsotopesCmd_->SetGuidance("Add isotopic element.");

    addMaterialCmd_ = std::make_unique<G4UIcmdWithAString>("/AIHL/material/addMaterial", this);
    addMaterialCmd_->SetGuidance("Add material: name=<name> density=\"...\" components=\"...\" mode=<mode>.");

    buildAllCmd_ = std::make_unique<G4UIcmdWithoutParameter>("/AIHL/material/buildAll", this);
    buildAllCmd_->SetGuidance("Build all pending material definitions.");

    setLockedCmd_ = std::make_unique<G4UIcmdWithABool>("/AIHL/material/setLocked", this);
    setLockedCmd_->SetGuidance("Lock or unlock MaterialManager definitions.");

    clearCmd_ = std::make_unique<G4UIcmdWithoutParameter>("/AIHL/material/clear", this);
    clearCmd_->SetGuidance("Clear MaterialManager definitions and caches.");
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
            G4cout << "[MaterialMessenger] Loaded materials from " << value
                   << " (materials=" << manager_->GetMaterialNames().size() << ")" << G4endl;
        });
    } else if (command == printCmd_.get()) {
        ExecuteWithWarning("/AIHL/material/print", [&]() { manager_->PrintAll(); });
    } else if (command == listCmd_.get()) {
        ExecuteWithWarning("/AIHL/material/list", [&]() {
            manager_->PrintIsotopes();
            manager_->PrintElements();
            manager_->PrintMaterials();
        });
    } else if (command == addNistCmd_.get()) {
        ExecuteWithWarning(value, [&]() {
            const auto args = MaterialCommandParser::ParseKeyValueLine(value);
            const std::string nist = MaterialCommandParser::Require(args, "nist", value);
            const auto nameIt = args.find("name");
            const std::string name = (nameIt == args.end() || nameIt->second.empty()) ? nist : nameIt->second;
            manager_->RegisterMaterial(name, manager_->BuildNistMaterial(nist));
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
            const auto mode = MaterialCommandParser::ParseMode(modeText);
            def.components = MaterialCommandParser::ParseMaterialComponents(
                MaterialCommandParser::Require(args, "components", value),
                mode
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
