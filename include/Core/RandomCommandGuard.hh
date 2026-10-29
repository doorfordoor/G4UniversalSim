#pragma once

#include <string>

namespace RandomCommandGuard {
// Syntax only: a restore file may be created later by the same macro.
// setSeeds accepts 2..99 nonzero signed longs; native code appends its own 0.
void Validate(const std::string& command);

// Returns false for non-restore commands. A restore is fully checked against
// an independent copy of the current engine, then committed from memory.
// Throws std::runtime_error on refusal; never calls native restoreStatus().
bool ExecuteRestoreIfRequested(const std::string& command);
}  // namespace RandomCommandGuard
