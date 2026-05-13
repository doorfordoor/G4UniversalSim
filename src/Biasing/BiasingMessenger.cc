#include "Biasing/BiasingMessenger.hh"

#include "Biasing/BiasingManager.hh"
#include "Utils/StringUtils.hh"

#include "G4Exception.hh"
#include "G4UIcmdWithABool.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIcmdWithoutParameter.hh"
#include "G4UIcommand.hh"
#include "G4UIdirectory.hh"
#include "G4ios.hh"

#include <cctype>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace {

std::vector<std::string> SplitArgs(const std::string& line)
{
    std::vector<std::string> args;
    std::string current;
    bool inQuote = false;

    for (char c : line) {
        if (c == '"') {
            inQuote = !inQuote;
            continue;
        }
        if (!inQuote && std::isspace(static_cast<unsigned char>(c))) {
            if (!current.empty()) {
                args.push_back(current);
                current.clear();
            }
            continue;
        }
        current.push_back(c);
    }
    if (inQuote) {
        throw std::runtime_error("unterminated quote in command arguments: '" + line + "'");
    }
    if (!current.empty()) args.push_back(current);
    return args;
}

[[noreturn]] void ThrowCommandError(const std::string& commandName,
                                    const std::string& raw,
                                    const std::string& reason)
{
    G4ExceptionDescription desc;
    desc << commandName << " failed: " << reason << "; input='" << raw << "'";
    G4Exception(commandName.c_str(), "AIHLBiasingMessenger001", FatalException, desc);
    throw std::runtime_error(commandName + " failed: " + reason + "; input='" + raw + "'");
}

double ParseDoubleArg(const std::string& commandName,
                      const std::string& raw,
                      const std::string& value,
                      const std::string& label)
{
    try {
        std::size_t consumed = 0;
        const double parsed = std::stod(value, &consumed);
        if (consumed != value.size()) {
            ThrowCommandError(commandName, raw, "invalid numeric " + label + "='" + value + "'");
        }
        return parsed;
    } catch (const std::exception&) {
        ThrowCommandError(commandName, raw, "invalid numeric " + label + "='" + value + "'");
    }
}

int ParseIntArg(const std::string& commandName,
                const std::string& raw,
                const std::string& value,
                const std::string& label)
{
    try {
        std::size_t consumed = 0;
        const int parsed = std::stoi(value, &consumed);
        if (consumed != value.size()) {
            ThrowCommandError(commandName, raw, "invalid integer " + label + "='" + value + "'");
        }
        return parsed;
    } catch (const std::exception&) {
        ThrowCommandError(commandName, raw, "invalid integer " + label + "='" + value + "'");
    }
}

bool ParseBoolArg(const std::string& commandName,
                  const std::string& raw,
                  const std::string& value,
                  const std::string& label)
{
    try {
        return StringUtils::ToBool(value);
    } catch (const std::exception&) {
        ThrowCommandError(commandName, raw, "invalid bool " + label + "='" + value + "'");
    }
}

} // namespace

