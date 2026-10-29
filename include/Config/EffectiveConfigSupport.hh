#pragma once
#include "Config/EffectiveConfig.hh"
#include "Config/IniReader.hh"
#include "Config/InputProvenance.hh"
#include <algorithm>
#include <mutex>
#include <memory>
#include <set>
namespace effective_config {
inline Value List(const std::vector<std::string>& values) { Value::Array a;for(const auto& v:values)a.emplace_back(v);return a; }
inline Value Numbers(const std::vector<double>& values, double unit=1) { Value::Array a;for(auto v:values)a.emplace_back(v/unit);return a; }
// Shared only for immutable accepted config reads and mutex-protected receipts.
struct ConsumerState {
 ConsumerState() = default;
 ConsumerState(const ConsumerState& other) : reader(other.reader), accepted(other.accepted), fields(other.fields), generation(other.generation) {}
 std::shared_ptr<ConsumerState> Clone() const { return std::make_shared<ConsumerState>(*this); }
 IniReader reader;
 bool accepted=false;
 std::vector<Field> fields;
 std::uint64_t generation=0;
 void Accept(const IniReader& input,std::vector<Field> current) {
  reader=input; ++generation;
  for(auto& field:current)field.configuration_generation=generation;
  fields=std::move(current);accepted=true;
 }
 mutable std::mutex mutex;
 mutable Value::Array evidence;
 Field Make(const std::string& path, Value value, const std::string& unit,
            const std::string& section, std::initializer_list<const char*> keys) const {
  Field f;f.path=path;f.resolved=std::move(value);f.unit=unit;f.configuration_generation=generation;
  f.requested_known=false;f.evidence_level=EvidenceLevel::ManagerAccepted;
  f.reason="Accepted Manager configuration; runtime application is recorded separately";
  Origin initial;initial.kind="default";initial.disposition="accepted";f.origins.push_back(initial);
  const auto declarations=reader.GetDeclarations();
  // Parser applies each winning key according to consumer order, not file order.
  // Keep overwritten duplicates as shadowed and preserve each alias's spelling.
  for(const char* key:keys) {
   std::vector<IniFieldInfo> matches;
   for(const auto& d:declarations)if(d.normalizedSection==section && d.normalizedKey==key)matches.push_back(d);
   for(std::size_t i=0;i<matches.size();++i){const auto& d=matches[i];Origin o;
    o.kind="main_ini";o.file=reader.GetFilename();o.line=d.lineNumber;o.section=d.originalSection;
    o.key=d.originalKey;o.raw=d.value;o.alias=d.originalKey;o.input_sha256=reader.GetInputSha256();
    o.disposition=i+1==matches.size()?"accepted":"shadowed";
    f.origins.push_back(o);if(i+1==matches.size()){f.requested=d.value;f.requested_known=true;}
   }
  }
  if(f.origins.size()>1)f.origins.front().disposition="shadowed";
  return f;
 }
 void Confirm(std::vector<Field> current,const std::string& command,Origin origin,bool unknown=false,
              const std::vector<std::string>& targetPaths={}) {
  origin.raw=command;
  for(auto& f:current) {
   auto old=std::find_if(fields.begin(),fields.end(),[&](const Field& x){return x.path==f.path;});
   if(old!=fields.end()) f.origins=old->origins;
   bool changed=old==fields.end() || old->resolved.ToJson()!=f.resolved.ToJson();
   const bool targeted=std::find(targetPaths.begin(),targetPaths.end(),f.path)!=targetPaths.end();
   if(!changed && !targeted && old!=fields.end()) {
    f.requested=old->requested;f.requested_known=old->requested_known;
   }
   if(!changed && old!=fields.end()) {
    f.application_status=old->application_status;f.evidence_level=old->evidence_level;f.reason=old->reason;
   }
   if(changed || unknown || targeted) {
    if(!f.origins.empty())f.origins.back().disposition="shadowed";
    f.origins.push_back(origin);f.requested=command;f.requested_known=true;
   }
   if(unknown){f.application_status=ApplicationStatus::Unknown;f.reason="Native command accepted; Manager cache is not GPS state";}
  }
  ++generation; for(auto& field:current)field.configuration_generation=generation;
  fields=std::move(current);accepted=true;
 }
 void Record(Value receipt) const {
  auto* object=std::get_if<Value::Object>(&receipt.data);
  if(object){
   (*object)["configuration_generation"]=static_cast<std::int64_t>(generation);
   const auto path=object->find("path");
   if(path!=object->end())if(const auto* name=std::get_if<std::string>(&path->second.data))
    for(const auto& field:fields)if(field.path==*name){
     if(field.resolved_known)(*object)["resolved_sha256"]=input_provenance::Sha256(field.resolved.ToJson());
     break;
    }
  }
  std::lock_guard<std::mutex> lock(mutex);evidence.push_back(std::move(receipt));
 }
 Value Evidence() const {std::lock_guard<std::mutex> lock(mutex);return evidence;}
};
}
