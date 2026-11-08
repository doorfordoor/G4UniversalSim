#pragma once

#include <exception>
#include <stdexcept>

namespace AnalysisOutput::detail {

// A narrow adapter for G4AnalysisManager's three ROOT file operations. The
// template lets component tests exercise the production ordering with faults;
// it owns no manager or resource and is not a general cleanup mechanism.
template<class AnalysisManager>
bool FinalizeRootFile(AnalysisManager& manager, bool& pending, bool& fileOpen)
{
    if (!pending) return false;
    pending = false; // consume this run's attempt even when cleanup fails
    std::exception_ptr firstFailure;
    try {
        if (!manager.Write()) {
            throw std::runtime_error("AnalysisOutput: failed to write ROOT file");
        }
    } catch (...) {
        firstFailure = std::current_exception();
    }
    try {
        if (!manager.CloseFile()) {
            throw std::runtime_error("AnalysisOutput: failed to close ROOT file");
        }
    } catch (...) {
        if (!firstFailure) firstFailure = std::current_exception();
    }
    // Keep resource state distinct from whether finalization was attempted.
    // A failed close must not make path/format setters think it is closed.
    try {
        fileOpen = manager.IsOpenFile();
        if (fileOpen && !firstFailure) {
            throw std::runtime_error("AnalysisOutput: ROOT file remains open after close");
        }
    } catch (...) {
        if (!firstFailure) firstFailure = std::current_exception();
    }
    if (firstFailure) std::rethrow_exception(firstFailure);
    return true;
}

} // namespace AnalysisOutput::detail
