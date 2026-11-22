#pragma once
// Module-private H4 observation seam shared by production and its direct probe.
// Native algorithms and return values remain authoritative; no RNG is added.
#include "Config/EffectiveRuntime.hh"
#include "Scoring/ScoringManager.hh"
#include "Scoring/ThreadLocalScoringContext.hh"
#include "G4ImportanceAlgorithm.hh"
#include "G4WeightWindowAlgorithm.hh"
#include "G4Version.hh"
#if G4VERSION_NUMBER >= 1140
#include "Biasing/detail/GeometricSamplingStores114.hh"
#else
#include "G4WeightWindowStore.hh"
#endif
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>

namespace biasing_detail {
struct SamplingObservation {
    bool active = false;
    bool invalidEnergy = false;
    bool failureReported = false;
    bool overflow = false;
    int runId = -1;
    std::int64_t calls = 0, returns = 0, actions = 0, split = 0, requestedExtraTracks = 0;
    std::int64_t suppressedAfterInvalidEnergy = 0;
    std::int64_t kill = 0, rouletteSurvived = 0, unchanged = 0, singleReduced = 0, invalidReturn = 0;
    std::int64_t energyQueries = 0, finiteEnergies = 0, nonfiniteEnergies = 0, negativeEnergies = 0;
    double energyMin = 0, energyMax = 0;

