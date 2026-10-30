#include "Scoring/NielTable.hh"
#include "Config/InputProvenance.hh"

#include "Utils/StringUtils.hh"
#include "G4SystemOfUnits.hh"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <sstream>
#include <stdexcept>

std::shared_ptr<const NielTable> NielTable::Load(const std::string& path)
{
    const auto acceptedInput = input_provenance::ReadFile(path, "niel_table", "displacement_table_parse");
    std::istringstream input(acceptedInput.bytes);
    auto table = std::make_shared<NielTable>();
    table->file_ = path;
    table->inputSha256_ = acceptedInput.sha256;
    std::string line;
    int lineNumber = 0;
    bool header = false;
    while (std::getline(input, line)) {
        ++lineNumber;
        if (lineNumber == 1 && line.size() >= 3 && line.compare(0, 3, "\xEF\xBB\xBF") == 0) line.erase(0, 3);
        const std::string text = StringUtils::Trim(line);
        if (text.empty() || text[0] == '#') continue;
        const auto fields = StringUtils::Split(text, ',');
        const std::string where = path + ":" + std::to_string(lineNumber);
        if (!header) {
            if (fields.size() != 2 || StringUtils::Trim(fields[0]) != "energy_MeV" ||
                StringUtils::Trim(fields[1]) != "niel_MeV_cm2_g") {
                throw std::runtime_error(where + ": NIEL table header must be 'energy_MeV,niel_MeV_cm2_g'");
            }
            header = true;
            continue;
        }
        if (fields.size() != 2) throw std::runtime_error(where + ": expected 2 columns");
        double energy = 0.0;
        double niel = 0.0;
        try {
            std::size_t used = 0;
            const std::string e = StringUtils::Trim(fields[0]);
            energy = std::stod(e, &used);
            if (used != e.size()) throw std::invalid_argument(e);
            const std::string n = StringUtils::Trim(fields[1]);
            niel = std::stod(n, &used);
            if (used != n.size()) throw std::invalid_argument(n);
        } catch (const std::exception&) {
            throw std::runtime_error(where + ": not a number");
        }
        if (!std::isfinite(energy) || !(energy > 0.0)) throw std::runtime_error(where + ": energy must be > 0");
        if (!std::isfinite(niel) || niel < 0.0) throw std::runtime_error(where + ": NIEL must be finite and >= 0");
        if (!table->energies_.empty() && !(energy * MeV > table->energies_.back())) {
            throw std::runtime_error(where + ": energies must be strictly increasing");
        }
        table->energies_.push_back(energy * MeV);
        table->values_.push_back(niel);
    }
    if (!header) throw std::runtime_error(path + ": NIEL table has no header 'energy_MeV,niel_MeV_cm2_g'");
    if (table->energies_.size() < 2) throw std::runtime_error(path + ": NIEL table needs at least 2 rows");
    return table;
}

bool NielTable::Evaluate(double energy, double& nielMeVcm2PerG) const
{
    if (!(energy >= energies_.front()) || !(energy <= energies_.back())) return false;
    auto upper = std::upper_bound(energies_.begin(), energies_.end(), energy);
    std::size_t i = upper == energies_.end() ? energies_.size() - 2
                                             : static_cast<std::size_t>(upper - energies_.begin()) - 1;
    const double e0 = energies_[i], e1 = energies_[i + 1];
    const double v0 = values_[i], v1 = values_[i + 1];
    if (v0 > 0.0 && v1 > 0.0) {
        const double t = std::log(energy / e0) / std::log(e1 / e0);
        nielMeVcm2PerG = std::exp(std::log(v0) + t * (std::log(v1) - std::log(v0)));
    } else {
        const double t = (energy - e0) / (e1 - e0);
        nielMeVcm2PerG = v0 + t * (v1 - v0);
    }
    return true;
}
