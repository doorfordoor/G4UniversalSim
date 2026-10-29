#pragma once

#include "Geometry/VolumeNode.hh"
#include "Geometry/GeometryConfigDiagnostic.hh"

#include "Config/IniReader.hh"
#include "Config/InputProvenance.hh"
#include <string>

class ConfigManager;
class GeometryConfig;

class GeometryTemplate {
public:
    virtual ~GeometryTemplate() = default;

    virtual std::string Name() const = 0;

    virtual VolumeNode BuildNodes(const ConfigManager& config) const = 0;

    virtual VolumeNode BuildNodesFromFile(const std::string& filename) const;

    virtual VolumeNode BuildNodes(const GeometryConfig& geometryConfig) const;

    virtual void ValidateConfig(const ConfigManager& config) const;

    const std::vector<GeometryConfigDiagnostic>& GetDiagnostics() const;
    const IniReader& GetInputReader() const { return inputReader_; }
    const std::vector<input_provenance::InputFile>& GetInputs() const { return inputs_; }

protected:
    mutable IniReader inputReader_;
    mutable std::vector<input_provenance::InputFile> inputs_;
    mutable std::vector<GeometryConfigDiagnostic> diagnostics_;
};
