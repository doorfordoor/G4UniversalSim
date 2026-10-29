#include "Biasing/BiasingManager.hh"
#include "Config/ConfigValue.hh"
#include "Config/EffectiveRuntime.hh"
#include "Utils/StringUtils.hh"
#include <algorithm>
#include <sstream>

namespace {
using namespace effective_config;
std::vector<std::string> Words(const std::string& text)
{
    // Match BiasingMessenger's quoted argument tokenization.
    std::vector<std::string> result;
    std::string word; bool quoted = false;
    for (unsigned char c : text) {
        if (c == '"') { quoted = !quoted; continue; }
        if (!quoted && std::isspace(c)) {
            if (!word.empty()) { result.push_back(word); word.clear(); }
        } else word.push_back(static_cast<char>(c));
    }
    if (!word.empty()) result.push_back(word);
    return result;
}
std::string LegacyIdentity(const std::string& particle)
{
    return "legacy:" + StringUtils::ToLower(StringUtils::Trim(particle));
}
Value TypedRequested(const Field& field, const Value& resolved)
{
    if (!field.requested_known) return {};
    const auto* raw = std::get_if<std::string>(&field.requested.data);
    if (!raw) return field.requested;
    ConfigValue value(*raw);
    if (std::holds_alternative<bool>(resolved.data)) return value.AsBool();
    if (std::holds_alternative<double>(resolved.data)) return value.AsDouble();
    if (std::holds_alternative<std::int64_t>(resolved.data)) return value.AsInt();
    if (std::holds_alternative<Value::Array>(resolved.data)) return List(value.AsStringVector());
    return *raw;
}
}

std::string BiasingManager::EffectiveRuleIdentity(const std::string& particle, const std::string& process)
{
    // A JSON tuple is injective even if either component contains |, / or ~.
    return "xs:" + effective_config::Value(effective_config::Value::Array{
        NormalizeParticleName(particle), StringUtils::Trim(process)}).ToJson();
}

