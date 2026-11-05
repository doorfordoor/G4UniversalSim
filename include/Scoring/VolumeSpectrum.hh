#ifndef G4USIM_SCORING_VOLUME_SPECTRUM_HH
#define G4USIM_SCORING_VOLUME_SPECTRUM_HH

// Roadmap H2-2: per-volume kinetic-energy spectrum of an already weighted
// scorer amount (dose Gy, fluence mm^-2 or displacement MeV/g).  The spectrum
// receives the same pre-step kinetic energy as the filter and the already
// weighted amount the scorer would otherwise accumulate; it never applies the
// weight again.  Bins are half-open [low, high) except the last bin, which is
// closed at max: E == max falls into bin bins-1 and not into overflow.
//
// The shared Histogram1D keeps its historical value >= max overflow convention
// and is not modified: bin edges are handled locally here.

#include "Output/OutputRecord.hh"

#include <map>
#include <string>
#include <utility>
#include <vector>

class OutputManager;

struct VolumeSpectrumConfig {
    int bins = 0;
    double minMeV = 0.0;
    double maxMeV = 0.0;
    std::string section;    // e.g. "scoring.spectrum.dose"
    std::string location;   // "file:line" of the declared section
};

struct VolumeSpectrumData {
    std::string name;
    std::vector<double> bins;
    double underflow = 0.0;
    double overflow = 0.0;
};

class VolumeSpectrum {
  public:
    VolumeSpectrum() = default;
    explicit VolumeSpectrum(VolumeSpectrumConfig config)
        : config_(std::move(config)), configured_(true)
    {
        ValidateConfig(config_);
    }

    // A configured spectrum must have at least one bin, a finite non-negative min,
    // a finite max above min, and a representable positive (max - min) / bins width.
    // A subnormal or zero width would turn the bin index into an undefined cast and
    // silently misplace every scored step.
    static void ValidateConfig(const VolumeSpectrumConfig& config);

    bool IsConfigured() const { return configured_; }
    const VolumeSpectrumConfig& Config() const { return config_; }

    // alreadyWeightedAmount is the weighted scorer amount for one scored step
    // (dose: w*edep/mass in Gy, fluence: w*length/volume in mm^-2,
    // displacement: w*length*NIEL*100/volume in MeV/g).  It is not multiplied by
    // any weight here.
    void Add(const std::string& volumePath, const std::string& volumeName,
             double energyMeV, double alreadyWeightedAmount);
    void Clear();

    // Writes spectrum_<scorer>[_tN].csv when configured; returns the filename or
    // an empty string.  events is the number of completed events of the thread.
    std::string Write(OutputManager& output, int runID, const std::string& scorer,
                      const std::string& unit, long long events) const;

  private:
    VolumeSpectrumConfig config_;
    bool configured_ = false;
    std::map<std::string, VolumeSpectrumData> volumes_;
};

#endif  // G4USIM_SCORING_VOLUME_SPECTRUM_HH
