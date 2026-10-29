#pragma once
#include "Config/EffectiveConfig.hh"
#include "Config/InputProvenance.hh"
#include <map>
#include <set>
#include <vector>
namespace effective_config {
inline const Value* ReceiptValue(const Value& value,const std::string& key) {
    const auto* object=std::get_if<Value::Object>(&value.data);if(!object)return nullptr;
    const auto found=object->find(key);return found==object->end()?nullptr:&found->second;
}
inline std::string ReceiptText(const Value& value,const std::string& key) {
    const auto* item=ReceiptValue(value,key);if(!item)return {};
    const auto* text=std::get_if<std::string>(&item->data);return text?*text:"";
}
struct RuntimeView { std::vector<Field> annotations; Value::Array evidence; };
inline RuntimeView ReduceRuntimeReceipts(const Snapshot& snapshot,const Value::Array& receipts,
                                 int thread,std::optional<std::int64_t> run) {
    struct Target { bool success=false, failed=false; Field field; };
    std::map<std::string,std::map<std::string,Target>> targets;
    RuntimeView result;
    struct Failure { std::string domain,target,source;std::uint64_t generation; };
    std::vector<Failure> failedBindings;
    const std::set<std::string> persistentStages{"geometry_construct","material_construct","field_construct","physics_cuts","physics_register","gps_apply","gdml_import"};
    for(auto receipt:receipts) {
        auto* object=std::get_if<Value::Object>(&receipt.data);if(!object)continue;
        const auto* owner=ReceiptValue(receipt,"thread_id");const auto* receiptRun=ReceiptValue(receipt,"run_id");
        if(!owner || owner->ToJson()!=Value(thread).ToJson())continue;
        const bool hasRun=receiptRun && receiptRun->ToJson()!="null";
        if(hasRun && (!run || receiptRun->ToJson()!=Value(*run).ToJson()))continue;
        const bool scoped=hasRun || persistentStages.count(ReceiptText(receipt,"stage"))!=0;
        const auto found=snapshot.Fields().find(ReceiptText(receipt,"path"));
        bool generationMatches=false,matches=false;
        if(found!=snapshot.Fields().end()) {
            const auto& field=found->second;const auto* generation=ReceiptValue(receipt,"configuration_generation");
            const auto* observed=ReceiptValue(receipt,"observed");
            generationMatches=generation && generation->ToJson()==Value(static_cast<std::int64_t>(field.configuration_generation)).ToJson();
            matches=scoped && generationMatches && field.resolved_known && observed && observed->ToJson()==field.resolved.ToJson() &&
                ReceiptText(receipt,"resolved_sha256")==input_provenance::Sha256(field.resolved.ToJson());
            // Different logical/physical targets are independent obligations.
            // A success on B can never erase a failure or unknown on A.
            if(scoped && generationMatches) {
                Value::Object identity;
                for(const auto* key:{"logical_volume","physical_volume","target","object","volume"})
                    if(const auto* value=ReceiptValue(receipt,key))identity[key]=*value;
                const auto identityText=Value(identity).ToJson();
                if(!identity.empty() && ReceiptText(receipt,"application_status")=="failed")
                    failedBindings.push_back({field.path.substr(0,field.path.find_last_of('/')),identityText,ReceiptText(receipt,"evidence_source"),field.configuration_generation});
                auto& target=targets[field.path][identityText];
                target.field=field;
                const auto status=ReceiptText(receipt,"application_status");const auto level=ReceiptText(receipt,"evidence_level");
                const bool validLevel=level=="thread_applied" || level=="kernel_constructed" || level=="run_validated";
                target.failed=target.failed || status=="failed";
                target.success=matches && !target.failed && field.application_status!=ApplicationStatus::Unknown &&
                    status=="applied" && validLevel && !ReceiptText(receipt,"evidence_source").empty();
                target.field.application_status=target.failed?ApplicationStatus::Failed:ApplicationStatus::Unknown;
                target.field.evidence_level=EvidenceLevel::None;target.field.applied_revision.reset();
                target.field.evidence_source=ReceiptText(receipt,"evidence_source");target.field.reason=ReceiptText(receipt,"reason");
                if(target.success) {
                    target.field.application_status=ApplicationStatus::Applied;
                    target.field.evidence_level=level=="thread_applied"?EvidenceLevel::ThreadApplied:level=="run_validated"?EvidenceLevel::RunValidated:EvidenceLevel::KernelConstructed;
                    target.field.applied_revision=field.revision;
                }
            }
        }
        (*object)["matches_resolved_value"]=matches;
        (*object)["scope_matches"]=scoped;(*object)["configuration_generation_matches"]=generationMatches;
        if(ReceiptText(receipt,"application_status")=="applied" && !matches) {
            (*object)["application_status"]="unknown";
            (*object)["observation_status"]="observed_independently_of_current_configuration_scope";
        }
        result.evidence.push_back(std::move(receipt));
    }
    // A failed binding for an object also invalidates other values observed
    // through that binding; observing the same field on a different LV cannot
    // turn a partially installed field object into a complete application.
    for(auto& item:targets)for(const auto& failure:failedBindings) {
        const auto& field=snapshot.Fields().at(item.first);
        if(field.configuration_generation!=failure.generation ||
           item.first.substr(0,item.first.find_last_of('/'))!=failure.domain)continue;
        auto& target=item.second[failure.target];target.failed=true;target.success=false;target.field=field;
        target.field.application_status=ApplicationStatus::Failed;target.field.evidence_level=EvidenceLevel::None;
        target.field.applied_revision.reset();target.field.evidence_source=failure.source;
        target.field.reason="Another binding of this object failed; successes on different targets cannot substitute";
    }
    for(const auto& item:targets) {
        const auto& obligations=item.second;
        const Target* selected=&obligations.begin()->second;
        for(const auto& target:obligations) {
            if(target.second.failed){selected=&target.second;break;}
            if(!target.second.success)selected=&target.second;
        }
        auto field=selected->field;
        if(field.application_status==ApplicationStatus::Unknown)
            field.reason="At least one current target lacks matching application evidence; other targets cannot substitute";
        result.annotations.push_back(std::move(field));
    }
    return result;
}

}
