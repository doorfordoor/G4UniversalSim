#include "Core/RuntimeSession.hh"
#include "Core/RuntimeExecution.hh"
#include "Core/SimulationManager.hh"
#include "Core/MacroPreflight.hh"
#include "Core/RandomCommandGuard.hh"
#include "Biasing/BiasingManager.hh"
#include "Materials/MaterialManager.hh"
#include "Output/OutputManager.hh"
#include "Source/SourceManager.hh"
#include "Utils/StringUtils.hh"
#include "G4RunManager.hh"
#include "G4UImanager.hh"
#include "G4StateManager.hh"
#include "G4UIterminal.hh"
#include "G4UIcsh.hh"
#include "G4UIcommand.hh"
#include "G4UIparameter.hh"
#include "G4UIcommandStatus.hh"
#include "G4VModularPhysicsList.hh"

#include <cctype>
#include <functional>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <utility>
#include <vector>

namespace runtime {
namespace {
class SemanticCommandError : public std::runtime_error {
 public:
  explicit SemanticCommandError(const std::string& message, std::string kind = "random_command_validation")
      : std::runtime_error(message), kind_(std::move(kind)) {}
  const std::string& Kind() const { return kind_; }
 private:
  std::string kind_;
};

bool RestartsExecutedKernel(const std::string& commandName) {
  return commandName == "/run/initialize" || commandName == "/run/reinitializegeometry" ||
         commandName == "/run/physicsmodified" || commandName == "/run/geometrymodified";
}

const char* const kRunRestartError = "Kernel reinitialization after an executed run is unsupported: "
    "Geant4 MT initialization can reset master run IDs while workers continue; start a new process instead";

// G4UIterminal prints unrecognized commands but does not propagate their
// failure to the exit code of the enclosing interactive session.
class FailFastCshShell final : public G4UIcsh {
 public:
  explicit FailFastCshShell(bool& stopAfterFailure) : stopAfterFailure_(stopAfterFailure) {}

  G4String GetCommandLineString(const char* message = nullptr) override {
    if (stopAfterFailure_) return "exit";
    return G4UIcsh::GetCommandLineString(message);
  }

 private:
  bool& stopAfterFailure_;
};

class AuditedCshSession final : public G4UIterminal {
 public:
  AuditedCshSession(NativeExecutionPort& execution, bool& stopAfterFailure, std::function<bool()> hasHandlerFailure,
                    std::function<bool(const std::string&)> beforeCommand,
                    std::function<void(const std::string&)> afterCommand)
      : G4UIterminal(new FailFastCshShell(stopAfterFailure)),
        execution_(execution), stopAfterFailure_(stopAfterFailure), hasHandlerFailure_(std::move(hasHandlerFailure)),
        beforeCommand_(std::move(beforeCommand)), afterCommand_(std::move(afterCommand)) {}

  G4int ReceiveG4cerr(const G4String& message) override {
    RecordDiagnostic(message);
    return G4UIterminal::ReceiveG4cerr(message);
  }

  G4int ReceiveG4cout(const G4String& message) override {
    RecordDiagnostic(message);
    return G4UIterminal::ReceiveG4cout(message);
  }

  const std::string& UnrecognizedCommandDiagnostic() const { return unrecognizedCommand_; }
  const std::string& InvalidParameterDiagnostic() const { return invalidParameter_; }
  const std::string& ParameterOutOfRangeDiagnostic() const { return parameterOutOfRange_; }
  const std::string& IllegalApplicationStateDiagnostic() const { return illegalApplicationState_; }
  const std::string& FailedCommand() const { return failedCommand_; }
  const std::string& SemanticFailureDiagnostic() const { return semanticFailure_; }
  const std::string& SemanticFailureKind() const { return semanticFailureKind_; }
  G4int FailedCommandStatus() const { return failedCommandStatus_; }

