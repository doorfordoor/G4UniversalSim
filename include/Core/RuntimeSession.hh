#pragma once
#include <optional>
#include <string>
class SimulationManager;
class G4RunManager;
struct MacroPreflightResult;
namespace runtime {
class NativeExecutionPort;
struct MacroFailureInfo {
  std::string file;
  int line = 0;
  std::string command;
  int code = 0;
  bool codeAvailable = false;
};

// Caller-owned diagnostics survive an exception; no copied Manager state.
struct CshOptions { std::string uiSession; bool seedLocked = false; };
std::string MacroCommandName(const std::string& text);
// Synchronous borrowed execution. No finalization or resource publication.
void RunBatchAndCshSession(SimulationManager& sim, G4RunManager& runManager,
                          NativeExecutionPort& execution,
                          const MacroPreflightResult& preflight, const CshOptions& options,
                          std::optional<MacroFailureInfo>& macroFailure, std::string& macroStatus);
}  // namespace runtime
