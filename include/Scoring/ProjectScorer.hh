#pragma once

#include "Scoring/CompiledScorer.hh"

namespace compiled_scorer {

// In a project source tree, include your trusted scorer header and select it
// with Definition::Declare<1>("my_scorer", &CreateMyScorer). Rebuild the CLI.
inline constexpr std::optional<Definition> ProjectScorer = std::nullopt;

}  // namespace compiled_scorer
