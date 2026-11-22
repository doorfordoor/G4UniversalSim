// Direct production-component contract: no run manager, geometry or transport.
#include "Biasing/detail/GeometricSamplingObservation.hh"
#include "BuildInfo.hh"
#include "Randomize.hh"
#include <iostream>
#include <limits>
#include <stdexcept>

namespace {
int checks = 0;
void Require(bool ok, const char* why)
{
    if (!ok) throw std::runtime_error(why);
    ++checks;
}
void Same(const G4Nsplit_Weight& expected, const G4Nsplit_Weight& actual)
{
    Require(expected.fN == actual.fN, "native result multiplicity changed");
    Require(expected.fW == actual.fW, "native result weight changed");
}
void NativeDelegation()
{
    using namespace biasing_detail;
    const double importance[][3] = {{1, 1, 1}, {1, 4, 1}, {4, 1, 0.25}, {1, 1.5, 1}};
    int index = 0;
    for (const auto& values : importance) {
        G4ImportanceAlgorithm native;
        SamplingObservation observation;
        ObservedImportanceAlgorithm observed(observation);
        G4Random::setTheSeed(2026112001 + index);
        const auto expected = native.Calculate(values[0], values[1], values[2]);
        const auto expectedState = G4Random::getTheEngine()->put();
        G4Random::setTheSeed(2026112001 + index);
        observation.Reset(index++);
        const auto actual = observed.Calculate(values[0], values[1], values[2]);
        Same(expected, actual);
        Require(expectedState == G4Random::getTheEngine()->put(), "importance observation changed RNG state");
        Require(observation.calls == 1 && observation.returns == 1, "importance call/return not observed once");
    }
    const double windows[][2] = {{1, 0.125}, {0.25, 1}, {1, 1}};
    for (const auto& values : windows) {
        G4WeightWindowAlgorithm native(2, 1, 100);
        SamplingObservation observation;
        ObservedWeightWindowAlgorithm observed(2, 1, 100, observation);
        G4Random::setTheSeed(2026112001 + index);
        const auto expected = native.Calculate(values[0], values[1]);
        const auto expectedState = G4Random::getTheEngine()->put();
        G4Random::setTheSeed(2026112001 + index);
        observation.Reset(index++);
        const auto actual = observed.Calculate(values[0], values[1]);
        Same(expected, actual);
        Require(expectedState == G4Random::getTheEngine()->put(), "window observation changed RNG state");
        Require(observation.calls == 1 && observation.returns == 1, "window call/return not observed once");
    }
}
void ClassificationContract()
{
    using namespace biasing_detail;
    SamplingObservation observation;
    observation.Reset(7);
    // Explicit return-value fixtures test the real counter component's public
    // contract, not transported tracks or scientific sampler_actions evidence.
    const int multiplicities[] = {4, 0, 1, 1, 1};
    const double weights[] = {0.25, 0, 2, 1, 0.5};
    for (int i = 0; i < 5; ++i) {
        G4Nsplit_Weight outcome; outcome.fN = multiplicities[i]; outcome.fW = weights[i];
        observation.NativeCall(); observation.Observe(1, outcome);
    }
    Require(observation.calls == 5 && observation.returns == 5, "classification fixture call count");
    Require(observation.actions == 4 && observation.unchanged == 1, "actions include an unchanged result");
    Require(observation.split == 1 && observation.requestedExtraTracks == 3, "requested split count");
    Require(observation.kill == 1 && observation.rouletteSurvived == 1 && observation.singleReduced == 1,
            "kill/roulette/single reduction conflated");
    Require(observation.invalidReturn == 0, "valid result fixtures rejected");
    observation.Reset(8);
    Require(observation.runId == 8 && observation.calls == 0 && observation.actions == 0 && observation.energyQueries == 0,
            "new run retained old counts");
}
void EnergyRejectionContract()
{
    using namespace biasing_detail;
    SamplingObservation observation;
    observation.Reset(10);
    Require(observation.ObserveEnergy(0) && observation.ObserveEnergy(2), "valid finite energy rejected");
    Require(observation.energyQueries == 2 && observation.finiteEnergies == 2 && observation.energyMin == 0 && observation.energyMax == 2,
            "finite energy range was not measured");
    const double invalid[] = {-1, std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN()};
    int run = 11;
    for (double energy : invalid) {
        observation.Reset(run++);
        Require(!observation.ObserveEnergy(energy), "illegal energy was accepted by production rejection component");
        Require(observation.invalidEnergy && observation.failureReported && observation.finiteEnergies == 0,
                "illegal energy did not latch failure");
        Require(observation.energyQueries == 1 && observation.nonfiniteEnergies + observation.negativeEnergies == 1,
                "illegal energy count conflated");
        ObservedWeightWindowAlgorithm observed(2, 1, 100, observation);
        const auto before = G4Random::getTheEngine()->put();
        const auto containment = observed.Calculate(1, 1);
        Require(containment.fN == 0 && containment.fW == 0, "failed callback did not terminate track");
        Require(before == G4Random::getTheEngine()->put(), "failed callback consumed RNG");
        Require(observation.calls == 0 && observation.returns == 0 && observation.actions == 0 && observation.suppressedAfterInvalidEnergy == 1,
                "failed containment reported a native outcome");
        const auto fields = observation.Fields();
        Require(!std::get<bool>(fields.at("observation_valid").data), "illegal energy reports valid observation");
        Require(std::holds_alternative<std::nullptr_t>(fields.at("sampled_neutron_E_min_MeV").data),
                "empty range fabricated an energy minimum");
    }
}
}

int main(int argc, char** argv)
{
    try {
        using effective_config::Value;
        if (argc == 2 && std::string(argv[1]) == "--identity") {
            std::cout << Value(Value::Object{{"source_fingerprint", G4USIM_SOURCE_FINGERPRINT},
                {"probe_sha256", G4USIM_H4_OBSERVATION_PROBE_SHA256},
                {"observer_sha256", G4USIM_H4_OBSERVATION_SOURCE_SHA256},
                {"scope", "actual private observer and native algorithms; direct component inputs, no transport"}}).ToJson() << '\n';
            return 0;
        }
        if (argc != 1) throw std::runtime_error("usage: geometricSamplingObservationCheck [--identity]");
        Require(G4RunManager::GetRunManager() == nullptr, "probe unexpectedly owns a run manager");
        NativeDelegation(); ClassificationContract(); EnergyRejectionContract();
        Require(G4RunManager::GetRunManager() == nullptr, "probe created a run manager");
        std::cout << Value(Value::Object{{"schema", "g4usim_h4_observation_contract_v1"}, {"checks", checks},
            {"passed", true}, {"transport_executed", false}, {"scientific_sample", false}}).ToJson() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "H4 observation component: " << error.what() << '\n';
        return 1;
    }
}
