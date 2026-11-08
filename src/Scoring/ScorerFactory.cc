#include "Scoring/ScorerFactory.hh"
#include "Scoring/DisplacementScorer.hh"
#include "Scoring/DoseScorer.hh"
#include "Scoring/EdepScorer.hh"
#include "Scoring/FluenceScorer.hh"
#include "Scoring/LETScorer.hh"
#include "Utils/StringUtils.hh"
#include <stdexcept>
#include <utility>

std::string ScorerDescription::Normalize(const std::string& value)
{
    return StringUtils::ToLower(StringUtils::Trim(value));
}

ScorerDescription::ScorerDescription(std::string id, std::string type, bool enabled, ScorerSettings settings)
    : id_(Normalize(id)), type_(Normalize(type)), enabled_(enabled), settings_(std::move(settings))
{
    if (id_.empty() || type_.empty()) throw std::runtime_error("Scorer description requires nonempty id and type");
}

void ScorerFactoryRegistry::Register(const std::string& type, Factory factory)
{
    if (frozen_) throw std::runtime_error("Scorer factory registry is frozen");
    const auto key = ScorerDescription::Normalize(type);
    if (key.empty() || !factory) throw std::runtime_error("Scorer factory requires nonempty type and nonnull factory");
    if (!factories_.emplace(key, factory).second) throw std::runtime_error("Duplicate scorer factory type: " + key);
}

std::unique_ptr<ScorerBase> ScorerFactoryRegistry::Create(const ScorerDescription& description, int threadId) const
{
    const std::string context = "Scorer factory type='" + description.Type() + "' id='" + description.Id() +
        "' thread=" + std::to_string(threadId) + ": ";
    const auto found = factories_.find(description.Type());
    if (found == factories_.end()) throw std::runtime_error(context + "unknown type");
    try {
        auto scorer = found->second(description, threadId);
        if (!scorer) throw std::runtime_error("returned null instance");
        if (ScorerDescription::Normalize(scorer->GetName()) != description.Id())
            throw std::runtime_error("returned name mismatch: " + scorer->GetName());
        scorer->SetEnabled(description.Enabled());
        return scorer;
    } catch (const std::exception& error) {
        throw std::runtime_error(context + error.what());
    } catch (...) {
        throw std::runtime_error(context + "non-standard exception");
    }
}

namespace {
void RequireCanonicalBuiltin(const ScorerDescription& description)
{
    // Existing writers and statistics use one fixed namespace per builtin.
    // Multiple names would overwrite files or mix instances in the same key.
    if (description.Id() != description.Type())
        throw std::runtime_error("Builtin scorer type requires its canonical id; aliases are unsupported");
}
std::unique_ptr<ScorerBase> MakeEdep(const ScorerDescription& d, int)
{
    RequireCanonicalBuiltin(d);
    auto s = std::make_unique<EdepScorer>(d.Id());
    const auto& c = d.Settings();
    s->EnableRawHistogram(c.rawEnabled); s->EnableWeightedHistogram(c.weightedEnabled);
    s->EnableVolumeSummary(c.volumeSummary); s->EnableParticleSummary(c.particleSummary);
    if (c.rawHistogram.configured) s->ConfigureRawHistogram(c.rawHistogram.bins,c.rawHistogram.min,c.rawHistogram.max);
    if (c.weightedHistogram.configured) s->ConfigureWeightedHistogram(c.weightedHistogram.bins,c.weightedHistogram.min,c.weightedHistogram.max);
    return s;
}
std::unique_ptr<ScorerBase> MakeLET(const ScorerDescription& d, int)
{
    RequireCanonicalBuiltin(d);
    auto s = std::make_unique<LETScorer>(d.Id()); s->SetParticles(d.Settings().particles); return s;
}
std::unique_ptr<ScorerBase> MakeDose(const ScorerDescription& d, int) {
    RequireCanonicalBuiltin(d); return std::make_unique<DoseScorer>(d.Id());
}
std::unique_ptr<ScorerBase> MakeFluence(const ScorerDescription& d, int) {
    RequireCanonicalBuiltin(d); return std::make_unique<FluenceScorer>(d.Id());
}
std::unique_ptr<ScorerBase> MakeDisplacement(const ScorerDescription& d, int)
{
    RequireCanonicalBuiltin(d);
    auto s = std::make_unique<DisplacementScorer>(d.Id()); s->SetTables(d.Settings().nielTables); return s;
}
}

ScorerFactoryRegistry BuiltinScorerFactories()
{
    ScorerFactoryRegistry registry;
    registry.Register("edep", MakeEdep); registry.Register("let", MakeLET);
    registry.Register("dose", MakeDose); registry.Register("fluence", MakeFluence);
    registry.Register("displacement", MakeDisplacement);
    return registry;
}
