#pragma once

#include "Scoring/ScorerBase.hh"
#include <map>
#include <memory>
#include <set>
#include <string>

class NielTable;

// A finite value snapshot. No writer, accumulator or mutable thread resource.
struct ScorerSettings {
    struct Histogram { int bins = 200; double min = 0; double max = 10; bool configured = false; };
    Histogram rawHistogram, weightedHistogram;
    bool rawEnabled = true, weightedEnabled = true, volumeSummary = true, particleSummary = true;
    std::set<std::string> particles;
    std::map<std::string, std::shared_ptr<const NielTable>> nielTables;
    std::map<std::string, double> parameters;
};

class ScorerDescription {
public:
    ScorerDescription(std::string id, std::string type, bool enabled = true,
                      ScorerSettings settings = {});
    const std::string& Id() const { return id_; }
    const std::string& Type() const { return type_; }
    bool Enabled() const { return enabled_; }
    const ScorerSettings& Settings() const { return settings_; }
    static std::string Normalize(const std::string& value);
private:
    std::string id_, type_;
    bool enabled_;
    ScorerSettings settings_;
};

// Explicit, configuration-time registration; no closures capturing master state.
// Do not mutate a Manager while it is being cloned. Each clone owns a registry copy.
class ScorerFactoryRegistry {
public:
    using Factory = std::unique_ptr<ScorerBase> (*)(const ScorerDescription&, int threadId);
    void Register(const std::string& type, Factory factory);
    void Freeze() { frozen_ = true; }
    std::unique_ptr<ScorerBase> Create(const ScorerDescription& description, int threadId) const;
private:
    std::map<std::string, Factory> factories_;
    bool frozen_ = false;
};

ScorerFactoryRegistry BuiltinScorerFactories();
