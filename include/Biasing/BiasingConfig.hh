#pragma once

#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

enum class BiasingType {
    None,
    CrossSection,
    Region,
    Importance
};

struct XSBiasRule {
    std::string name;
    std::string particleName;
    std::vector<std::string> processNames;
    double factor = 1.0;
    bool onlyPrimary = true;
    bool applyToSecondaries = false;
    double minWeight = 0.05;
    int maxInteractions = 5;
    std::vector<std::string> volumeNames;
    bool enabled = true;

    bool IsValid() const
    {
        try {
            Validate();
            return true;
        } catch (...) {
            return false;
        }
    }

    void Validate() const
    {
        if (particleName.empty()) throw std::runtime_error("XSBiasRule validation failed: particleName is empty");
        if (factor <= 0.0) throw std::runtime_error("XSBiasRule validation failed for '" + particleName + "': factor must be > 0");
        if (minWeight <= 0.0) throw std::runtime_error("XSBiasRule validation failed for '" + particleName + "': minWeight must be > 0");
        if (maxInteractions < 0) throw std::runtime_error("XSBiasRule validation failed for '" + particleName + "': maxInteractions must be >= 0");
        if (onlyPrimary && applyToSecondaries) {
            throw std::runtime_error(
                "XSBiasRule validation failed for '" + particleName
                + "': onlyPrimary=true conflicts with applyToSecondaries=true"
            );
        }
    }

    std::string ToString() const
    {
        const auto join = [](const std::vector<std::string>& values) {
            if (values.empty()) return std::string("<all-or-deferred>");
            std::ostringstream oss;
            for (std::size_t i = 0; i < values.size(); ++i) {
                if (i > 0) oss << ",";
                oss << values[i];
            }
            return oss.str();
        };

        std::ostringstream oss;
        oss << "XSBiasRule{name=" << (name.empty() ? "<unnamed>" : name)
            << ", particle=" << particleName
            << ", processes=" << join(processNames)
            << ", factor=" << factor
            << ", onlyPrimary=" << (onlyPrimary ? "true" : "false")
            << ", applyToSecondaries=" << (applyToSecondaries ? "true" : "false")
            << ", minWeight=" << minWeight
            << ", maxInteractions=" << maxInteractions
            << ", volumes=" << join(volumeNames)
            << ", enabled=" << (enabled ? "true" : "false")
            << "}";
        return oss.str();
    }
};

struct BiasingConfig {
    bool enabled = false;
    std::vector<XSBiasRule> xsRules;

    void Clear()
    {
        enabled = false;
        xsRules.clear();
    }

    bool HasRules() const
    {
        return !xsRules.empty();
    }

    std::vector<XSBiasRule> GetEnabledXSRules() const
    {
        std::vector<XSBiasRule> rules;
        for (const XSBiasRule& rule : xsRules) {
            if (rule.enabled) rules.push_back(rule);
        }
        return rules;
    }

    void Validate() const
    {
        for (const XSBiasRule& rule : xsRules) rule.Validate();
    }
};
