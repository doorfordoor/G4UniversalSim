#pragma once

// Strict JSON adapter for the controlled session protocol.
//
// The repository has no JSON parser of its own, so F2 vendors one fixed,
// official single-header release (nlohmann/json 3.11.3, MIT) through
// ThirdParty/SessionJsonDependency.hh. This adapter only accepts the safe
// subset the protocol needs: an object-rooted document with bounded depth and
// string sizes, no duplicate keys, no non-finite numbers and no binary values.
// Parsing failures are reported, never silently repaired.

#include "ThirdParty/SessionJsonDependency.hh"

#include <cstddef>
#include <string>
#include <string_view>

namespace SessionJson {

using Json = nlohmann::json;

// One request or response frame; larger documents are rejected before parsing.
constexpr std::size_t kMaxDocumentBytes = 65536;
// Individual string values (paths, labels, units) stay far below this bound.
constexpr std::size_t kMaxStringBytes = 8192;
// Containers are shallow in this protocol (objects of scalars and small arrays).
constexpr int kMaxDepth = 12;
// Arrays are only used for vectors and artifact lists.
constexpr std::size_t kMaxArrayLength = 512;

// Parses `text` strictly. On failure returns false and fills `error` with a
// stable machine-facing message; `value` is left untouched.
bool ParseStrict(std::string_view text, Json& value, std::string& error);

// Compact single-line serialisation with ASCII escapes. Callers add framing.
std::string Dump(const Json& value);

}  // namespace SessionJson
