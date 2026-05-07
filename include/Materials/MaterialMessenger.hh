#pragma once

#include "G4UImessenger.hh"

#include <functional>
#include <memory>
#include <string>

class G4UIcmdWithABool;
class G4UIcmdWithAString;
class G4UIcmdWithoutParameter;
class G4UIcommand;
class G4UIdirectory;
class G4String;
class MaterialManager;

class MaterialMessenger : public G4UImessenger {
public:
    explicit MaterialMessenger(MaterialManager* manager);
    ~MaterialMessenger() override;

    void SetNewValue(G4UIcommand* command, G4String newValue) override;

private:
    void ExecuteWithWarning(const std::string& commandText, const std::function<void()>& action);

    MaterialManager* manager_ = nullptr;
    std::unique_ptr<G4UIdirectory> materialDir_;
    std::unique_ptr<G4UIcmdWithAString> loadCmd_;
    std::unique_ptr<G4UIcmdWithoutParameter> printCmd_;
    std::unique_ptr<G4UIcmdWithoutParameter> listCmd_;
    std::unique_ptr<G4UIcmdWithAString> addNistCmd_;
    std::unique_ptr<G4UIcmdWithAString> addIsotopeCmd_;
    std::unique_ptr<G4UIcmdWithAString> addElementCmd_;
    std::unique_ptr<G4UIcmdWithAString> addElementFromIsotopesCmd_;
    std::unique_ptr<G4UIcmdWithAString> addMaterialCmd_;
    std::unique_ptr<G4UIcmdWithoutParameter> buildAllCmd_;
    std::unique_ptr<G4UIcmdWithABool> setLockedCmd_;
    std::unique_ptr<G4UIcmdWithoutParameter> clearCmd_;
};
