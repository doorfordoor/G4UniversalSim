#pragma once

#include "Materials/MaterialDefinition.hh"

#include <map>
#include <stdexcept>
#include <string>
#include <vector>

class MaterialIniReader {
public:
    using Section = std::map<std::string, std::string>;

    MaterialIniReader() = default;

    void Load(const std::string& filename);

    bool HasIsotope(const std::string& name) const;
    bool HasElement(const std::string& name) const;
    bool HasMaterial(const std::string& name) const;

    const IsotopeDefinition& GetIsotopeDefinition(const std::string& name) const;
    const ElementDefinition& GetElementDefinition(const std::string& name) const;
    const MaterialDefinition& GetMaterialDefinition(const std::string& name) const;

    std::vector<std::string> GetIsotopeNames() const;
    std::vector<std::string> GetElementNames() const;
    std::vector<std::string> GetMaterialNames() const;
    std::vector<std::string> GetNistMaterialNames() const;

    void Clear();

    static std::string Normalize(const std::string& name);
    static std::runtime_error Error(
        const std::string& filename,
        const std::string& section,
        const std::string& key,
        const std::string& message
    );
    static std::string Require(
        const Section& sectionData,
        const std::string& filename,
        const std::string& section,
        const std::string& key
    );

private:
    void ParseSections(
        const std::string& filename,
        const std::map<std::string, Section>& sections
    );

    std::vector<std::string> nistMaterials_;
    std::map<std::string, IsotopeDefinition> isotopes_;
    std::map<std::string, ElementDefinition> elements_;
    std::map<std::string, MaterialDefinition> materials_;
};
