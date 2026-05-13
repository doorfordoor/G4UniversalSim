#pragma once

#include <algorithm>
#include <cctype>
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

namespace BiasingConfigDetail {

inline std::string Trim(const std::string& text)
{
    const auto first = std::find_if_not(text.begin(), text.end(), [](unsigned char c) { return std::isspace(c); });
    const auto last = std::find_if_not(text.rbegin(), text.rend(), [](unsigned char c) { return std::isspace(c); }).base();
    if (first >= last) return {};
    return std::string(first, last);
}

inline std::string ToLower(std::string text)
{
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return text;
}

inline std::string Join(const std::vector<std::string>& values, const std::string& emptyText)
{
    if (values.empty()) return emptyText;
    std::ostringstream oss;
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i > 0) oss << ",";
        oss << values[i];
    }
    return oss.str();
}

inline bool SameProcessRuleKey(const std::string& particleA,
                               const std::string& processA,
                               const std::string& particleB,
                               const std::string& processB)
{
    return ToLower(Trim(particleA)) == ToLower(Trim(particleB))
        && Trim(processA) == Trim(processB);
}

}  // namespace BiasingConfigDetail

// Legacy particle-level rule kept for old ini and macro compatibility.
//
// New code should prefer XSProcessBiasRule, which is keyed by particle+process.
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
    bool legacy = true;

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
        if (BiasingConfigDetail::Trim(particleName).empty()) {
            throw std::runtime_error("XSBiasRule validation failed: particleName is empty");
        }
        if (factor <= 0.0) {
            throw std::runtime_error("XSBiasRule validation failed for '" + particleName + "': factor must be > 0");
        }
        if (minWeight < 0.0) {
            throw std::runtime_error("XSBiasRule validation failed for '" + particleName + "': minWeight must be >= 0");
        }
        if (maxInteractions < -1) {
            throw std::runtime_error("XSBiasRule validation failed for '" + particleName + "': maxInteractions must be -1 or >= 0");
        }
        if (onlyPrimary && applyToSecondaries) {
            throw std::runtime_error(
                "XSBiasRule validation failed for '" + particleName
                + "': onlyPrimary=true conflicts with applyToSecondaries=true"
            );
        }
    }

    std::string ToString() const
    {
        std::ostringstream oss;
        oss << "LegacyXSBiasRule{name=" << (name.empty() ? "<unnamed>" : name)
            << ", particle=" << particleName
            << ", processes=" << BiasingConfigDetail::Join(processNames, "<none>")
            << ", factor=" << factor
            << ", onlyPrimary=" << (onlyPrimary ? "true" : "false")
            << ", applyToSecondaries=" << (applyToSecondaries ? "true" : "false")
            << ", minWeight=" << minWeight
            << ", maxInteractions=" << maxInteractions
            << ", volumes=" << BiasingConfigDetail::Join(volumeNames, "<deferred>")
            << ", enabled=" << (enabled ? "true" : "false")
            << "}";
        return oss.str();
    }
};

struct XSProcessBiasRule {
    std::string name;
    std::string particleName;
    std::string processName;
    double factor = 1.0;
    std::vector<std::string> volumeNames;
    bool onlyPrimary = true;
    bool applyToSecondaries = false;
    double minWeight = 0.05;
    int maxInteractions = 5;
    bool enabled = true;
    bool legacyGenerated = false;

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
        if (BiasingConfigDetail::Trim(particleName).empty()) {
            throw std::runtime_error("XSProcessBiasRule validation failed: particleName is empty");
        }
        if (BiasingConfigDetail::Trim(processName).empty()) {
            throw std::runtime_error("XSProcessBiasRule validation failed for particle '" + particleName + "': processName is empty");
        }
        if (factor <= 0.0) {
            throw std::runtime_error("XSProcessBiasRule validation failed for '" + Key() + "': factor must be > 0");
        }
        if (minWeight < 0.0) {
            throw std::runtime_error("XSProcessBiasRule validation failed for '" + Key() + "': minWeight must be >= 0");
        }
        if (maxInteractions < -1) {
            throw std::runtime_error("XSProcessBiasRule validation failed for '" + Key() + "': maxInteractions must be -1 or >= 0");
        }
        if (onlyPrimary && applyToSecondaries) {
            throw std::runtime_error(
                "XSProcessBiasRule validation failed for '" + Key()
                + "': onlyPrimary=true conflicts with applyToSecondaries=true"
            );
        }
    }

    std::string Key() const
    {
        return BiasingConfigDetail::ToLower(BiasingConfigDetail::Trim(particleName))
            + "|" + BiasingConfigDetail::Trim(processName);
    }

    std::string ToString() const
    {
        std::ostringstream oss;
        oss << "XSProcessBiasRule{name=" << (name.empty() ? "<unnamed>" : name)
            << ", particle=" << particleName
            << ", process=" << processName
            << ", factor=" << factor
            << ", onlyPrimary=" << (onlyPrimary ? "true" : "false")
            << ", applyToSecondaries=" << (applyToSecondaries ? "true" : "false")
            << ", minWeight=" << minWeight
            << ", maxInteractions=" << maxInteractions
            << ", volumes=" << BiasingConfigDetail::Join(volumeNames, "<deferred>")
            << ", enabled=" << (enabled ? "true" : "false")
            << ", legacyGenerated=" << (legacyGenerated ? "true" : "false")
            << "}";
        return oss.str();
    }
};