    void Count(std::int64_t& value, std::int64_t amount = 1) noexcept
    {
        if (amount > std::numeric_limits<std::int64_t>::max() - value) overflow = true;
        else value += amount;
    }
    void Reset(int id) noexcept { *this = SamplingObservation{}; runId = id; active = true; }
    void NativeCall() noexcept { if (active) Count(calls); }
    void Observe(double initialWeight, const G4Nsplit_Weight& outcome) noexcept
    {
        if (!active) return;
        Count(returns);
        if (outcome.fN < 0 || !std::isfinite(initialWeight) || initialWeight <= 0 ||
            !std::isfinite(outcome.fW) || outcome.fW < 0 || (outcome.fN > 0 && outcome.fW == 0)) {
            Count(invalidReturn);
            return;
        }
        // These are native algorithm decisions, not observed stack insertions.
        if (outcome.fN != 1 || outcome.fW != initialWeight) Count(actions);
        if (outcome.fN == 0) Count(kill);
        else if (outcome.fN > 1) {
            Count(split);
            Count(requestedExtraTracks, static_cast<std::int64_t>(outcome.fN) - 1);
        } else if (outcome.fW > initialWeight) Count(rouletteSurvived);
        else if (outcome.fW < initialWeight) Count(singleReduced);
        else Count(unchanged);
    }
    bool ObserveEnergy(double energy) noexcept
    {
        if (!active) return true;
        Count(energyQueries);
        if (!std::isfinite(energy)) { Count(nonfiniteEnergies); invalidEnergy = true; }
        else if (energy < 0) { Count(negativeEnergies); invalidEnergy = true; }
        else {
            if (finiteEnergies == 0) energyMin = energyMax = energy;
            else { energyMin = std::min(energyMin, energy); energyMax = std::max(energyMax, energy); }
            Count(finiteEnergies);
            return true;
        }
        // Follow the existing XS callback failure contract. Reporting cannot
        // throw across a transport callback; EndRun also rejects the latched run.
        if (!failureReported) {
            failureReported = true;
            try {
                if (auto* scoring = AIHL::GetCurrentThreadScoringManager())
                    scoring->ReportScoringFailure("h4_weight_window_energy",
                        "sampled neutron kinetic energy must be finite and nonnegative");
            } catch (...) {}
            if (auto* manager = G4RunManager::GetRunManager()) manager->AbortRun(true);
        }
        return false;
    }
    effective_config::Value::Object Fields() const
    {
        using effective_config::Value;
        return {{"observation_run_id", runId}, {"sampler_calculate_calls", calls}, {"sampler_calculate_returns", returns}, {"sampler_actions", actions},
            {"sampler_suppressed_after_invalid_energy", suppressedAfterInvalidEnergy},
            {"sampler_split_outcomes", split}, {"sampler_requested_extra_tracks", requestedExtraTracks},
            {"sampler_kill_outcomes", kill}, {"sampler_roulette_survived_outcomes", rouletteSurvived},
            {"sampler_unchanged_outcomes", unchanged}, {"sampler_single_weight_reduced_outcomes", singleReduced},
            {"sampler_invalid_return_outcomes", invalidReturn}, {"sampled_neutron_E_query_count", energyQueries},
            {"sampled_neutron_E_finite_count", finiteEnergies}, {"sampled_neutron_E_nonfinite", nonfiniteEnergies},
            {"sampled_neutron_E_negative", negativeEnergies},
            {"sampled_neutron_E_min_MeV", finiteEnergies ? Value(energyMin) : Value()},
            {"sampled_neutron_E_max_MeV", finiteEnergies ? Value(energyMax) : Value()},
            {"observation_valid", !invalidEnergy && !overflow && invalidReturn == 0},
            {"counter_overflow", overflow}, {"manual_probe_queries_excluded", true},
            {"sampler_action_semantics", "valid native Calculate result: N!=1 or output weight differs; requested tracks are not observed stack insertions"}};
    }
};

class ObservedImportanceAlgorithm final : public G4ImportanceAlgorithm {
public:
    explicit ObservedImportanceAlgorithm(SamplingObservation& observation) : observation_(observation) {}
    G4Nsplit_Weight Calculate(G4double before, G4double after, G4double weight) const override
    {
        observation_.NativeCall();
        const auto result = G4ImportanceAlgorithm::Calculate(before, after, weight);
        observation_.Observe(weight, result);
        return result;
    }
private:
    SamplingObservation& observation_;
};
class ObservedWeightWindowAlgorithm final : public G4WeightWindowAlgorithm {
public:
    ObservedWeightWindowAlgorithm(double upper, double survival, int maximum, SamplingObservation& observation)
        : G4WeightWindowAlgorithm(upper, survival, maximum), observation_(observation) {}
    G4Nsplit_Weight Calculate(G4double weight, G4double lower) const override
    {
        // Invalid tracked energy has already failed/aborted the run. Contain
        // that failed callback without querying NaN or consuming another RNG draw;
        // this is never counted as a native algorithm outcome or successful run.
        if (observation_.invalidEnergy) {
            if (observation_.active) observation_.Count(observation_.suppressedAfterInvalidEnergy);
            return G4Nsplit_Weight{};
        }
        observation_.NativeCall();
        const auto result = G4WeightWindowAlgorithm::Calculate(weight, lower);
        observation_.Observe(weight, result);
        return result;
    }
private:
    SamplingObservation& observation_;
};
#if G4VERSION_NUMBER >= 1140
using WeightWindowStoreBase = OwnedWeightWindowStore;
#else
using WeightWindowStoreBase = G4WeightWindowStore;
#endif
class WeightWindowStore final : public WeightWindowStoreBase {
public:
#if G4VERSION_NUMBER >= 1140
    WeightWindowStore(SamplingObservation& observation, const G4VPhysicalVolume& world)
        : WeightWindowStoreBase(world), observation_(observation) {}
#else
    explicit WeightWindowStore(SamplingObservation& observation) : observation_(observation) {}
#endif
    ~WeightWindowStore() override = default;
    G4double GetLowerWeight(const G4GeometryCell& cell, G4double energy) const override
    {
        if (!observation_.ObserveEnergy(energy)) return 1.0; // failed-run containment only
        return WeightWindowStoreBase::GetLowerWeight(cell, energy);
    }
    G4double ReadLowerWeight(const G4GeometryCell& cell, G4double energy) const
    {
        return WeightWindowStoreBase::GetLowerWeight(cell, energy); // manual probe, excluded
    }
private:
    SamplingObservation& observation_;
};

} // namespace biasing_detail
