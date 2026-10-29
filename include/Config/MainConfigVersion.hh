#pragma once

#include "Config/IniReader.hh"

#include <stdexcept>
#include <string>

// This is the input format version, independent of geometry/project/output
// schemas. Absence keeps the legacy interpretation; it does not opt into a
// closed schema or change duplicate-key precedence. Validate on a candidate
// reader so a rejected load cannot replace a previously accepted configuration.
inline void ValidateMainIniFormat(const IniReader& reader)
{
    if (!reader.HasKey("general", "schema_version")) return;
    for (const auto& field : reader.GetFields()) {
        if (field.normalizedSection != "general" || field.normalizedKey != "schema_version") continue;
        if (field.value != "1") {
            throw std::runtime_error(
                "Main INI schema version rejected at " + reader.GetFilename() + ":"
                + std::to_string(field.lineNumber) + " [" + field.originalSection + "]/"
                + field.originalKey + " = '" + field.value
                + "': supported value is 1; omit the field for legacy version 1. "
                  "Do not downgrade a future format by changing its version tag.");
        }
        (void)reader.GetString("general", "schema_version");
        return;
    }
    throw std::logic_error("Main INI version key has no source declaration");
}
