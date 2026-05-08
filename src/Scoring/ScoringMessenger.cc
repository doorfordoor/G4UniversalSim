#include "Scoring/ScoringMessenger.hh"

#include "Scoring/ScoringManager.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include "G4Exception.hh"
#include "G4UIcmdWithABool.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIcmdWithAnInteger.hh"
#include "G4UIcmdWithoutParameter.hh"
#include "G4UIdirectory.hh"

#include <cctype>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

ScoringManager* RequireManager(ScoringManager* manager, const std::string& command)
{
    if (!manager) {
        throw std::runtime_error("ScoringMessenger command '" + command + "' failed: ScoringManager is null");
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
    if (inQuotes) throw std::runtime_error("unclosed quote");
    if (!current.empty()) tokens.push_back(current);
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
        if (key.empty()) throw std::runtime_error("empty key in token '" + token + "'");
        values[key] = value;
    }
    return values;
}

std::string RequiredValue(const std::map<std::string, std::string>& values,
                          const std::string& key)
{
    const auto it = values.find(key);
    if (it == values.end() || StringUtils::Trim(it->second).empty()) {
        throw std::runtime_error("missing required key '" + key + "'");
    }
    return it->second;
}

struct HistogramArgs {
    int bins = 0;
    double min = 0.0;
    double max = 0.0;
};

HistogramArgs ParseHistogramArgs(const std::string& raw)
{
    if (StringUtils::Contains(raw, "=")) {
        const auto values = ParseKeyValueLine(raw);
        HistogramArgs args;
        args.bins = std::stoi(RequiredValue(values, "bins"));
        args.min = UnitParser::ParseEnergy(RequiredValue(values, "min"));
        args.max = UnitParser::ParseEnergy(RequiredValue(values, "max"));
        return args;
    }

    const auto tokens = SplitWhitespaceRespectQuotes(raw);
    if (tokens.size() < 3) {
        throw std::runtime_error("expected '<bins> <min energy> <max energy>' or key=value form");
    }

    HistogramArgs args;
    args.bins = std::stoi(tokens[0]);

    if (tokens.size() == 3) {
        args.min = UnitParser::ParseEnergy(tokens[1]);
        args.max = UnitParser::ParseEnergy(tokens[2]);
    } else if (tokens.size() == 5) {
        args.min = UnitParser::ParseEnergy(tokens[1] + " " + tokens[2]);
        args.max = UnitParser::ParseEnergy(tokens[3] + " " + tokens[4]);
    } else {
        std::string minText = tokens[1];
        std::string maxText;
        bool splitFound = false;
        for (std::size_t i = 2; i < tokens.size(); ++i) {
            if (!splitFound && !tokens[i].empty() && std::isdigit(static_cast<unsigned char>(tokens[i][0]))) {
                splitFound = true;
                maxText = tokens[i];
            } else if (splitFound) {
                maxText += " " + tokens[i];
            } else {
                minText += " " + tokens[i];
            }
        }
        if (!splitFound) {
            throw std::runtime_error("could not split min/max energy values");
        }
        args.min = UnitParser::ParseEnergy(minText);
        args.max = UnitParser::ParseEnergy(maxText);
    }
    return args;
}

void ReportFailure(const std::string& command, const std::string& raw, const std::exception& error)
{
    const auto message = "Scoring command " + command + " failed for input '" + raw + "': " + error.what();
    G4Exception("ScoringMessenger::SetNewValue", "AIHL_SCORING_001",
                FatalException, message.c_str());
}

} // namespace