BiasingMessenger::BiasingMessenger(BiasingManager* manager)
    : manager_(manager)
{
    biasingDir_ = new G4UIdirectory("/AIHL/biasing/");
    biasingDir_->SetGuidance("AIHL biasing configuration commands.");

    xsDir_ = new G4UIdirectory("/AIHL/biasing/xs/");
    xsDir_->SetGuidance("AIHL cross-section biasing commands.");

    enableCmd_ = new G4UIcmdWithABool("/AIHL/biasing/enable", this);
    enableCmd_->SetGuidance("Enable or disable biasing.");

    addParticleCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/addParticle", this);
    addParticleCmd_->SetGuidance("Add or create a cross-section bias rule for a particle.");

    addProcessCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/addProcess", this);
    addProcessCmd_->SetGuidance("Add a process to the only existing XS rule.");

    addProcessForParticleCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/addProcessForParticle", this);
    addProcessForParticleCmd_->SetGuidance("Add process for particle: <particle> <process>.");

    addRuleCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/addRule", this);
    addRuleCmd_->SetGuidance("Create or get process-level XS rule: <particle> <process>.");

    setFactorCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/setFactor", this);
    setFactorCmd_->SetGuidance("Set XS bias factor. Legacy: <particle> <factor>. Process-level: <particle> <process> <factor>.");

    setRuleFactorCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/setRuleFactor", this);
    setRuleFactorCmd_->SetGuidance("Set process-level XS bias factor: <particle> <process> <factor>.");

    onlyPrimaryCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/onlyPrimary", this);
    onlyPrimaryCmd_->SetGuidance("Set only-primary flag. Legacy: <particle> <true|false>. Process-level: <particle> <process> <true|false>.");

    setRuleOnlyPrimaryCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/setRuleOnlyPrimary", this);
    setRuleOnlyPrimaryCmd_->SetGuidance("Set process-level only-primary flag: <particle> <process> <true|false>.");

    applyToSecondariesCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/applyToSecondaries", this);
    applyToSecondariesCmd_->SetGuidance("Set secondary flag. Legacy: <particle> <true|false>. Process-level: <particle> <process> <true|false>.");

    setRuleApplyToSecondariesCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/setRuleApplyToSecondaries", this);
    setRuleApplyToSecondariesCmd_->SetGuidance("Set process-level secondary flag: <particle> <process> <true|false>.");

    setMinWeightCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/setMinWeight", this);
    setMinWeightCmd_->SetGuidance("Set minimum track weight. Legacy: <particle> <value>. Process-level: <particle> <process> <value>.");

    setRuleMinWeightCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/setRuleMinWeight", this);
    setRuleMinWeightCmd_->SetGuidance("Set process-level minimum track weight: <particle> <process> <value>.");

    setMaxInteractionsCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/setMaxInteractions", this);
    setMaxInteractionsCmd_->SetGuidance("Set max biased interactions. Legacy: <particle> <n>. Process-level: <particle> <process> <n>.");

    setRuleMaxInteractionsCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/setRuleMaxInteractions", this);
    setRuleMaxInteractionsCmd_->SetGuidance("Set process-level max biased interactions: <particle> <process> <n>.");

    addVolumeCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/addVolume", this);
    addVolumeCmd_->SetGuidance("Add bias volume. Legacy/global: <volume>. Process-level: <particle> <process> <volume>.");

    addRuleVolumeCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/addRuleVolume", this);
    addRuleVolumeCmd_->SetGuidance("Add process-level target volume: <particle> <process> <volume>.");

    addVolumeForParticleCmd_ = new G4UIcmdWithAString("/AIHL/biasing/xs/addVolumeForParticle", this);
    addVolumeForParticleCmd_->SetGuidance("Add target volume for particle: <particle> <volume>.");

    validateCmd_ = new G4UIcmdWithoutParameter("/AIHL/biasing/validate", this);
    validateCmd_->SetGuidance("Validate current biasing configuration.");

    printRulesCmd_ = new G4UIcmdWithoutParameter("/AIHL/biasing/xs/printRules", this);
    printRulesCmd_->SetGuidance("Print process-level and legacy XS bias rules.");

    printCmd_ = new G4UIcmdWithoutParameter("/AIHL/biasing/print", this);
    printCmd_->SetGuidance("Print current biasing configuration.");

    clearCmd_ = new G4UIcmdWithoutParameter("/AIHL/biasing/clear", this);
    clearCmd_->SetGuidance("Clear current biasing configuration.");
}

