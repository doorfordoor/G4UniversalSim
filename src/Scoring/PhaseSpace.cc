#include "Scoring/PhaseSpace.hh"

#include "Utils/StringUtils.hh"

#include "G4SystemOfUnits.hh"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace {

std::string Number(double value)
{
    std::ostringstream stream;
    stream << std::setprecision(15) << value;
    return stream.str();
}

double ParseNumber(const std::string& text, const std::string& where)
{
    try {
        std::size_t used = 0;
        const double value = std::stod(text, &used);
        if (used != text.size() || !std::isfinite(value)) throw std::invalid_argument(text);
        return value;
    } catch (const std::exception&) {
        throw std::runtime_error("PhaseSpace " + where + ": invalid number '" + text + "'");
    }
}

int ParseInt(const std::string& text, const std::string& where)
{
    const double value = ParseNumber(text, where);
    if (value != std::floor(value) || std::abs(value) > 2147483647.0) {
        throw std::runtime_error("PhaseSpace " + where + ": expected an integer, got '" + text + "'");
    }
    return static_cast<int>(value);
}

}  // namespace

namespace PhaseSpace {

const std::vector<std::string>& Header()
{
    static const std::vector<std::string> header = {
        "runID", "eventID", "trackID", "parentID", "particle", "pdg", "x_mm", "y_mm", "z_mm",
        "u", "v", "w", "kineticEnergy_MeV", "time_ns", "weight"};
    return header;
}

std::vector<std::string> Row(const PhaseSpaceParticle& p)
{
    return {std::to_string(p.runID), std::to_string(p.eventID), std::to_string(p.trackID),
            std::to_string(p.parentID), p.particle, std::to_string(p.pdg),
            Number(p.x / mm), Number(p.y / mm), Number(p.z / mm), Number(p.u), Number(p.v), Number(p.w),
            Number(p.kineticEnergy / MeV), Number(p.time / ns), Number(p.weight)};
}

std::vector<std::vector<PhaseSpaceParticle>> ReadHistories(const std::vector<std::string>& files,
    std::vector<input_provenance::InputFile>* acceptedInputs)
{
    std::vector<std::vector<PhaseSpaceParticle>> histories;
    std::vector<input_provenance::InputFile> inputs;
    if (files.empty()) throw std::runtime_error("PhaseSpace needs at least one file");
    for (const std::string& file : files) {
        auto fileInput = input_provenance::ReadFile(file);
        std::istringstream input(fileInput.bytes);
        // Retain accepted identity/hash, not another copy of all replay bytes.
        if (acceptedInputs) inputs.push_back({fileInput.path, {}, fileInput.sha256});
        std::string line;
        int lineNumber = 0;
        bool headerSeen = false;
        int lastRun = 0, lastEvent = 0;
        bool startNew = true;
        while (std::getline(input, line)) {
            ++lineNumber;
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (StringUtils::Trim(line).empty()) continue;
            std::vector<std::string> cells;
            for (const auto& cell : StringUtils::Split(line, ',')) cells.push_back(StringUtils::Trim(cell));
            const std::string where = "'" + file + "' line " + std::to_string(lineNumber);
            if (!headerSeen) {
                if (cells != Header()) {
                    throw std::runtime_error("PhaseSpace " + where + ": header must be phase_space_csv_v1 "
                                             "(runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,"
                                             "kineticEnergy_MeV,time_ns,weight)");
                }
                headerSeen = true;
                continue;
            }
            if (cells.size() != Header().size()) {
                throw std::runtime_error("PhaseSpace " + where + ": expected " + std::to_string(Header().size()) +
                                         " columns");
            }
            PhaseSpaceParticle p;
            p.runID = ParseInt(cells[0], where);
            p.eventID = ParseInt(cells[1], where);
            p.trackID = ParseInt(cells[2], where);
            p.parentID = ParseInt(cells[3], where);
            p.particle = cells[4];
            p.pdg = ParseInt(cells[5], where);
            p.x = ParseNumber(cells[6], where) * mm;
            p.y = ParseNumber(cells[7], where) * mm;
            p.z = ParseNumber(cells[8], where) * mm;
            p.u = ParseNumber(cells[9], where);
            p.v = ParseNumber(cells[10], where);
            p.w = ParseNumber(cells[11], where);
            p.kineticEnergy = ParseNumber(cells[12], where) * MeV;
            p.time = ParseNumber(cells[13], where) * ns;
            p.weight = ParseNumber(cells[14], where);
            const double norm = std::sqrt(p.u * p.u + p.v * p.v + p.w * p.w);
            if (std::abs(norm - 1.0) > 1e-6) {
                throw std::runtime_error("PhaseSpace " + where + ": direction (u,v,w) must be a unit vector");
            }
            if (p.kineticEnergy < 0.0 || !(p.weight > 0.0) || p.pdg == 0 || p.particle.empty()) {
                throw std::runtime_error("PhaseSpace " + where +
                                         ": needs kineticEnergy >= 0, weight > 0, a particle name and pdg != 0");
            }
            if (startNew || p.runID != lastRun || p.eventID != lastEvent) histories.emplace_back();
            histories.back().push_back(p);
            lastRun = p.runID;
            lastEvent = p.eventID;
            startNew = false;
        }
        if (!headerSeen) throw std::runtime_error("PhaseSpace '" + file + "' is empty (no header)");
    }
    if (histories.empty()) throw std::runtime_error("PhaseSpace files contain no particles");
    if (acceptedInputs) *acceptedInputs = std::move(inputs);
    return histories;
}

}  // namespace PhaseSpace