struct BiasingConfig {
    bool enabled = false;
    std::vector<XSBiasRule> xsRules;
    std::vector<XSProcessBiasRule> xsProcessRules;

    void Clear()
    {
        enabled = false;
        xsRules.clear();
        xsProcessRules.clear();
    }

    bool HasRules() const
    {
        return !xsRules.empty() || !xsProcessRules.empty();
    }

    void AddProcessRule(const XSProcessBiasRule& rule)
    {
        XSProcessBiasRule copy = rule;
        copy.particleName = BiasingConfigDetail::Trim(copy.particleName);
        copy.processName = BiasingConfigDetail::Trim(copy.processName);
        if (copy.applyToSecondaries) copy.onlyPrimary = false;
        if (copy.onlyPrimary) copy.applyToSecondaries = false;
        if (copy.name.empty()) copy.name = "xs_" + copy.particleName + "_" + copy.processName;
        copy.Validate();

        for (XSProcessBiasRule& existing : xsProcessRules) {
            if (BiasingConfigDetail::SameProcessRuleKey(existing.particleName, existing.processName, copy.particleName, copy.processName)) {
                if (existing.legacyGenerated && !copy.legacyGenerated) {
                    existing = copy;
                } else if (!existing.legacyGenerated && !copy.legacyGenerated) {
                    existing = copy;
                } else if (existing.legacyGenerated && copy.legacyGenerated) {
                    existing = copy;
                }
                return;
            }
        }
        xsProcessRules.push_back(copy);
    }

    std::vector<XSBiasRule> GetEnabledXSRules() const
    {
        std::vector<XSBiasRule> rules;
        for (const XSBiasRule& rule : xsRules) {
            if (rule.enabled) rules.push_back(rule);
        }
        return rules;
    }

    std::vector<XSProcessBiasRule> GetEnabledXSProcessRules() const
    {
        std::vector<XSProcessBiasRule> rules;
        for (const XSProcessBiasRule& rule : xsProcessRules) {
            if (rule.enabled) rules.push_back(rule);
        }
        return rules;
    }

    void ExpandLegacyRulesToProcessRules()
    {
        std::vector<XSProcessBiasRule> expanded;
        for (const XSBiasRule& legacyRule : xsRules) {
            if (!legacyRule.enabled) continue;
            legacyRule.Validate();
            for (const std::string& processName : legacyRule.processNames) {
                const std::string process = BiasingConfigDetail::Trim(processName);
                if (process.empty()) continue;

                XSProcessBiasRule rule;
                rule.name = legacyRule.name.empty()
                    ? "xs_" + legacyRule.particleName + "_" + process
                    : legacyRule.name + "_" + process;
                rule.particleName = legacyRule.particleName;
                rule.processName = process;
                rule.factor = legacyRule.factor;
                rule.volumeNames = legacyRule.volumeNames;
                rule.onlyPrimary = legacyRule.onlyPrimary;
                rule.applyToSecondaries = legacyRule.applyToSecondaries;
                if (rule.applyToSecondaries) rule.onlyPrimary = false;
                if (rule.onlyPrimary) rule.applyToSecondaries = false;
                rule.minWeight = legacyRule.minWeight;
                rule.maxInteractions = legacyRule.maxInteractions;
                rule.enabled = legacyRule.enabled;
                rule.legacyGenerated = true;
                rule.Validate();
                expanded.push_back(rule);
            }
        }

        for (const XSProcessBiasRule& rule : expanded) {
            bool hasExplicit = false;
            for (const XSProcessBiasRule& existing : xsProcessRules) {
                if (!existing.legacyGenerated
                    && BiasingConfigDetail::SameProcessRuleKey(existing.particleName, existing.processName, rule.particleName, rule.processName)) {
                    hasExplicit = true;
                    break;
                }
            }
            if (!hasExplicit) AddProcessRule(rule);
        }
    }

    void Validate() const
    {
        for (const XSBiasRule& rule : xsRules) rule.Validate();
        for (const XSProcessBiasRule& rule : xsProcessRules) rule.Validate();
    }
};
