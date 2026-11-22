#pragma once

#include "Output/RunSummary.hh"
#include "Scoring/ScoringManager.hh"

#include <optional>
#include <stdexcept>
#include <string>
#include <type_traits>

namespace compiled_scorer {

// Source compatibility for the single trusted scorer chosen by a project.
inline constexpr int ApiVersion = 1;

class Definition {
public:
    template<auto Version>
    static constexpr Definition Declare(const char* id, ScorerFactoryRegistry::Factory factory)
    {
        static_assert(std::is_same_v<decltype(Version), int> && Version == ApiVersion,
                      "Unsupported compiled scorer API version (expected integer 1)");
        return Definition{id, factory};
    }

    constexpr const char* Id() const { return id_; }
    constexpr ScorerFactoryRegistry::Factory Factory() const { return factory_; }

private:
    constexpr Definition(const char* id, ScorerFactoryRegistry::Factory factory)
        : id_(id), factory_(factory) {}
    const char* id_;
    ScorerFactoryRegistry::Factory factory_;
};

inline void Register(const std::optional<Definition>& selected, ScoringManager& scoring, RunSummary& summary)
{
    if (!selected) return;
    const std::string id = selected->Id() ? selected->Id() : "";
    if (id.empty() || id.front() < 'a' || id.front() > 'z' ||
        id.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_") != std::string::npos)
        throw std::invalid_argument("Invalid compiled scorer registration id: " + id);
    scoring.RegisterScorerFactory(id, selected->Factory());
    scoring.RegisterScorer(ScorerDescription(id, id));
    summary.Set("compiled_scorer_api_version", ApiVersion);
    summary.Set("compiled_scorer_id", id);
}

}  // namespace compiled_scorer
