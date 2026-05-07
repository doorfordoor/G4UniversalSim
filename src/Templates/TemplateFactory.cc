#include "Templates/TemplateFactory.hh"

#include "Templates/ArrayTemplate.hh"
#include "Templates/GDMLTemplate.hh"
#include "Templates/GeometryTemplate.hh"
#include "Templates/HierarchicalVolumeTemplate.hh"
#include "Templates/LayeredDeviceTemplate.hh"
#include "Templates/ShieldingTemplate.hh"
#include "Templates/SimpleBoxTemplate.hh"
#include "Utils/StringUtils.hh"

#include <stdexcept>

std::unique_ptr<GeometryTemplate> TemplateFactory::Create(const std::string& name)
{
    const std::string value = StringUtils::ToLower(StringUtils::Trim(name));
    if (value == "simple_box" || value == "simple") return std::make_unique<SimpleBoxTemplate>();
    if (value == "layered_device" || value == "layered") return std::make_unique<LayeredDeviceTemplate>();
    if (value == "hierarchical") return std::make_unique<HierarchicalVolumeTemplate>();
    if (value == "array") return std::make_unique<ArrayTemplate>();
    if (value == "shielding") return std::make_unique<ShieldingTemplate>();
    if (value == "gdml") return std::make_unique<GDMLTemplate>();
    throw std::runtime_error("Unknown geometry template: '" + name + "'");
}

std::vector<std::string> TemplateFactory::AvailableTemplates()
{
    return {"simple_box", "layered_device", "hierarchical", "array", "shielding", "gdml"};
}
