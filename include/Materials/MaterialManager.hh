#pragma once

#include "Materials/MaterialDefinition.hh"

#include <map>
#include <set>
#include <string>
#include <vector>

class G4Element;
class G4Isotope;
class G4Material;

class MaterialManager {
public:
    MaterialManager();
    ~MaterialManager();

    void LoadMaterials(const std::string& filename);

    void AddIsotopeDefinition(const IsotopeDefinition& def);
    void AddElementDefinition(const ElementDefinition& def);
    void AddMaterialDefinition(const MaterialDefinition& def);

    G4Isotope* BuildIsotope(const std::string& name);
    G4Element* BuildElement(const std::string& name);
    G4Material* BuildMaterial(const std::string& name);

    void BuildAll();

    G4Material* GetMaterial(const std::string& name) const;
    G4Element* GetElement(const std::string& name) const;
    G4Isotope* GetIsotope(const std::string& name) const;

    bool HasMaterial(const std::string& name) const;
    bool HasElement(const std::string& name) const;
    bool HasIsotope(const std::string& name) const;

    G4Material* BuildNistMaterial(const std::string& name);

    G4Material* BuildCustomMaterial(const MaterialDefinition& desc);

    void RegisterMaterial(const std::string& name, G4Material* material);
    void RegisterElement(const std::string& name, G4Element* element);
    void RegisterIsotope(const std::string& name, G4Isotope* isotope);

    std::vector<std::string> GetMaterialNames() const;
    std::vector<std::string> GetElementNames() const;
    std::vector<std::string> GetIsotopeNames() const;

    void PrintMaterials() const;
    void PrintElements() const;
    void PrintIsotopes() const;
    void PrintAll() const;

    void Clear();

    void SetLocked(bool locked);
    bool IsLocked() const;

private:
    static std::string Normalize(const std::string& name);
    void EnsureUnlocked(const std::string& action) const;

    std::map<std::string, IsotopeDefinition> isotopeDefinitions_;
    std::map<std::string, ElementDefinition> elementDefinitions_;
    std::map<std::string, MaterialDefinition> materialDefinitions_;
    std::vector<std::string> nistMaterialDefinitions_;

    std::map<std::string, G4Isotope*> isotopes_;
    std::map<std::string, G4Element*> elements_;
    std::map<std::string, G4Material*> materials_;
    std::set<std::string> buildingMaterials_;

    bool locked_ = false;
};
