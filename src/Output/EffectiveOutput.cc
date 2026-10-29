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
    add("format", FormatName(format_), {"format"});
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
    const auto name=command.substr(0,end);
    const auto argument=end==std::string::npos?std::string():command.substr(end+1);
    std::vector<std::string> targets;
    if (name == "/AIHL/output/setDir" || name == "/AIHL/app/setOutputDir") targets = {"/output/dir"};
    else if (name == "/AIHL/output/setThreadSuffix") targets = {"/output/thread_suffix"};
    else return;
    effectiveState_->Confirm(ExportEffectiveConfigFields(), command, origin, false, targets);
    for(auto& field:effectiveState_->fields)if(std::find(targets.begin(),targets.end(),field.path)!=targets.end()){
        if(field.path=="/output/thread_suffix")field.requested=ConfigValue(StringUtils::Trim(argument)).AsBool();
        else field.requested=argument;
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
