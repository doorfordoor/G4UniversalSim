#include "Source/SourceMessenger.hh"

#include "Source/SourceManager.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4Exception.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIcmdWithoutParameter.hh"
#include "G4UIdirectory.hh"
#include "G4ios.hh"

#include <cctype>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

[[noreturn]] void ThrowCommandError(const std::string& command,
                                    const std::string& value,
                                    const std::string& reason)
{
    throw std::runtime_error("SourceMessenger command '" + command +
                             "' failed for input '" + value + "': " + reason);
}

SourceManager* RequireManager(SourceManager* manager, const std::string& command)
{
    if (!manager) {
        throw std::runtime_error("SourceMessenger command '" + command +
                                 "' failed: SourceManager is null");
    }
    return manager;
}

std::vector<std::string> SplitWhitespaceRespectQuotes(const std::string& text)
{
    std::vector<std::string> tokens;
    std::string current;
    bool inQuotes = false;

    for (char ch : text) {
        if (ch == '"') {
            inQuotes = !inQuotes;
            continue;
        }
        if (std::isspace(static_cast<unsigned char>(ch)) && !inQuotes) {
            if (!current.empty()) {
                tokens.push_back(current);
                current.clear();
            }
        } else {
            current.push_back(ch);
        }
    }

    if (inQuotes) {
        throw std::runtime_error("unclosed quote");
    }
    if (!current.empty()) {
        tokens.push_back(current);
    }
    return tokens;
}

std::map<std::string, std::string> ParseKeyValueLine(const std::string& line)
{
    std::map<std::string, std::string> values;
    for (const auto& token : SplitWhitespaceRespectQuotes(line)) {
        const auto pos = token.find('=');
        if (pos == std::string::npos || pos == 0) {
            throw std::runtime_error("expected key=value token, got '" + token + "'");
        }
        auto key = StringUtils::ToLower(StringUtils::Trim(token.substr(0, pos)));
        auto value = StringUtils::Trim(token.substr(pos + 1));
        if (key.empty()) {
            throw std::runtime_error("empty key in token '" + token + "'");
        }
        values[key] = value;
    }
    return values;
}

std::string GetRequired(const std::map<std::string, std::string>& values,
                        const std::string& key,
                        const std::string& command,
                        const std::string& raw)
{
    const auto iter = values.find(key);
    if (iter == values.end() || StringUtils::Trim(iter->second).empty()) {
        ThrowCommandError(command, raw, "missing required key '" + key + "'");
    }
    return iter->second;
}

std::string GetOptional(const std::map<std::string, std::string>& values,
                        const std::string& key,
                        const std::string& defaultValue)
{
    const auto iter = values.find(key);
    if (iter == values.end()) {
        return defaultValue;
    }
    return iter->second;
}

std::vector<double> ParseLengthVec3(const std::string& text)
{
    const auto trimmed = StringUtils::Trim(text);
    if (trimmed.empty()) {
        throw std::runtime_error("empty vector");
    }

    if (StringUtils::Contains(trimmed, ",")) {
        auto values = UnitParser::ParseVectorWithUnit(trimmed);
        if (values.size() != 3) {
            throw std::runtime_error("expected 3 vector components");
        }
        return values;
    }

    const auto tokens = SplitWhitespaceRespectQuotes(trimmed);
    std::vector<double> values;
    if (tokens.size() == 3) {
        for (const auto& token : tokens) {
            values.push_back(UnitParser::ParseLength(token));
        }
    } else if (tokens.size() == 4) {
        values.push_back(UnitParser::ParseLength(tokens[0] + " " + tokens[3]));
        values.push_back(UnitParser::ParseLength(tokens[1] + " " + tokens[3]));
        values.push_back(UnitParser::ParseLength(tokens[2] + " " + tokens[3]));
    } else if (tokens.size() == 6) {
        values.push_back(UnitParser::ParseLength(tokens[0] + " " + tokens[1]));
        values.push_back(UnitParser::ParseLength(tokens[2] + " " + tokens[3]));
        values.push_back(UnitParser::ParseLength(tokens[4] + " " + tokens[5]));
    } else {
        throw std::runtime_error("expected 'x y z unit', 'x unit y unit z unit', or comma-separated vector");
    }
    return values;
}

std::vector<double> ParseDirectionVec3(const std::string& text)
{
    auto parts = StringUtils::Contains(text, ",")
                     ? StringUtils::Split(text, ',')
                     : SplitWhitespaceRespectQuotes(text);
    if (parts.size() != 3) {
        throw std::runtime_error("direction requires 3 numeric components");
    }

    std::vector<double> values;
    values.reserve(3);
    for (const auto& part : parts) {
        const auto trimmed = StringUtils::Trim(part);
        try {
            size_t consumed = 0;
            const auto value = std::stod(trimmed, &consumed);
            if (consumed != trimmed.size()) {
                throw std::runtime_error("trailing characters");
            }
            values.push_back(value);
        } catch (const std::exception&) {
            throw std::runtime_error("invalid direction component '" + trimmed + "'");
        }
    }
    return values;
}

void ReportCommandFailure(const std::string& command,
                          const std::string& raw,
                          const std::exception& error)
{
    const auto message = "Source command " + command + " failed for input '" +
                         raw + "': " + error.what();
    G4Exception("SourceMessenger::SetNewValue", "AIHL_SOURCE_001",
                FatalException, message.c_str());
}

} // namespace