std::vector<effective_config::Field> BiasingManager::BuildEffectiveConfigFields() const
{
    using namespace effective_config;
    std::vector<Field> result;
    std::set<std::string> overriddenLegacy;
    for (const auto& legacy : config_.xsRules) for (const auto& process : legacy.processNames)
        overriddenLegacy.insert(EffectiveRuleIdentity(legacy.particleName, process));
    const auto add = [&](const std::string& identity, const char* key, Value value,
                         const std::vector<std::string>& sections, const char* inputKey = nullptr,
                         const std::string& derivation = "") {
        const auto path = identity.empty() ? FieldPath("biasing", key) : ObjectFieldPath("biasing", identity, key);
        Field field = effectiveState_->Make(path, value, "", "", {});
        if (overriddenLegacy.count(identity) && !sections.empty() && sections.front() != "biasing.xs" &&
            std::string(key) != "enabled" && std::string(key) != "name" && std::string(key) != "legacy_generated") {
            const char* legacyKey = std::string(key) == "particle" ? "particles" : (std::string(key) == "process" ? "processes" : key);
            auto shadowed = effectiveState_->Make(path, value, "", "biasing.xs", {legacyKey});
            for (auto& origin : shadowed.origins) origin.disposition = "shadowed";
            field.origins = std::move(shadowed.origins);
        }
        for (const auto& section : sections) {
            auto part = effectiveState_->Make(path, value, "", section, {inputKey ? inputKey : key});
            for(auto& previous:field.origins)if(previous.disposition!="shadowed")previous.disposition="shadowed";
            // Each process section creates a fresh rule, so omission in a later
            // section really resets that property to the rule default.
            field.origins.insert(field.origins.end(), part.origins.begin(), part.origins.end());
            field.requested_known = part.requested_known;
            field.requested = TypedRequested(part, value);
            const std::string property=key;
            if(!part.requested_known && section.rfind("biasing.xs.",0)==0 && (property=="particle" || property=="process" || property=="name")) {
                const auto headers=effectiveState_->reader.GetSectionDeclarations();
                std::size_t winningHeader=0;for(const auto& header:headers)if(header.normalizedSection==section)winningHeader=std::max(winningHeader,header.lineNumber);
                for(auto& old:field.origins)if(old.disposition=="accepted")old.disposition="shadowed";
                for(const auto& header:headers)if(header.normalizedSection==section){
                    Origin declared;declared.kind="main_ini";declared.file=effectiveState_->reader.GetFilename();declared.line=header.lineNumber;
                    declared.section=header.originalSection;declared.raw="["+header.originalSection+"]";declared.input_sha256=effectiveState_->reader.GetInputSha256();declared.disposition=header.lineNumber==winningHeader?"derived":"shadowed";
                    field.origins.push_back(declared);
                }
                Origin derived;derived.kind="derived";derived.disposition="derived";derived.raw="Rule "+property+" derived from accepted section identity";field.origins.push_back(derived);
                // A header is a request for an object identity, not an explicit
                // per-property request for its generated display name.
                if(property!="name"){field.requested=value;field.requested_known=true;}
                field.reason="Derived from accepted process-rule section identity; runtime evidence is separate";
            }
        }
        field.resolved = std::move(value);
        if(std::string(key)=="only_primary" && field.requested_known && field.requested.ToJson()!=field.resolved.ToJson()){
            Origin derived;derived.kind="derived";derived.disposition="derived";derived.raw="apply_to_secondaries=true forces only_primary=false";field.origins.push_back(derived);
            field.reason="only_primary request is resolved by apply_to_secondaries precedence";
        }
        if (!derivation.empty()) {
            Origin derived; derived.kind = "derived"; derived.disposition = "derived"; derived.raw = derivation;
            field.origins.push_back(std::move(derived));
            field.reason = derivation + "; runtime application is recorded separately";
        }
        for (const auto& old : effectiveState_->fields) if (old.path == field.path) {
            field.origins = old.origins; field.requested = old.requested; field.requested_known = old.requested_known;
        }
        result.push_back(std::move(field));
    };
    add("", "enabled", config_.enabled, {"biasing"});
    // The legacy global volume list is consumed only while biasing is enabled.
    add("", "global_volumes", List(globalBiasVolumes_), config_.enabled ? std::vector<std::string>{"biasing.xs"} : std::vector<std::string>{}, "volumes");
    for (const auto& rule : config_.xsRules) {
        const std::string identity = LegacyIdentity(rule.particleName);
        const std::vector<std::string> sections{"biasing.xs"};
        add(identity, "particle", rule.particleName, sections, "particles", "Particle identity derived from the accepted legacy particles list");
        // Identity is derived from one element of the accepted particles array.
        if (!effectiveState_->accepted) result.back().requested = rule.particleName;
        add(identity, "processes", List(rule.processNames), sections, "processes");
        add(identity, "name", rule.name, {}, nullptr, "Generated legacy rule name");
        add(identity, "enabled", rule.enabled, {});
        add(identity, "factor", rule.factor, sections);
        add(identity, "only_primary", rule.onlyPrimary, sections);
        add(identity, "apply_to_secondaries", rule.applyToSecondaries, sections);
        add(identity, "min_weight", rule.minWeight, sections);
        add(identity, "max_interactions", rule.maxInteractions, sections);
        add(identity, "volumes", List(rule.volumeNames), sections);
    }
    for (const auto& rule : BuildExpandedProcessRules(false)) {
        const auto identity = EffectiveRuleIdentity(rule.particleName, rule.processName);
        std::vector<std::string> sections;
        std::string derivation;
        if (rule.legacyGenerated) {
            sections = {"biasing.xs"};
            derivation = "Expanded from legacy particle/process lists; explicit rules override the same pair";
        } else {
            const auto source = effectiveRuleSections_.find(identity);
            if (source != effectiveRuleSections_.end()) sections = source->second;
        }
        add(identity, "particle", rule.particleName, sections, rule.legacyGenerated ? "particles" : "particle", derivation);
        if (rule.legacyGenerated && !effectiveState_->accepted) result.back().requested = rule.particleName;
        add(identity, "process", rule.processName, sections, rule.legacyGenerated ? "processes" : "process", derivation);
        if (rule.legacyGenerated && !effectiveState_->accepted) result.back().requested = rule.processName;
        add(identity, "name", rule.name, rule.legacyGenerated ? std::vector<std::string>{} : sections, nullptr,
            rule.legacyGenerated ? "Generated expanded legacy name" : "");
        add(identity, "enabled", rule.enabled, rule.legacyGenerated ? std::vector<std::string>{} : sections);
        add(identity, "factor", rule.factor, sections, nullptr, derivation);
        add(identity, "volumes", List(rule.volumeNames), sections, nullptr, derivation);
        add(identity, "only_primary", rule.onlyPrimary, sections, nullptr, derivation);
        add(identity, "apply_to_secondaries", rule.applyToSecondaries, sections, nullptr, derivation);
        add(identity, "min_weight", rule.minWeight, sections, nullptr, derivation);
        add(identity, "max_interactions", rule.maxInteractions, sections, nullptr, derivation);
        add(identity, "legacy_generated", rule.legacyGenerated, {}, nullptr, rule.legacyGenerated ? derivation : "");
    }
    return result;
}

void BiasingManager::AcceptEffectiveConfig(const IniReader& reader)
{
    auto previous = effectiveState_;
    auto next = std::make_shared<effective_config::ConsumerState>();
    next->reader = reader;
    next->generation = previous->generation;
    effectiveState_ = next;
    try { next->Accept(reader, BuildEffectiveConfigFields()); }
    catch (...) { effectiveState_ = previous; throw; }
}
std::vector<effective_config::Field> BiasingManager::ExportEffectiveConfigFields() const
{
    return effectiveState_->accepted ? effectiveState_->fields : BuildEffectiveConfigFields();
}
effective_config::Value BiasingManager::ExportEffectiveConfigEvidence() const { return effectiveState_->Evidence(); }