 private:
  // G4UIterminal's own override is private but virtual. Capture the actual
  // ApplyCommand result here: G4UImanager::GetLastReturnCode() remains zero
  // for rejected csh commands in the tested Geant4 11.3.2 installation.
  void ExecuteCommand(const G4String& command) override {
    if (command.length() < 2) return;
    auto* ui = G4UImanager::GetUIpointer();
    if (!ui) return;
    // Validate the same alias-expanded direct command that Geant4 executes.
    const G4String auditedCommand = StringUtils::NormalizeCommandSlashes(
        StringUtils::Trim(ui->SolveAlias(command)));

    bool handled = false;
    try {
      handled = beforeCommand_(command);
    } catch (const SemanticCommandError& error) {
      stopAfterFailure_ = true;
      failedCommand_ = command;
      semanticFailure_ = error.what();
      semanticFailureKind_ = error.Kind();
      G4cerr << error.what() << G4endl;
      return;
    } catch (const std::exception& error) {
      stopAfterFailure_ = true;
      failedCommand_ = command;
      failedCommandStatus_ = fIllegalApplicationState;
      illegalApplicationState_ = error.what();
      G4cerr << error.what() << G4endl;
      return;
    }
    const G4int result = handled ? fCommandSucceeded : execution_.ApplyCommand(auditedCommand);
    // Finish the current command's diagnostics, then stop reading later input.
    // Messenger failures can occur even when ApplyCommand returns zero.
    if (result != fCommandSucceeded || hasHandlerFailure_()) stopAfterFailure_ = true;
    if (!stopAfterFailure_) afterCommand_(auditedCommand);
    const G4int parameterIndex = result % 100;
    const G4int status = result - parameterIndex;
    if (status != fCommandSucceeded && failedCommand_.empty()) {
      failedCommand_ = command;
      failedCommandStatus_ = result;
    }

    // Preserve the stock G4UIterminal diagnostics alongside the status audit.
    switch (status) {
      case fCommandSucceeded: break;
      case fCommandNotFound:
        G4cerr << "command <" << ui->SolveAlias(command) << "> not found" << G4endl;
        if (command.find("@@") != G4String::npos) G4cout << "@@G4UIterminal" << G4endl;
        break;
      case fIllegalApplicationState:
        G4cerr << "illegal application state -- command refused" << G4endl;
        break;
      case fParameterOutOfRange:
        break;
      case fParameterOutOfCandidates: {
        if (auto* cmd = FindCommand(command)) {
          G4cerr << "Parameter is out of candidate list (index " << parameterIndex << ")" << G4endl;
          if (parameterIndex < 99 && cmd->GetParameter(parameterIndex)) {
            G4cerr << "Candidates : " << cmd->GetParameter(parameterIndex)->GetParameterCandidates() << G4endl;
          }
        }
        break;
      }
      case fParameterUnreadable:
        G4cerr << "Parameter is wrong type and/or is not omittable (index "
               << parameterIndex << ")" << G4endl;
        break;
      default:
        G4cerr << "command refused (" << status << ")" << G4endl;
        break;
    }
  }

