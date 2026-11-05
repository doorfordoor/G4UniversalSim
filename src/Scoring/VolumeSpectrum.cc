#include "Scoring/VolumeSpectrum.hh"

#include "Output/CsvWriter.hh"
#include "Output/OutputManager.hh"
#include "Scoring/NumericChecks.hh"

#include <cmath>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace {

std::string Number(double value)
{
    std::ostringstream stream;
    stream << std::setprecision(12) << value;
    return stream.str();
}

}  // namespace

void VolumeSpectrum::ValidateConfig(const VolumeSpectrumConfig& config)
{
    const std::string where = config.section.empty() ? std::string("spectrum")
                                                     : "[" + config.section + "]" +
                                                           (config.location.empty() ? "" : " at " + config.location);
    if (config.bins < 1) {
        throw std::runtime_error(where + " requires bins >= 1");
    }
    if (!std::isfinite(config.minMeV) || config.minMeV < 0.0) {
        throw std::runtime_error(where + " requires a finite non-negative min");
    }
    if (!std::isfinite(config.maxMeV) || !(config.maxMeV > config.minMeV)) {
        throw std::runtime_error(where + " requires a finite max greater than min");
    }
    const double width = (config.maxMeV - config.minMeV) / static_cast<double>(config.bins);
    if (!std::isfinite(width) || width <= 0.0) {
        throw std::runtime_error(where + " bin width (max - min) / bins is not a representable positive finite number");
    }
}

void VolumeSpectrum::Add(const std::string& volumePath, const std::string& volumeName,
                         double energyMeV, double alreadyWeightedAmount)
{
    if (!IsConfigured()) return;
    if (volumePath.empty()) {
        throw std::runtime_error("VolumeSpectrum requires a touchable path for volume '" + volumeName + "'");
    }
    if (!std::isfinite(energyMeV) || !std::isfinite(alreadyWeightedAmount)) {
        throw std::runtime_error("VolumeSpectrum rejects a nonfinite energy or weighted amount for volume '" +
                                 volumeName + "'");
    }
    auto& volume = volumes_[volumePath];
    if (volume.name.empty()) {
        volume.name = volumeName;
        volume.bins.assign(static_cast<std::size_t>(config_.bins), 0.0);
    } else if (volume.name != volumeName) {
        throw std::runtime_error("VolumeSpectrum detected changing volume name for touchable " + volumePath);
    }

    if (energyMeV < config_.minMeV) {
        volume.underflow = ScoringNumeric::Add(volume.underflow, alreadyWeightedAmount,
                                               "spectrum underflow accumulation");
        return;
    }
    if (energyMeV > config_.maxMeV) {
        volume.overflow = ScoringNumeric::Add(volume.overflow, alreadyWeightedAmount,
                                              "spectrum overflow accumulation");
        return;
    }
    const double width = (config_.maxMeV - config_.minMeV) / static_cast<double>(config_.bins);
    int bin = static_cast<int>(std::floor((energyMeV - config_.minMeV) / width));
    if (bin < 0) bin = 0;
    if (bin >= config_.bins) bin = config_.bins - 1;  // E == max closes the last bin
    volume.bins[static_cast<std::size_t>(bin)] =
        ScoringNumeric::Add(volume.bins[static_cast<std::size_t>(bin)], alreadyWeightedAmount,
                            "spectrum bin accumulation");
}

void VolumeSpectrum::Clear()
{
    volumes_.clear();
}

std::string VolumeSpectrum::Write(OutputManager& output, int runID, const std::string& scorer,
                                  const std::string& unit, long long events) const
{
    if (!IsConfigured()) return {};
    const std::string filename = output.MakeThreadFilename("spectrum_" + scorer + ".csv");
    const std::string path = output.MakeOutputPath(filename);
    CsvWriter writer(path);
    writer.WriteHeader({"runID", "scorer", "volume_path", "volume_name", "region", "bin",
                        "low_edge_MeV", "high_edge_MeV", "amount", "unit", "n_events"});
    const double width = (config_.maxMeV - config_.minMeV) / static_cast<double>(config_.bins);
    const std::string eventCount = std::to_string(events);
    for (const auto& item : volumes_) {
        const VolumeSpectrumData& volume = item.second;
        for (int bin = 0; bin < config_.bins; ++bin) {
            const double low = config_.minMeV + width * static_cast<double>(bin);
            const double high = bin + 1 == config_.bins ? config_.maxMeV : low + width;
            writer.WriteRow({std::to_string(runID), scorer, item.first, volume.name, "bin",
                             std::to_string(bin), Number(low), Number(high),
                             Number(volume.bins[static_cast<std::size_t>(bin)]), unit, eventCount});
        }
        writer.WriteRow({std::to_string(runID), scorer, item.first, volume.name, "underflow",
                         "-1", "", Number(config_.minMeV), Number(volume.underflow), unit, eventCount});
        writer.WriteRow({std::to_string(runID), scorer, item.first, volume.name, "overflow",
                         std::to_string(config_.bins), Number(config_.maxMeV), "",
                         Number(volume.overflow), unit, eventCount});
    }
    writer.Close();
    output.RegisterGeneratedFile(writer.GetFilename(), OutputManager::ArtifactScope::Thread,
                                 output.GetRunId(), output.GetThreadId());
    return writer.GetFilename();
}
