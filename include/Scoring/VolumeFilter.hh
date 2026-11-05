#ifndef G4USIM_SCORING_VOLUME_FILTER_HH
#define G4USIM_SCORING_VOLUME_FILTER_HH

// Roadmap H2-2: per-volume particle / kinetic-energy filter shared by the
// dose, fluence, LET and displacement scorers.  The filter is evaluated once
// per scored step, after each scorer's existing physical guards and before any
// accumulation.  Kinetic energy is the pre-step energy (HitRecord::kineticEnergy),
// i.e. the same quantity as hits_t0.csv kineticEnergy_MeV.  The energy window is
// half-open [energy_min, energy_max): a step with E == energy_max is rejected so
// that disjoint partition components are mutually exclusive.

#include "Output/OutputRecord.hh"

#include <cmath>
#include <limits>
#include <set>
#include <stdexcept>
#include <string>

struct VolumeFilterConfig {
    bool allParticles = false;              // [scoring.filter.*] particles = all
    std::set<std::string> particles;        // empty with allParticles == false: no particle condition
    double energyMinMeV = 0.0;              // inclusive
    double energyMaxMeV = std::numeric_limits<double>::infinity();  // exclusive
    std::string section;                    // e.g. "scoring.filter.dose"
    std::string location;                   // "file:line" of the declared section

    bool HasParticleCondition() const { return allParticles || !particles.empty(); }
};

class VolumeFilter {
  public:
    VolumeFilter() = default;
    explicit VolumeFilter(VolumeFilterConfig config)
        : config_(std::move(config)), configured_(true)
    {
    }

    bool IsConfigured() const { return configured_; }
    const VolumeFilterConfig& Config() const { return config_; }

    bool Matches(const HitRecord& hit) const
    {
        if (!configured_) return true;
        // The sampled kinetic energy feeds the energy window and the spectrum.  A
        // non-finite value is an internal error, not a legitimate rejection: surface
        // it before the particle condition so a mismatch cannot hide the failure.
        if (!std::isfinite(hit.kineticEnergy)) {
            throw std::runtime_error("VolumeFilter rejects a nonfinite sampled kinetic energy for volume '" +
                                     hit.volumeName + "'");
        }
        if (config_.allParticles) {
            // "all" means no particle condition; energy window still applies.
        } else if (!config_.particles.empty() && config_.particles.count(hit.particleName) == 0) {
            return false;
        }
        const double energy = hit.kineticEnergy;
        if (!(energy >= config_.energyMinMeV)) return false;
        if (!(energy < config_.energyMaxMeV)) return false;
        return true;
    }

  private:
    VolumeFilterConfig config_;
    bool configured_ = false;
};

#endif  // G4USIM_SCORING_VOLUME_FILTER_HH
