#include "Scoring/PhaseSpace.hh"

#include "Utils/StringUtils.hh"

#include "G4SystemOfUnits.hh"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <algorithm>
#include <sstream>
#include <stdexcept>

namespace {

std::string Number(double value)
{
    std::ostringstream stream;
    stream << std::setprecision(std::numeric_limits<double>::max_digits10) << value;
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

void ValidateDynamicState(const PhaseSpaceDynamicState& s, const std::string& where)
{
    const auto bad=[&](const char* text){throw std::runtime_error("PhaseSpace " + where + ": " + text);};
    if (!std::isfinite(s.mass) || s.mass<0 || !std::isfinite(s.magneticMoment)) bad("invalid dynamic mass/magnetic moment");
    double norm=0;
    for (double v:s.polarization) {if(!std::isfinite(v))bad("invalid polarization");norm+=v*v;}
    if (!std::isfinite(norm) || norm>1.+1e-12)bad("invalid polarization magnitude");
    if(s.electronOccupancy) {
        if(s.electronOccupancy->empty() || s.electronOccupancy->size()>20)bad("unsupported electron_occupancy size");
        long long total=0;
        for(int n:*s.electronOccupancy){if(n<0)bad("negative electron_occupancy");total+=n;}
        if(total>2147483647LL)bad("electron_occupancy total overflow");
    }
}

const std::vector<std::string>& Header()
{
    static const std::vector<std::string> header = {
        "runID", "eventID", "trackID", "parentID", "particle", "pdg", "x_mm", "y_mm", "z_mm",
        "u", "v", "w", "kineticEnergy_MeV", "time_ns", "weight", "charge_eplus", "dynamic_mass_MeV", "electron_occupancy",
        "magnetic_moment_MeV_per_T", "polarization_x", "polarization_y", "polarization_z"};
    return header;
}

std::vector<std::string> Row(const PhaseSpaceParticle& p)
{
    if (!p.charge || !std::isfinite(*p.charge)) {
        throw std::runtime_error("PhaseSpace v3 requires finite actual boundary charge");
    }
    if (!p.dynamicState) throw std::runtime_error("PhaseSpace v3 requires actual dynamic state");
    ValidateDynamicState(*p.dynamicState, "writer");
    const auto& state = *p.dynamicState;
    std::string occupancy = "none";
    if (state.electronOccupancy) {
        occupancy = "[";
        for (std::size_t i=0;i<state.electronOccupancy->size();++i) {
            if (i) occupancy += ";";
            occupancy += std::to_string(state.electronOccupancy->at(i));
        }
        occupancy += "]";
    }
    return {std::to_string(p.runID), std::to_string(p.eventID), std::to_string(p.trackID),
            std::to_string(p.parentID), p.particle, std::to_string(p.pdg),
            Number(p.x / mm), Number(p.y / mm), Number(p.z / mm), Number(p.u), Number(p.v), Number(p.w),
            Number(p.kineticEnergy / MeV), Number(p.time / ns), Number(p.weight), Number(*p.charge / eplus), Number(state.mass / MeV), occupancy,
            Number(state.magneticMoment / (MeV/tesla)), Number(state.polarization[0]),
            Number(state.polarization[1]), Number(state.polarization[2])};
}

std::vector<std::vector<PhaseSpaceParticle>> ReadHistories(const std::vector<std::string>& files,
    std::vector<input_provenance::InputFile>* acceptedInputs)
{
    std::vector<std::vector<PhaseSpaceParticle>> histories;
    std::vector<input_provenance::InputFile> inputs;
    if (files.empty()) throw std::runtime_error("PhaseSpace needs at least one file");
    const std::vector<std::string> legacyHeader(Header().begin(), Header().begin() + 15);
    const std::vector<std::string> v2Header(Header().begin(), Header().begin() + 16);
    for (std::size_t fileIndex = 0; fileIndex < files.size(); ++fileIndex) {
        const std::string& file = files[fileIndex];
        auto fileInput = input_provenance::ReadFile(file, "phase_space", "source_histories_parse");
        std::istringstream input(fileInput.bytes);
        // Retain accepted identity/hash, not another copy of all replay bytes.
        if (acceptedInputs) inputs.push_back({fileInput.path, {}, fileInput.sha256});
        std::string line;
        int lineNumber = 0;
        bool headerSeen = false;
        bool hasCharge = false;
        bool hasState = false;
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
                if (cells != Header() && cells != legacyHeader && cells != v2Header) {
                    throw std::runtime_error("PhaseSpace " + where + ": header must be phase_space_csv_v3 (22 canonical columns), v2 "
                                             "(runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,"
                                             "kineticEnergy_MeV,time_ns,weight,charge_eplus), or legacy v1 without charge_eplus");
                }
                hasState = cells == Header();
                hasCharge = hasState || cells == v2Header;
                headerSeen = true;
                continue;
            }
            const auto expectedColumns = hasState ? Header().size() : (hasCharge ? v2Header.size() : legacyHeader.size());
            if (cells.size() != expectedColumns) {
                throw std::runtime_error("PhaseSpace " + where + ": expected " + std::to_string(expectedColumns) +
                                         " columns");
            }
            PhaseSpaceParticle p;
            p.inputFileIndex = fileIndex;
            p.inputLine = lineNumber;
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
            if (hasCharge) p.charge = ParseNumber(cells[15], where) * eplus;
            if (hasState) {
                PhaseSpaceDynamicState state;
                state.mass = ParseNumber(cells[16], where) * MeV;
                if (cells[17] != "none") {
                    const auto& value=cells[17];
                    if (value.size()<3 || value.front()!='[' || value.back()!=']')
                        throw std::runtime_error("PhaseSpace " + where + ": invalid electron_occupancy");
                    state.electronOccupancy.emplace();
                    std::string body=value.substr(1,value.size()-2);
                    std::size_t begin=0;
                    do {
                        const auto end=body.find(';',begin);
                        const auto token=body.substr(begin,end==std::string::npos?end:end-begin);
                        if (token.empty() || token.find_first_not_of("0123456789")!=std::string::npos)
                            throw std::runtime_error("PhaseSpace " + where + ": invalid electron_occupancy integer");
                        state.electronOccupancy->push_back(ParseInt(token,where));
                        if (end==std::string::npos) break;
                        begin=end+1;
                    } while(true);
                }
                state.magneticMoment=ParseNumber(cells[18],where)*(MeV/tesla);
                for(int i=0;i<3;++i)state.polarization[i]=ParseNumber(cells[19+i],where);
                ValidateDynamicState(state,where);p.dynamicState=std::move(state);
            }
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