ScoringMessenger::ScoringMessenger(ScoringManager* manager)
    : manager_(manager)
{
    scoringDir_ = new G4UIdirectory("/AIHL/scoring/");
    scoringDir_->SetGuidance("AIHL scoring configuration commands. Prefer before /run/initialize.");

    enableCmd_ = new G4UIcmdWithABool("/AIHL/scoring/enable", this);
    hitsCmd_ = new G4UIcmdWithABool("/AIHL/scoring/hits", this);
    eventEdepCmd_ = new G4UIcmdWithABool("/AIHL/scoring/eventEdep", this);
    edepCmd_ = new G4UIcmdWithABool("/AIHL/scoring/edep", this);
    letCmd_ = new G4UIcmdWithABool("/AIHL/scoring/let", this);
    doseCmd_ = new G4UIcmdWithABool("/AIHL/scoring/dose", this);
    fluenceCmd_ = new G4UIcmdWithABool("/AIHL/scoring/fluence", this);
    autoCreateScorersCmd_ = new G4UIcmdWithABool("/AIHL/scoring/autoCreateScorers", this);
    setEdepHistogramCmd_ = new G4UIcmdWithAString("/AIHL/scoring/setEdepHistogram", this);
    setWeightedEdepHistogramCmd_ = new G4UIcmdWithAString("/AIHL/scoring/setWeightedEdepHistogram", this);
    verboseCmd_ = new G4UIcmdWithAnInteger("/AIHL/scoring/verbose", this);
    printCmd_ = new G4UIcmdWithoutParameter("/AIHL/scoring/print", this);

    enableCmd_->SetGuidance("Enable or disable all scoring.");
    hitsCmd_->SetGuidance("Enable or disable hit output.");
    eventEdepCmd_->SetGuidance("Enable or disable event edep output.");
    edepCmd_->SetGuidance("Enable or disable EdepScorer.");
    letCmd_->SetGuidance("Enable or disable LETScorer stub.");
    doseCmd_->SetGuidance("Enable or disable DoseScorer stub.");
    fluenceCmd_->SetGuidance("Enable or disable FluenceScorer stub.");
    autoCreateScorersCmd_->SetGuidance("Enable automatic default scorer creation.");
    setEdepHistogramCmd_->SetGuidance("Configure raw event edep histogram: bins=200 min=0 eV max=10 MeV.");
    setWeightedEdepHistogramCmd_->SetGuidance("Configure weighted event edep histogram.");
    verboseCmd_->SetGuidance("Set scoring verbose level.");
    printCmd_->SetGuidance("Print scoring summary.");
}

ScoringMessenger::~ScoringMessenger()
{
    delete printCmd_;
    delete verboseCmd_;
    delete setWeightedEdepHistogramCmd_;
    delete setEdepHistogramCmd_;
    delete autoCreateScorersCmd_;
    delete fluenceCmd_;
    delete doseCmd_;
    delete letCmd_;
    delete edepCmd_;
    delete eventEdepCmd_;
    delete hitsCmd_;
    delete enableCmd_;
    delete scoringDir_;
}

void ScoringMessenger::SetNewValue(G4UIcommand* command, G4String newValue)
{
    const std::string raw = newValue;
    const std::string commandPath = command ? command->GetCommandPath() : "<unknown>";
    try {
        auto* manager = RequireManager(manager_, commandPath);
        if (command == enableCmd_) {
            manager->Enable(enableCmd_->GetNewBoolValue(newValue));
        } else if (command == hitsCmd_) {
            manager->EnableHitOutput(hitsCmd_->GetNewBoolValue(newValue));
        } else if (command == eventEdepCmd_) {
            manager->EnableEventEdepOutput(eventEdepCmd_->GetNewBoolValue(newValue));
        } else if (command == edepCmd_) {
            manager->EnableEdepScoring(edepCmd_->GetNewBoolValue(newValue));
        } else if (command == letCmd_) {
            manager->EnableLETScoring(letCmd_->GetNewBoolValue(newValue));
        } else if (command == doseCmd_) {
            manager->EnableDoseScoring(doseCmd_->GetNewBoolValue(newValue));
        } else if (command == fluenceCmd_) {
            manager->EnableFluenceScoring(fluenceCmd_->GetNewBoolValue(newValue));
        } else if (command == autoCreateScorersCmd_) {
            manager->SetAutoCreateDefaultScorers(autoCreateScorersCmd_->GetNewBoolValue(newValue));
        } else if (command == setEdepHistogramCmd_) {
            const auto args = ParseHistogramArgs(raw);
            manager->ConfigureEdepHistogram(args.bins, args.min, args.max);
        } else if (command == setWeightedEdepHistogramCmd_) {
            const auto args = ParseHistogramArgs(raw);
            manager->ConfigureWeightedEdepHistogram(args.bins, args.min, args.max);
        } else if (command == verboseCmd_) {
            manager->SetVerboseLevel(verboseCmd_->GetNewIntValue(newValue));
        } else if (command == printCmd_) {
            manager->PrintSummary();
        }
    } catch (const std::exception& error) {
        ReportFailure(commandPath, raw, error);
    }
}