void BiasingManager::ConfirmEffectiveConfigDerived(const std::string& reason, effective_config::Origin origin)
{
    bool requestedKnown=false;effective_config::Value requested;
    for(const auto& field:effectiveState_->fields)if(field.path=="/biasing/enabled"){requestedKnown=field.requested_known;requested=field.requested;}
    origin.kind = "derived"; origin.disposition = "derived";
    effectiveState_->Confirm(BuildEffectiveConfigFields(), reason, origin, false, {"/biasing/enabled"});
    for (auto& field : effectiveState_->fields) if (field.path == "/biasing/enabled") {
        // A dependency resolution must preserve an earlier explicit request.
        field.requested_known=requestedKnown;field.requested=requested;
        field.reason = reason + "; runtime application is recorded separately";
    }
}

void BiasingManager::ConfirmEffectiveConfigMutation(const std::string& command, effective_config::Origin origin)
{
    using namespace effective_config;
    if (origin.kind == "derived") { ConfirmEffectiveConfigDerived(command, std::move(origin)); return; }
    auto words = Words(command);
    if (words.empty() || words[0].rfind("/AIHL/biasing/", 0) != 0) return;
    const std::string name = words[0].substr(std::string("/AIHL/biasing/").size());
    if (name == "print" || name == "validate" || name == "xs/printRules") return;
    auto current = BuildEffectiveConfigFields();
    std::vector<std::string> targets;
    const auto target = [&](const std::string& object, const std::string& key) {
        targets.push_back(object.empty() ? FieldPath("biasing", key) : ObjectFieldPath("biasing", object, key));
    };
    if (name == "enable" || name == "clear") target("", "enabled");
    std::string property;
    if (name.find("Factor") != std::string::npos) property = "factor";
    else if (name.find("onlyPrimary") != std::string::npos || name.find("OnlyPrimary") != std::string::npos) property = "only_primary";
    else if (name.find("applyToSecondaries") != std::string::npos || name.find("ApplyToSecondaries") != std::string::npos) property = "apply_to_secondaries";
    else if (name.find("MinWeight") != std::string::npos) property = "min_weight";
    else if (name.find("MaxInteractions") != std::string::npos) property = "max_interactions";
    else if (name.find("Volume") != std::string::npos) property = "volumes";
    else if (name.find("Process") != std::string::npos) property = "processes";
    // A successful no-op still supplies a new accepted origin for its target.
    const bool processForm = words.size() == 4 || name == "xs/addRule";
    if (words.size() >= 3 && processForm) {
        const auto identity = EffectiveRuleIdentity(words[1], words[2]);
        if (!property.empty()) target(identity, property);
        else if(name=="xs/addRule"){target(identity,"particle");target(identity,"process");}
    } else if (name == "xs/addVolume" && words.size() == 2) target("", "global_volumes");
    else if (words.size() >= 2) {
        std::string particle = words[1];
        if (name == "xs/addProcess" && config_.xsRules.size() == 1) particle = config_.xsRules.front().particleName;
        const auto legacy = LegacyIdentity(particle);
        if (!property.empty()) target(legacy, property);
        else if (name == "xs/addParticle") target(legacy, "particle");
        for (const auto& rule : BuildExpandedProcessRules(false)) if (rule.legacyGenerated && NormalizeParticleName(rule.particleName) == NormalizeParticleName(particle))
            if (!property.empty()) target(EffectiveRuleIdentity(rule.particleName, rule.processName), property == "processes" ? "process" : property);
    }
    const auto old = effectiveState_->fields;
    effectiveState_->Confirm(std::move(current), command, origin, false, targets);
    for (auto& field : effectiveState_->fields) {
        const auto previous = std::find_if(old.begin(), old.end(), [&](const Field& f) { return f.path == field.path; });
        const bool changed = previous == old.end() || previous->resolved.ToJson() != field.resolved.ToJson();
        const bool targeted=std::find(targets.begin(),targets.end(),field.path)!=targets.end();
        if(changed || targeted) {
            const auto key=field.path.substr(field.path.find_last_of('/')+1);
            bool derived=!targeted;
            if(!processForm)for(const auto& rule:BuildExpandedProcessRules(false))if(rule.legacyGenerated &&
                field.path.rfind("/biasing/objects/"+EscapePointerToken(EffectiveRuleIdentity(rule.particleName,rule.processName))+"/",0)==0)derived=true;
            if(derived) {
                field.requested_known=false;
                if(!field.origins.empty()){field.origins.back().kind="derived";field.origins.back().disposition="derived";}
                field.reason="Derived consequence of successful command; no explicit request for this property";
            } else if(words.size()>1) {
                if(key=="particle")field.requested=words[1];
                else if(key=="process")field.requested=words[2];
                else if(std::holds_alternative<bool>(field.resolved.data))field.requested=ConfigValue(words.back()).AsBool();
                else if(std::holds_alternative<double>(field.resolved.data))field.requested=ConfigValue(words.back()).AsDouble();
                else if(std::holds_alternative<std::int64_t>(field.resolved.data))field.requested=ConfigValue(words.back()).AsInt();
                else field.requested=words.back(); // one member requested by addProcess/addVolume
                field.requested_known=true;
            }
        }
    }
}
