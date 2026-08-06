#include "Geometry/GeometrySafety.hh"

#include "Config/ConfigManager.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include <sstream>
#include <stdexcept>

namespace {

const std::set<std::string> kProductionCutKeys = {
    "cut.gamma", "cut.e-", "cut.e+", "cut.proton"
};

std::string CutSuggestion(const std::string& key)
{
    if (key == "cut.electron" || key == "cut.electron-") return "Use 'cut.e-' instead.";
    if (key == "cut.positron" || key == "cut.positron+") return "Use 'cut.e+' instead.";
    return "Use one of cut.gamma, cut.e-, cut.e+, or cut.proton.";
}

}  // namespace

namespace GeometrySafety {

std::string Normalize(const std::string& value)
{
    return StringUtils::ToLower(StringUtils::Trim(value));
}

[[noreturn]] void ThrowFieldError(
    const ConfigManager& config,
    const IniFieldInfo& field,
    const std::string& message,
    const std::string& suggestion
)
{
    std::ostringstream text;
    text << "Geometry config error in file '" << config.GetMainConfigPath()
         << "', line " << field.lineNumber << ", section '[" << field.section
         << "]', key '" << field.key << "', value '" << field.value << "': " << message;
    if (!suggestion.empty()) text << " " << suggestion;
    throw std::runtime_error(text.str());
}

void ValidateProductionCuts(
    const ConfigManager& config,
    const std::set<std::string>& allowedSections
)
{
    const auto fields = config.GetFields();
    for (const auto& field : fields) {
        const std::string key = Normalize(field.key);
        if (!StringUtils::StartsWith(key, "cut.")) continue;

        if (!kProductionCutKeys.count(key)) {
            ThrowFieldError(
                config,
                field,
                "unknown production cut key.",
                CutSuggestion(key)
            );
        }
        if (!allowedSections.count(Normalize(field.section))) {
            ThrowFieldError(
                config,
                field,
                "production cuts are not supported in this section.",
                "Move the cut to a supported volume section and set a non-empty region."
            );
        }

        bool hasRegion = false;
        for (const auto& candidate : fields) {
            if (Normalize(candidate.section) == Normalize(field.section)
                && Normalize(candidate.key) == "region"
                && !StringUtils::Trim(candidate.value).empty()) {
                hasRegion = true;
                break;
            }
        }
        if (!hasRegion) {
            ThrowFieldError(
                config,
                field,
                "production cut requires a non-empty region in the same section.",
                "Add 'region = <RegionName>' to this section."
            );
        }
        try {
            if (UnitParser::ParseLength(field.value) <= 0.0) {
                ThrowFieldError(config, field, "production cut must be > 0.");
            }
        } catch (const std::runtime_error& error) {
            const std::string message = error.what();
            if (message.find("Geometry config error") != std::string::npos) throw;
            ThrowFieldError(config, field, "invalid production cut value: " + message);
        }
    }
}

void ValidateFixedBoxShape(
    const ConfigManager& config,
    const std::string& section,
    const std::string& owner
)
{
    for (const auto& field : config.GetFields()) {
        if (Normalize(field.section) != Normalize(section) || Normalize(field.key) != "shape") continue;
        if (Normalize(field.value) != "box") {
            ThrowFieldError(
                config,
                field,
                owner + " only supports shape=box.",
                "Use 'shape = box' or the hierarchical template for other supported shapes."
            );
        }
        (void)config.GetString(section, "shape");
    }
}

}  // namespace GeometrySafety
