#pragma once

#include <memory>
#include <string>
#include <vector>

class GeometryTemplate;

class TemplateFactory {
public:
    static std::unique_ptr<GeometryTemplate> Create(const std::string& name);
    static std::vector<std::string> AvailableTemplates();
};