SourceMessenger::SourceMessenger(SourceManager* manager)
    : manager_(manager)
{
    sourceDir_ = new G4UIdirectory("/AIHL/source/");
    sourceDir_->SetGuidance("AIHL source control commands. Native /gps/... commands remain available.");

    presetCmd_ = new G4UIcmdWithAString("/AIHL/source/preset", this);
    presetCmd_->SetGuidance("Apply a lightweight source preset.");

    particleCmd_ = new G4UIcmdWithAString("/AIHL/source/particle", this);
    particleCmd_->SetGuidance("Set GPS particle name.");

    energyCmd_ = new G4UIcmdWithAString("/AIHL/source/energy", this);
    energyCmd_->SetGuidance("Set mono energy, for example: 10 MeV.");

    pointCmd_ = new G4UIcmdWithAString("/AIHL/source/point", this);
    pointCmd_->SetGuidance("Set point position, for example: 0 0 -1 mm or 0 mm,0 mm,-1 mm.");

    directionCmd_ = new G4UIcmdWithAString("/AIHL/source/direction", this);
    directionCmd_->SetGuidance("Set beam direction, for example: 0 0 1.");

    isotropicCmd_ = new G4UIcmdWithoutParameter("/AIHL/source/isotropic", this);
    isotropicCmd_->SetGuidance("Set isotropic angular distribution.");

    planeBeamCmd_ = new G4UIcmdWithAString("/AIHL/source/planeBeam", this);
    planeBeamCmd_->SetGuidance("Set plane circular beam: radius=1 mm z=-1 mm direction=+z.");

    printCmd_ = new G4UIcmdWithoutParameter("/AIHL/source/print", this);
    printCmd_->SetGuidance("Print current source summary.");

    resetCmd_ = new G4UIcmdWithoutParameter("/AIHL/source/reset", this);
    resetCmd_->SetGuidance("Reset lazy GPS and cached source configuration.");
}

SourceMessenger::~SourceMessenger()
{
    delete resetCmd_;
    delete printCmd_;
    delete planeBeamCmd_;
    delete isotropicCmd_;
    delete directionCmd_;
    delete pointCmd_;
    delete energyCmd_;
    delete particleCmd_;
    delete presetCmd_;
    delete sourceDir_;
}

void SourceMessenger::SetNewValue(G4UIcommand* command, G4String newValue)
{
    const std::string raw = newValue;

    try {
        if (command == presetCmd_) {
            RequireManager(manager_, "/AIHL/source/preset")->ApplyPreset(raw);
        } else if (command == particleCmd_) {
            RequireManager(manager_, "/AIHL/source/particle")->SetParticle(raw);
        } else if (command == energyCmd_) {
            RequireManager(manager_, "/AIHL/source/energy")
                ->SetMonoEnergy(UnitParser::ParseEnergy(raw));
        } else if (command == pointCmd_) {
            const auto pos = ParseLengthVec3(raw);
            RequireManager(manager_, "/AIHL/source/point")
                ->SetPointPosition(pos[0], pos[1], pos[2]);
        } else if (command == directionCmd_) {
            const auto dir = ParseDirectionVec3(raw);
            RequireManager(manager_, "/AIHL/source/direction")
                ->SetDirection(dir[0], dir[1], dir[2]);
        } else if (command == isotropicCmd_) {
            RequireManager(manager_, "/AIHL/source/isotropic")->SetIsotropic();
        } else if (command == planeBeamCmd_) {
            double radius = 0.0;
            double z = 0.0;
            std::string direction = "+z";

            if (StringUtils::Contains(raw, "=")) {
                const auto values = ParseKeyValueLine(raw);
                radius = UnitParser::ParseLength(
                    GetRequired(values, "radius", "/AIHL/source/planeBeam", raw));
                z = UnitParser::ParseLength(
                    GetRequired(values, "z", "/AIHL/source/planeBeam", raw));
                direction = GetOptional(values, "direction", "+z");
            } else {
                const auto tokens = SplitWhitespaceRespectQuotes(raw);
                if (tokens.size() == 3) {
                    radius = UnitParser::ParseLength(tokens[0]);
                    z = UnitParser::ParseLength(tokens[1]);
                    direction = tokens[2];
                } else if (tokens.size() == 5) {
                    radius = UnitParser::ParseLength(tokens[0] + " " + tokens[1]);
                    z = UnitParser::ParseLength(tokens[2] + " " + tokens[3]);
                    direction = tokens[4];
                } else {
                    ThrowCommandError("/AIHL/source/planeBeam", raw,
                                      "expected key=value form or '<radius> <z> <direction>'");
                }
            }

            RequireManager(manager_, "/AIHL/source/planeBeam")
                ->SetPlaneBeam(radius, z, direction);
        } else if (command == printCmd_) {
            RequireManager(manager_, "/AIHL/source/print")->PrintSummary();
        } else if (command == resetCmd_) {
            RequireManager(manager_, "/AIHL/source/reset")->ResetGPS();
        }
    } catch (const std::exception& error) {
        ReportCommandFailure(command ? command->GetCommandPath() : "<unknown>",
                             raw, error);
    }
}