  void RecordDiagnostic(const G4String& message) {
    std::string normalized(message);
    for (char& ch : normalized) {
      ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    if ((normalized.find("command <") != std::string::npos &&
         normalized.find("> not found") != std::string::npos) ||
        normalized.find("command not found:") != std::string::npos) {
      if (unrecognizedCommand_.empty()) unrecognizedCommand_ = message;
    }
    // Keep human-readable native diagnostics in addition to the numeric
    // ApplyCommand result recorded by this session's ExecuteCommand override.
    if (normalized.find("parameter is wrong type and/or is not omittable") != std::string::npos) {
      if (invalidParameter_.empty()) invalidParameter_ = message;
    }
    if (normalized.find("parameter out of range:") != std::string::npos) {
      if (parameterOutOfRange_.empty()) parameterOutOfRange_ = message;
    }
    if (normalized.find("illegal application state -- command refused") != std::string::npos) {
      if (illegalApplicationState_.empty()) illegalApplicationState_ = message;
    }
  }

  NativeExecutionPort& execution_;
  bool& stopAfterFailure_;
  std::function<bool()> hasHandlerFailure_;
  std::function<bool(const std::string&)> beforeCommand_;
  std::function<void(const std::string&)> afterCommand_;
  std::string semanticFailure_;
  std::string semanticFailureKind_;
  std::string unrecognizedCommand_;
  std::string invalidParameter_;
  std::string parameterOutOfRange_;
  std::string illegalApplicationState_;
  std::string failedCommand_;
  G4int failedCommandStatus_ = 0;
};

}  // namespace

std::string MacroCommandName(const std::string& text) {
  const auto end = text.find_first_of(" \t\r\n");
  std::string name = text.substr(0, end);
  for (char& ch : name) ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
  return name;
}

void RunBatchAndCshSession(SimulationManager& sim, G4RunManager& runManager,
                          NativeExecutionPort& execution,
                          const MacroPreflightResult& preflight, const CshOptions& options,
                          std::optional<MacroFailureInfo>& macroFailure, std::string& macroStatus)
{
    bool physicsListDirty = false;
    if (!sim.GetContext().GetMacroFile().empty()) {
      macroStatus = "running";
      bool kernelInitialized = false;
      for (const auto& command : preflight.commands) {
        const std::string commandName = MacroCommandName(command.text);
        try { sim.ValidateEffectiveModuleCommand(command.text); }
        catch(const std::exception&) {
          macroFailure=MacroFailureInfo{command.sourceFile.string(),static_cast<int>(command.lineNumber),command.text,0,false};
          macroStatus="failed";
          throw;
        }
        if (!sim.GetOutputManager()->GetRunSummary().GetRuns().empty() && RestartsExecutedKernel(commandName)) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error(kRunRestartError);
        }
        const bool physicsCommand = commandName.rfind("/aihl/physics/", 0) == 0 ||
            commandName.rfind("/aihl/biasing/", 0) == 0;
        const bool readOnlyPhysicsCommand = commandName == "/aihl/physics/print" ||
            commandName == "/aihl/physics/listavailablereferences" ||
            commandName == "/aihl/physics/listavailableemreferences" ||
            commandName == "/aihl/physics/dumpprocesses" ||
            commandName == "/aihl/biasing/print" ||
            commandName == "/aihl/biasing/validate" ||
            commandName == "/aihl/biasing/xs/printrules";
        const bool changesPhysics = physicsCommand && !readOnlyPhysicsCommand;
        const bool materialCommand = commandName.rfind("/aihl/material/", 0) == 0;
        const bool readOnlyMaterialCommand = commandName == "/aihl/material/print" ||
            commandName == "/aihl/material/list";
        if (materialCommand && !readOnlyMaterialCommand && kernelInitialized) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error("Material macro command after kernel initialization is not supported; move it before /run/initialize or /run/beamOn, or start a new process: " + command.text);
        }
        if (changesPhysics && kernelInitialized) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error("Physics/biasing macro command after kernel initialization is not supported; move it before /run/initialize or /run/beamOn: " + command.text);
        }
        if (commandName == "/run/reinitializegeometry" && kernelInitialized &&
            sim.GetBiasingManager() && sim.GetBiasingManager()->IsEnabled()) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error("/run/reinitializeGeometry with attached biasing operators is not safe in this lifecycle; start a fresh process with the new geometry instead.");
        }
        if (commandName == "/run/initialize") {
          // Contract E: dependency guards must run before the physics/SD are
          // constructed; nested guards after /run/initialize cannot undo that.
          try {
            sim.ValidateParallelWorldDependencies();
          } catch (...) {
            macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber),
                                            command.text, 0, false};
            macroStatus = "failed";
            throw;
          }
        }
        if (commandName == "/run/initialize" || commandName == "/run/beamon") {
          if (physicsListDirty) {
            runManager.SetUserInitialization(sim.CreatePhysicsList().release());
            sim.InitializeSourceAfterPhysicsListRegistered();
            physicsListDirty = false;
          }
        }
        if (commandName == "/run/beamon" && sim.GetBiasingManager() && sim.GetBiasingManager()->IsEnabled()) {
          if (!kernelInitialized) {
            try {
              execution.InitializeKernel();
            } catch (...) {
              macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber),
                                              command.text, 0, false};
              macroStatus = "failed";
              throw;
            }
            kernelInitialized = true;
          }
          try {
            sim.ValidateBiasingProcessTargets();
          } catch (...) {
            macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
            macroStatus = "failed";
            throw;
          }
        }
        if (commandName == "/run/beamon") {
          if (!kernelInitialized) {
            macroFailure = MacroFailureInfo{
                command.sourceFile.string(), static_cast<int>(command.lineNumber),
                command.text, 0, false};
            macroStatus = "failed";
            throw std::runtime_error(
                "/run/beamOn requires an initialized Geant4 kernel in batch mode; "
                "add /run/initialize before /run/beamOn. Without initialization "
                "Geant4 may silently ignore BeamOn without processing events.");
          }
          try {
            sim.ValidateScoringVolumeConfigsBeforeRun();
            sim.ValidateParallelWorldForRun();
          } catch (...) {
            macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
            macroStatus = "failed";
            throw;
          }
          try {
            const int nextRunId = static_cast<int>(sim.GetOutputManager()->GetRunSummary().GetRuns().size());
            sim.GetOutputManager()->ValidateOutputTargetDirectories(
                nextRunId, sim.GetContext().GetNumThreads());
          } catch (...) {
            macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
            macroStatus = "failed";
            throw;
          }
        }
        const auto sourceFailuresBefore = sim.GetSourceManager()->GetCommandFailureCount();
        const auto materialFailuresBefore = sim.GetMaterialManager()->GetCommandFailureCount();
        const auto outputFailuresBefore = sim.GetOutputManager()->GetCommandFailureCount();
        const auto biasingFailuresBefore = sim.GetBiasingManager()->GetCommandFailureCount();
        const bool seedStateChanged = sim.NoteMacroCommand(command.text);
        bool restoredRandomState = false;
        try {
          sim.GetSourceManager()->BeforeNativeGPSCommand(command.text);
          RandomCommandGuard::Validate(command.text);
          restoredRandomState = RandomCommandGuard::ExecuteRestoreIfRequested(command.text);
        } catch (...) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
          macroStatus = "failed";
          throw;
        }
        int status = fCommandSucceeded;
        try {
          if (!restoredRandomState) status = execution.ApplyCommand(command.text);
        } catch (...) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber),
                                          command.text, 0, false};
          macroStatus = "failed";
          throw;
        }
        if (status != 0) {
          macroFailure = MacroFailureInfo{
              command.sourceFile.string(),
              static_cast<int>(command.lineNumber),
              command.text,
              status,
              true};
          macroStatus = "failed";
          throw std::runtime_error(
              "Failed to execute macro command '" + command.text + "' at " +
              command.sourceFile.string() + ":" +
              std::to_string(command.lineNumber) +
              ", G4UImanager status=" + std::to_string(status));
        }
        if (sim.GetSourceManager()->GetCommandFailureCount() != sourceFailuresBefore) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber),
                                          command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error(sim.GetSourceManager()->GetLastCommandFailure());
        }
        if (materialCommand &&
            sim.GetMaterialManager()->GetCommandFailureCount() != materialFailuresBefore) {
          macroFailure = MacroFailureInfo{
              command.sourceFile.string(), static_cast<int>(command.lineNumber),
              command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error(sim.GetMaterialManager()->GetLastCommandFailure());
        }
        if (commandName.rfind("/aihl/output/", 0) == 0 &&
            sim.GetOutputManager()->GetCommandFailureCount() != outputFailuresBefore) {
          macroFailure = MacroFailureInfo{
              command.sourceFile.string(), static_cast<int>(command.lineNumber),
              command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error(sim.GetOutputManager()->GetLastCommandFailure());
        }
        if (sim.GetBiasingManager()->GetCommandFailureCount() != biasingFailuresBefore) {
          macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error(sim.GetBiasingManager()->GetLastCommandFailure());
        }
        // Worker construction can fail during initialization as well as BeamOn.
        // Do not consume a later macro command after a latched failure, even
        // when the kernel command itself returned success.
        if (sim.GetOutputManager()->HasOutputFailure()) {
          const auto failure = sim.GetOutputManager()->GetOutputFailure();
          macroFailure = MacroFailureInfo{
              command.sourceFile.string(), static_cast<int>(command.lineNumber),
              command.text, 0, false};
          macroStatus = "failed";
          throw std::runtime_error("Worker output failure (run " +
              std::to_string(failure.runId) + ", thread " +
              std::to_string(failure.threadId) + ", " + failure.stage +
              "): " + failure.message);
        }
        if (commandName == "/run/initialize") {
          kernelInitialized = true;
          try {
            sim.ValidateBiasingProcessTargets();
            sim.ValidateParallelWorldForRun();
          } catch (...) {
            macroFailure = MacroFailureInfo{command.sourceFile.string(), static_cast<int>(command.lineNumber), command.text, 0, false};
            macroStatus = "failed";
            throw;
          }
        }
        if (changesPhysics) physicsListDirty = true;
        sim.ConfirmMacroCommandSuccess(seedStateChanged);
        sim.RecordSuccessfulMacroCommand(command.text, command.sourceFile.string(),
                                         static_cast<int>(command.lineNumber), command.inputSha256);
      }
      macroStatus = "completed";
    }

    if (sim.GetContext().IsInteractive()) {
      // A batch macro may end after mutating physics but before initializing
      // the kernel. Rebind now: the interactive /run/initialize command is
      // dispatched inside Geant4 and cannot go through the batch rebind path.
      if (physicsListDirty) {
        runManager.SetUserInitialization(sim.CreatePhysicsList().release());
        sim.InitializeSourceAfterPhysicsListRegistered();
        physicsListDirty = false;
        std::cout << "[PhysicsLifecycle] Rebound physics list from batch macro before interactive UI.\n";
      }
      // Interactive PhysicsMessenger mutations are rejected after registration.
      if (options.uiSession != "csh" && sim.GetSourceManager()->HasPendingDeferredConfiguration()) {
        throw std::runtime_error("Interactive ion/confinement configuration before its first run requires --ui-session csh "
                                 "to track native GPS overrides; use csh or a batch macro in a fresh process");
      }
      sim.EnableInteractivePhysicsGuard();
      const auto physicsFailuresBefore = sim.GetInteractivePhysicsFailureCount();
      const auto appFailuresBefore = sim.GetAppCommandFailureCount();
      const auto sourceFailuresBefore = sim.GetSourceManager()->GetCommandFailureCount();
      const auto materialFailuresBefore = sim.GetMaterialManager()->GetCommandFailureCount();
      const auto outputFailuresBefore = sim.GetOutputManager()->GetCommandFailureCount();
      // Rejected interactive biasing mutations used to be warnings only: the
      // command was ignored, the session continued and the process exited 0
      // while the user believed biasing was configured.
      const auto biasingRejectsBefore = sim.GetBiasingManager()->GetInteractiveRejectCount();
      const auto biasingFailuresBefore = sim.GetBiasingManager()->GetCommandFailureCount();
      RunSummary& summary = sim.GetOutputManager()->GetRunSummary();
      summary.Set("interactive_command_failure_kind", "none");
      summary.Set("interactive_command_failure_message", "not_applicable");
      std::string unrecognizedCommand;
      std::string invalidParameter;
      std::string parameterOutOfRange;
      std::string illegalApplicationState;
      std::string failedCommand;
      std::string randomSemanticFailure;
      std::string semanticFailureKind;
      G4int failedCommandStatus = fCommandSucceeded;
      if (options.uiSession == "csh") {
        bool stopAfterFailure = false;
        const auto hasHandlerFailure = [&]() {
          return sim.GetInteractivePhysicsFailureCount() != physicsFailuresBefore ||
                 sim.GetAppCommandFailureCount() != appFailuresBefore ||
                 sim.GetSourceManager()->GetCommandFailureCount() != sourceFailuresBefore ||
                 sim.GetMaterialManager()->GetCommandFailureCount() != materialFailuresBefore ||
                 sim.GetOutputManager()->GetCommandFailureCount() != outputFailuresBefore ||
                 sim.GetBiasingManager()->GetInteractiveRejectCount() != biasingRejectsBefore ||
                 sim.GetBiasingManager()->GetCommandFailureCount() != biasingFailuresBefore ||
                 sim.GetOutputManager()->HasOutputFailure();
        };
        AuditedCshSession ui(execution, stopAfterFailure, hasHandlerFailure, [&](const std::string& command) {
          sim.GetSourceManager()->BeforeNativeGPSCommand(command);
          try {
            const std::string resolved = StringUtils::NormalizeCommandSlashes(StringUtils::Trim(
                G4UImanager::GetUIpointer()->SolveAlias(command.c_str())));
            std::istringstream input(resolved);
            std::string token;
            input >> token;
            token = StringUtils::ToLower(token);
            if (!sim.GetOutputManager()->GetRunSummary().GetRuns().empty() && RestartsExecutedKernel(token))
              throw SemanticCommandError(kRunRestartError, "run_lifecycle");
            if (token == "/control/execute" || token == "/control/loop" ||
                token == "/control/foreach" || token == "/control/if" || token == "/control/doif" ||
                token == "/control/strif" || token == "/control/strdoif") {
              throw std::runtime_error("Nested/dynamic csh dispatch cannot audit random command semantics; "
                                       "use a preflighted --macro file or direct csh commands instead");
            }
            if (options.seedLocked && token.rfind("/random/", 0) == 0) {
              throw std::runtime_error("Random command conflicts with explicit CLI seed lock");
            }
            RandomCommandGuard::Validate(resolved);
            sim.ValidateEffectiveModuleCommand(resolved);
            if (token == "/run/initialize") {
              try {
                sim.ValidateParallelWorldDependencies();
              } catch (const std::exception& error) {
                throw SemanticCommandError(error.what(), "parallel_world_config");
              }
            }
            if (token == "/run/beamon" &&
                G4StateManager::GetStateManager()->GetCurrentState() != G4State_PreInit) {
              try {
                sim.ValidateScoringVolumeConfigsBeforeRun();
              } catch (const std::exception& error) {
                const std::string message = error.what();
                const std::string kind =
                    message.find("unknown Geant4 particle") != std::string::npos
                        ? "scoring_filter_particle"
                        : "scoring_volume_config";
                throw SemanticCommandError(message, kind);
              }
              try {
                sim.ValidateParallelWorldForRun();
              } catch (const std::exception& error) {
                throw SemanticCommandError(error.what(), "parallel_world_config");
              }
            }
            return RandomCommandGuard::ExecuteRestoreIfRequested(resolved);
          } catch (const SemanticCommandError&) {
            throw;
          } catch (const std::exception& error) {
            throw SemanticCommandError(error.what());
          }
        }, [&](const std::string& command) {
          sim.ConfirmMacroCommandSuccess(sim.NoteMacroCommand(command));
          sim.RecordSuccessfulMacroCommand(command, "", 0);
          const std::string resolved = StringUtils::NormalizeCommandSlashes(StringUtils::Trim(
              G4UImanager::GetUIpointer()->SolveAlias(command.c_str())));
          std::istringstream stream(resolved);
          std::string token;
          stream >> token;
          if (StringUtils::ToLower(token) == "/run/initialize") {
            // The kernel is now initialized: validate configured volume filters
            // before any later /run/beamOn can generate events. A failure is
            // recorded in the shared latch; the session stops on the next check.
            try {
              sim.ValidateScoringVolumeConfigsBeforeRun();
              sim.ValidateParallelWorldForRun();
            } catch (const std::exception&) {
            }
          }
        });
        ui.SessionStart();
        unrecognizedCommand = ui.UnrecognizedCommandDiagnostic();
        invalidParameter = ui.InvalidParameterDiagnostic();
        parameterOutOfRange = ui.ParameterOutOfRangeDiagnostic();
        illegalApplicationState = ui.IllegalApplicationStateDiagnostic();
        failedCommand = ui.FailedCommand();
        failedCommandStatus = ui.FailedCommandStatus();
        randomSemanticFailure = ui.SemanticFailureDiagnostic();
        semanticFailureKind = ui.SemanticFailureKind();
      } else {
        throw std::runtime_error("Interactive execution requires --ui-session csh; native unaudited sessions are unavailable.");
      }
      const bool sourceFailed = sim.GetSourceManager()->GetCommandFailureCount() != sourceFailuresBefore;
      const bool materialFailed = sim.GetMaterialManager()->GetCommandFailureCount() != materialFailuresBefore;
      const bool outputFailed = sim.GetOutputManager()->GetCommandFailureCount() != outputFailuresBefore;
      const bool physicsFailed = sim.GetInteractivePhysicsFailureCount() != physicsFailuresBefore;
      const bool appFailed = sim.GetAppCommandFailureCount() != appFailuresBefore;
      const bool biasingFailed = sim.GetBiasingManager()->GetInteractiveRejectCount() != biasingRejectsBefore ||
          sim.GetBiasingManager()->GetCommandFailureCount() != biasingFailuresBefore;
      const bool uiCommandFailed = failedCommandStatus != fCommandSucceeded;
      if (sourceFailed || materialFailed || outputFailed || !unrecognizedCommand.empty() || !invalidParameter.empty() ||
          !parameterOutOfRange.empty() || !illegalApplicationState.empty() || physicsFailed ||
          biasingFailed || appFailed || uiCommandFailed || !randomSemanticFailure.empty()) {
        std::vector<std::string> kinds;
        if (sourceFailed) kinds.push_back("source");
        if (physicsFailed) kinds.push_back("physics");
        if (appFailed) kinds.push_back("app");
        if (biasingFailed) kinds.push_back("biasing");
        if (materialFailed) kinds.push_back("material");
        if (outputFailed) kinds.push_back("output");
        if (!randomSemanticFailure.empty()) kinds.push_back(semanticFailureKind);
        if (!unrecognizedCommand.empty()) kinds.push_back("geant4_command_not_found");
        if (!invalidParameter.empty()) kinds.push_back("geant4_invalid_parameter");
        if (!parameterOutOfRange.empty()) kinds.push_back("geant4_parameter_out_of_range");
        if (!illegalApplicationState.empty()) kinds.push_back("geant4_illegal_application_state");
        // A refused command also reports a non-zero UI status; keep the specific
        // diagnostic as the reported kind instead of degrading it to "multiple".
        if (uiCommandFailed && kinds.empty()) kinds.push_back("geant4_command_status");
        std::string kind;
        if (kinds.size() == 1) {
          kind = kinds.front();
        } else if (kinds.size() == 2 && materialFailed && outputFailed) {
          // Historical summary value: material and output failures were
          // reported together before the other kinds existed.
          kind = "material_and_output";
        } else {
          kind = "multiple";
        }
        std::vector<std::string> messages;
        const auto appendDiagnostic = [&](const std::string& diagnostic) {
          if (diagnostic.empty()) return;
          // Native G4cerr diagnostics often end with a newline; the summary
          // is key=value line-oriented and must keep the complete message on
          // a single line for downstream parsers.
          std::string singleLine;
          singleLine.reserve(diagnostic.size());
          for (char ch : diagnostic) {
            if (ch == '\r' || ch == '\n' || ch == '\t') {
              if (!singleLine.empty() && singleLine.back() != ' ') singleLine.push_back(' ');
            } else {
              singleLine.push_back(ch);
            }
          }
          while (!singleLine.empty() && singleLine.back() == ' ') singleLine.pop_back();
          if (!singleLine.empty()) messages.push_back(std::move(singleLine));
        };
        if (sourceFailed) appendDiagnostic(sim.GetSourceManager()->GetLastCommandFailure());
        if (physicsFailed) appendDiagnostic(sim.GetLastInteractivePhysicsFailure());
        if (appFailed) appendDiagnostic(sim.GetLastAppCommandFailure());
        if (biasingFailed) {
          if (sim.GetBiasingManager()->GetInteractiveRejectCount() != biasingRejectsBefore)
            appendDiagnostic(sim.GetBiasingManager()->GetLastInteractiveReject());
          if (sim.GetBiasingManager()->GetCommandFailureCount() != biasingFailuresBefore)
            appendDiagnostic(sim.GetBiasingManager()->GetLastCommandFailure());
        }
        if (materialFailed) appendDiagnostic(sim.GetMaterialManager()->GetLastCommandFailure());
        if (outputFailed) appendDiagnostic(sim.GetOutputManager()->GetLastCommandFailure());
        appendDiagnostic(unrecognizedCommand);
        appendDiagnostic(invalidParameter);
        appendDiagnostic(parameterOutOfRange);
        appendDiagnostic(illegalApplicationState);
        appendDiagnostic(randomSemanticFailure);
        if (!randomSemanticFailure.empty()) appendDiagnostic("Rejected command: " + failedCommand);
        if (uiCommandFailed) {
          appendDiagnostic("Geant4 UI status=" + std::to_string(failedCommandStatus) +
                           " for command: " + failedCommand);
        }
        const std::string message = StringUtils::Join(messages, "; ");
        summary.Set("interactive_command_failure_kind", kind);
        summary.Set("interactive_command_failure_message", message);
        throw std::runtime_error("Interactive command failure: " + message);
      }
    }
    if (sim.GetOutputManager()->HasOutputFailure()) {
      const auto failure = sim.GetOutputManager()->GetOutputFailure();
      throw std::runtime_error("Interactive output failure (run " +
          std::to_string(failure.runId) + ", thread " +
          std::to_string(failure.threadId) + ", " + failure.stage +
          "): " + failure.message);
    }

}
}  // namespace runtime