BiasingMessenger::~BiasingMessenger()
{
    delete clearCmd_;
    delete printCmd_;
    delete printRulesCmd_;
    delete validateCmd_;
    delete addVolumeForParticleCmd_;
    delete addRuleVolumeCmd_;
    delete addVolumeCmd_;
    delete setRuleMaxInteractionsCmd_;
    delete setMaxInteractionsCmd_;
    delete setRuleMinWeightCmd_;
    delete setMinWeightCmd_;
    delete setRuleApplyToSecondariesCmd_;
    delete applyToSecondariesCmd_;
    delete setRuleOnlyPrimaryCmd_;
    delete onlyPrimaryCmd_;
    delete setRuleFactorCmd_;
    delete setFactorCmd_;
    delete addRuleCmd_;
    delete addProcessForParticleCmd_;
    delete addProcessCmd_;
    delete addParticleCmd_;
    delete enableCmd_;
    delete xsDir_;
    delete biasingDir_;
}

void BiasingMessenger::SetNewValue(G4UIcommand* command, G4String newValue)
{
    const std::string raw = std::string(newValue);
    try {
        if (command == enableCmd_) {
            EnsureManager("/AIHL/biasing/enable");
            manager_->Enable(enableCmd_->GetNewBoolValue(newValue));
            NotifyChanged();
            return;
        }
        if (command == addParticleCmd_) {
            EnsureManager("/AIHL/biasing/xs/addParticle");
            manager_->AddXSBiasParticle(raw);
            NotifyChanged();
            return;
        }
        if (command == addProcessCmd_) {
            EnsureManager("/AIHL/biasing/xs/addProcess");
            manager_->AddXSBiasProcess(raw);
            NotifyChanged();
            return;
        }
        if (command == addProcessForParticleCmd_) {
            EnsureManager("/AIHL/biasing/xs/addProcessForParticle");
            const auto args = SplitArgs(raw);
            if (args.size() != 2) ThrowCommandError("/AIHL/biasing/xs/addProcessForParticle", raw, "expected <particle> <process>");
            manager_->AddXSBiasProcess(args[0], args[1]);
            NotifyChanged();
            return;
        }
        if (command == addRuleCmd_) {
            EnsureManager("/AIHL/biasing/xs/addRule");
            const auto args = SplitArgs(raw);
            if (args.size() != 2) ThrowCommandError("/AIHL/biasing/xs/addRule", raw, "expected <particle> <process>");
            manager_->CreateOrGetXSProcessBiasRule(args[0], args[1]);
            NotifyChanged();
            return;
        }
        if (command == setFactorCmd_) {
            EnsureManager("/AIHL/biasing/xs/setFactor");
            const auto args = SplitArgs(raw);
            if (args.size() == 2) {
                manager_->SetXSBiasFactor(args[0], ParseDoubleArg("/AIHL/biasing/xs/setFactor", raw, args[1], "factor"));
            } else if (args.size() == 3) {
                manager_->SetXSProcessBiasFactor(args[0], args[1], ParseDoubleArg("/AIHL/biasing/xs/setFactor", raw, args[2], "factor"));
            } else {
                ThrowCommandError("/AIHL/biasing/xs/setFactor", raw, "expected legacy <particle> <factor> or process-level <particle> <process> <factor>");
            }
            NotifyChanged();
            return;
        }
        if (command == setRuleFactorCmd_) {
            EnsureManager("/AIHL/biasing/xs/setRuleFactor");
            const auto args = SplitArgs(raw);
            if (args.size() != 3) ThrowCommandError("/AIHL/biasing/xs/setRuleFactor", raw, "expected <particle> <process> <factor>");
            manager_->SetXSProcessBiasFactor(args[0], args[1], ParseDoubleArg("/AIHL/biasing/xs/setRuleFactor", raw, args[2], "factor"));
            NotifyChanged();
            return;
        }
        if (command == onlyPrimaryCmd_) {
            EnsureManager("/AIHL/biasing/xs/onlyPrimary");
            const auto args = SplitArgs(raw);
            if (args.size() == 2) {
                manager_->SetOnlyPrimary(args[0], ParseBoolArg("/AIHL/biasing/xs/onlyPrimary", raw, args[1], "onlyPrimary"));
            } else if (args.size() == 3) {
                manager_->SetXSProcessOnlyPrimary(args[0], args[1], ParseBoolArg("/AIHL/biasing/xs/onlyPrimary", raw, args[2], "onlyPrimary"));
            } else {
                ThrowCommandError("/AIHL/biasing/xs/onlyPrimary", raw, "expected legacy <particle> <true|false> or process-level <particle> <process> <true|false>");
            }
            NotifyChanged();
            return;
        }
        if (command == setRuleOnlyPrimaryCmd_) {
            EnsureManager("/AIHL/biasing/xs/setRuleOnlyPrimary");
            const auto args = SplitArgs(raw);
            if (args.size() != 3) ThrowCommandError("/AIHL/biasing/xs/setRuleOnlyPrimary", raw, "expected <particle> <process> <true|false>");
            manager_->SetXSProcessOnlyPrimary(args[0], args[1], ParseBoolArg("/AIHL/biasing/xs/setRuleOnlyPrimary", raw, args[2], "onlyPrimary"));
            NotifyChanged();
            return;
        }
        if (command == applyToSecondariesCmd_) {
            EnsureManager("/AIHL/biasing/xs/applyToSecondaries");
            const auto args = SplitArgs(raw);
            if (args.size() == 2) {
                manager_->SetApplyToSecondaries(args[0], ParseBoolArg("/AIHL/biasing/xs/applyToSecondaries", raw, args[1], "applyToSecondaries"));
            } else if (args.size() == 3) {
                manager_->SetXSProcessApplyToSecondaries(args[0], args[1], ParseBoolArg("/AIHL/biasing/xs/applyToSecondaries", raw, args[2], "applyToSecondaries"));
            } else {
                ThrowCommandError("/AIHL/biasing/xs/applyToSecondaries", raw, "expected legacy <particle> <true|false> or process-level <particle> <process> <true|false>");
            }
            NotifyChanged();
            return;
        }
        if (command == setRuleApplyToSecondariesCmd_) {
            EnsureManager("/AIHL/biasing/xs/setRuleApplyToSecondaries");
            const auto args = SplitArgs(raw);
            if (args.size() != 3) ThrowCommandError("/AIHL/biasing/xs/setRuleApplyToSecondaries", raw, "expected <particle> <process> <true|false>");
            manager_->SetXSProcessApplyToSecondaries(args[0], args[1], ParseBoolArg("/AIHL/biasing/xs/setRuleApplyToSecondaries", raw, args[2], "applyToSecondaries"));
            NotifyChanged();
            return;
        }
        if (command == setMinWeightCmd_) {
            EnsureManager("/AIHL/biasing/xs/setMinWeight");
            const auto args = SplitArgs(raw);
            if (args.size() == 2) {
                manager_->SetMinWeight(args[0], ParseDoubleArg("/AIHL/biasing/xs/setMinWeight", raw, args[1], "minWeight"));
            } else if (args.size() == 3) {
                manager_->SetXSProcessMinWeight(args[0], args[1], ParseDoubleArg("/AIHL/biasing/xs/setMinWeight", raw, args[2], "minWeight"));
            } else {
                ThrowCommandError("/AIHL/biasing/xs/setMinWeight", raw, "expected legacy <particle> <value> or process-level <particle> <process> <value>");
            }
            NotifyChanged();
            return;
        }
        if (command == setRuleMinWeightCmd_) {
            EnsureManager("/AIHL/biasing/xs/setRuleMinWeight");
            const auto args = SplitArgs(raw);
            if (args.size() != 3) ThrowCommandError("/AIHL/biasing/xs/setRuleMinWeight", raw, "expected <particle> <process> <value>");
            manager_->SetXSProcessMinWeight(args[0], args[1], ParseDoubleArg("/AIHL/biasing/xs/setRuleMinWeight", raw, args[2], "minWeight"));
            NotifyChanged();
            return;
        }
        if (command == setMaxInteractionsCmd_) {
            EnsureManager("/AIHL/biasing/xs/setMaxInteractions");
            const auto args = SplitArgs(raw);
            if (args.size() == 2) {
                manager_->SetMaxInteractions(args[0], ParseIntArg("/AIHL/biasing/xs/setMaxInteractions", raw, args[1], "maxInteractions"));
            } else if (args.size() == 3) {
                manager_->SetXSProcessMaxInteractions(args[0], args[1], ParseIntArg("/AIHL/biasing/xs/setMaxInteractions", raw, args[2], "maxInteractions"));
            } else {
                ThrowCommandError("/AIHL/biasing/xs/setMaxInteractions", raw, "expected legacy <particle> <n> or process-level <particle> <process> <n>");
            }
            NotifyChanged();
            return;
        }
        if (command == setRuleMaxInteractionsCmd_) {
            EnsureManager("/AIHL/biasing/xs/setRuleMaxInteractions");
            const auto args = SplitArgs(raw);
            if (args.size() != 3) ThrowCommandError("/AIHL/biasing/xs/setRuleMaxInteractions", raw, "expected <particle> <process> <n>");
            manager_->SetXSProcessMaxInteractions(args[0], args[1], ParseIntArg("/AIHL/biasing/xs/setRuleMaxInteractions", raw, args[2], "maxInteractions"));
            NotifyChanged();
            return;
        }
        if (command == addVolumeCmd_) {
            EnsureManager("/AIHL/biasing/xs/addVolume");
            const auto args = SplitArgs(raw);
            if (args.size() == 1) {
                manager_->AddBiasVolume(args[0]);
            } else if (args.size() == 3) {
                manager_->AddXSProcessBiasVolume(args[0], args[1], args[2]);
            } else {
                ThrowCommandError("/AIHL/biasing/xs/addVolume", raw, "expected legacy/global <volume> or process-level <particle> <process> <volume>");
            }
            NotifyChanged();
            return;
        }
        if (command == addRuleVolumeCmd_) {
            EnsureManager("/AIHL/biasing/xs/addRuleVolume");
            const auto args = SplitArgs(raw);
            if (args.size() != 3) ThrowCommandError("/AIHL/biasing/xs/addRuleVolume", raw, "expected <particle> <process> <volume>");
            manager_->AddXSProcessBiasVolume(args[0], args[1], args[2]);
            NotifyChanged();
            return;
        }
        if (command == addVolumeForParticleCmd_) {
            EnsureManager("/AIHL/biasing/xs/addVolumeForParticle");
            const auto args = SplitArgs(raw);
            if (args.size() != 2) ThrowCommandError("/AIHL/biasing/xs/addVolumeForParticle", raw, "expected <particle> <volume>");
            manager_->AddBiasVolumeForParticle(args[0], args[1]);
            NotifyChanged();
            return;
        }
        if (command == validateCmd_) {
            EnsureManager("/AIHL/biasing/validate");
            manager_->Validate();
            G4cout << "[BiasingMessenger] Biasing configuration is valid." << G4endl;
            return;
        }
        if (command == printRulesCmd_) {
            EnsureManager("/AIHL/biasing/xs/printRules");
            manager_->PrintSummary();
            return;
        }
        if (command == printCmd_) {
            EnsureManager("/AIHL/biasing/print");
            manager_->PrintSummary();
            return;
        }
        if (command == clearCmd_) {
            EnsureManager("/AIHL/biasing/clear");
            manager_->Clear();
            NotifyChanged();
            return;
        }
    } catch (const std::exception& ex) {
        G4ExceptionDescription desc;
        desc << "Biasing command failed. input='" << raw << "', error='" << ex.what() << "'";
        G4Exception("BiasingMessenger::SetNewValue", "AIHLBiasingMessenger002", FatalException, desc);
    }
}

void BiasingMessenger::EnsureManager(const char* commandName) const
{
    if (!manager_) {
        throw std::runtime_error(std::string(commandName) + " failed: BiasingManager is null");
    }
}

void BiasingMessenger::NotifyChanged() const
{
    G4cout << "[BiasingMessenger] Biasing state changed. Configure /AIHL/physics/enableBiasing true "
              "and reinitialize physics/geometry before the next run if the run manager was already initialized."
           << G4endl;
}
