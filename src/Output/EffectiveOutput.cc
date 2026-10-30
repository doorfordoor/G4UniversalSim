#include "Output/OutputManager.hh"
#include "Output/AnalysisOutput.hh"
#include "Config/EffectiveRuntime.hh"
#include "Config/ConfigValue.hh"
#include "Utils/StringUtils.hh"
#include <algorithm>

std::vector<effective_config::Field> OutputManager::ExportEffectiveConfigFields() const
{
    using namespace effective_config;
    std::vector<Field> fields;
    const auto add = [&](const char* name, Value value, std::initializer_list<const char*> keys) {
        auto field = effectiveState_->Make(FieldPath("output", name), std::move(value), "", "output", keys);
        if (std::string(name) == "dir") {
            // GetStringCompat chooses first nonempty dir, then outputDir.
            const auto& reader = effectiveState_->reader;
            std::string winner;
            for (const auto* key : {"dir", "outputdir"}) {
                for (const auto& d : reader.GetFields())
                    if (d.normalizedSection == "output" && d.normalizedKey == key && !d.value.empty()) winner = key;
                if (!winner.empty()) break;
            }
            for (auto& origin : field.origins) if (origin.kind == "main_ini" && StringUtils::ToLower(origin.key) != winner)
                origin.disposition = "shadowed";
            if (winner.empty()) { field.requested_known = false; field.origins.front().disposition = "accepted"; }
            else for(const auto& d:reader.GetFields())if(d.normalizedSection=="output" && d.normalizedKey==winner){
                field.requested=d.value;field.requested_known=true;
            }
        }
        // Requested is the accepted INI spelling/value. CLI may already have
        // changed resolved before Accept; attributing resolved to INI is false.
        for (const auto& old : effectiveState_->fields) if (old.path == field.path) {
            field.origins = old.origins; field.requested = old.requested; field.requested_known = old.requested_known;
        }
        fields.push_back(std::move(field));
    };
    add("dir", outputDir_, {"outputdir", "dir"});
    add("format", FormatName(GetFormat()), {"format"});
    fields.back().reason = FormatSelectionReason();
    // No INI consumer exists for this switch: only accepted Messenger commands.
    add("thread_suffix", threadSuffixEnabled_, {});
    return fields;
}
void OutputManager::AcceptEffectiveConfig(const IniReader& reader)
{
    auto previous=effectiveState_;
    auto candidate=std::make_shared<effective_config::ConsumerState>();candidate->reader=reader;candidate->generation=previous->generation;
    effectiveState_=candidate;
    try { candidate->Accept(reader,ExportEffectiveConfigFields()); }
    catch(...) { effectiveState_=previous;throw; }
}
void OutputManager::ConfirmEffectiveConfigMutation(const std::string& command, effective_config::Origin origin)
{
    const auto end=command.find_first_of(" \t");
    const auto name=StringUtils::ToLower(command.substr(0,end));
    const auto argument=end==std::string::npos?std::string():StringUtils::Trim(command.substr(end+1));
    std::vector<std::string> targets;
    if (name == "/aihl/output/setdir" || name == "/aihl/app/setoutputdir") targets = {"/output/dir"};
    else if (name == "/aihl/output/setthreadsuffix") targets = {"/output/thread_suffix"};
    else if (name == "/aihl/output/setformat") targets = {"/output/format"};
    else if (format_ == Format::Auto && (name == "/aihl/scoring/enable" ||
             name == "/aihl/scoring/hits" || name == "/aihl/scoring/eventedep")) {
        auto current = ExportEffectiveConfigFields();
        const auto previous = std::find_if(effectiveState_->fields.begin(), effectiveState_->fields.end(),
            [](const effective_config::Field& field) { return field.path == "/output/format"; });
        auto format = std::find_if(current.begin(), current.end(),
            [](const effective_config::Field& field) { return field.path == "/output/format"; });
        if (previous != effectiveState_->fields.end() && format != current.end() &&
            previous->resolved.ToJson() != format->resolved.ToJson()) {
            // Scoring changes the resolution, not the user's format policy.
            // Keep the auto request and record the accepted dependency command.
            origin.kind = "derived"; origin.disposition = "derived"; origin.raw = command;
            format->origins.push_back(std::move(origin));
            effectiveState_->Accept(effectiveState_->reader, std::move(current));
        }
        return;
    } else return;
    effectiveState_->Confirm(ExportEffectiveConfigFields(), command, origin, false, targets);
    for(auto& field:effectiveState_->fields)if(std::find(targets.begin(),targets.end(),field.path)!=targets.end()){
        if(field.path=="/output/thread_suffix")field.requested=ConfigValue(argument).AsBool();
        else field.requested=argument;
        if(field.path=="/output/format")field.reason=FormatSelectionReason();
        field.requested_known=true;
        for(std::size_t i=0;i+1<field.origins.size();++i)if(field.origins[i].disposition!="shadowed")field.origins[i].disposition="shadowed";
        // CLI carries the original argv value, not the synthetic setter used
        // by root to notify this consumer. Prior INI raw requests stay intact.
        if(origin.kind=="cli" && !field.origins.empty())field.origins.back().raw=argument;
    }
}
effective_config::Value OutputManager::ExportEffectiveConfigEvidence() const { return effectiveState_->Evidence(); }
void OutputManager::RecordEffectiveConfigState(const std::string& stage) const
{
    using namespace effective_config;
    for (const auto& field : ExportEffectiveConfigFields()) {
        auto receipt = Receipt(field.path, field.resolved, stage, "OutputManager actual writer state", "thread_applied", "unknown",
            "Writer state is observed independently of configuration acceptance; ROOT open state alone does not establish format application");
        auto& object = std::get<Value::Object>(receipt.data);
        object["manager_thread_id"] = threadId_;
        object["manager_run_id"] = runId_;
        object["initialized"] = initialized_;
        object["hit_file_open"] = IsHitFileOpen();
        object["event_edep_file_open"] = IsEventEdepFileOpen();
        object["root_open"] = AnalysisOutput::IsOpen();
        object["thread_suffix"] = threadSuffixEnabled_;
        object["hit_filename"] = GetHitFilename();
        object["event_edep_filename"] = GetEventEdepFilename();
        effectiveState_->Record(std::move(receipt));
    }
}
