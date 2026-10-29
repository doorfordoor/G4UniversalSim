#include "Scoring/ScoringManager.hh"
#include "Scoring/NielTable.hh"
#include "Scoring/EdepScorer.hh"
#include "Scoring/LETScorer.hh"
#include "Scoring/DoseScorer.hh"
#include "Scoring/FluenceScorer.hh"
#include "Scoring/DisplacementScorer.hh"
#include "Output/OutputManager.hh"
#include "Output/CsvWriter.hh"
#include "G4PhysicalVolumeStore.hh"
#include "G4VPhysicalVolume.hh"
#include "Config/EffectiveRuntime.hh"
#include "G4SystemOfUnits.hh"
#include "Utils/StringUtils.hh"

#include <algorithm>
#include <sstream>

std::vector<effective_config::Field> ScoringManager::ExportEffectiveConfigFields() const
{
    using namespace effective_config;
    std::vector<Field> result;
    const auto add = [&](const std::string& module, const std::string& object,
                         const std::string& name, Value value, const std::string& section,
                         const char* key, const std::string& unit = "") {
        const auto path = object.empty() ? FieldPath(module, name) : ObjectFieldPath(module, object, name);
        // The legacy reader only consumes scoring.* after a [scoring] section.
        const bool consumed = section.rfind("scoring", 0) != 0 || effectiveState_->reader.HasSection("scoring");
        Field field = effectiveState_->Make(path, std::move(value), unit,
                                            consumed ? section : "", {key});
        field.evidence_source = "ScoringManager accepted configuration readback";
        const auto previous = std::find_if(effectiveState_->fields.begin(), effectiveState_->fields.end(),
            [&](const Field& old) { return old.path == path; });
        if (previous != effectiveState_->fields.end()) {
            field.origins = previous->origins;
            field.requested = previous->requested;
            field.requested_known = previous->requested_known;
        } else if (!field.requested_known) {
            // These values are the actual constructor defaults, before any command.
            field.requested = field.resolved;
            field.requested_known = true;
            field.origins.front().raw = field.resolved.ToJson();
        }
        result.push_back(std::move(field));
    };
    add("scoring", "", "enabled", enabled_, "scoring", "enabled");
    add("scoring", "", "hits", hitOutputEnabled_, "scoring", "hits");
    add("scoring", "", "event_edep", eventEdepOutputEnabled_, "scoring", "event_edep");
    add("scoring", "", "edep", edepScoringEnabled_, "scoring", "edep");
    add("scoring", "", "let", letScoringEnabled_, "scoring", "let");
    add("scoring", "", "dose", doseScoringEnabled_, "scoring", "dose");
    add("scoring", "", "fluence", fluenceScoringEnabled_, "scoring", "fluence");
    add("scoring", "", "displacement", displacementScoringEnabled_, "scoring", "displacement");
    add("scoring", "", "auto_create_default_scorers", autoCreateDefaultScorers_, "scoring", "auto_create_default_scorers");
    add("scoring", "", "verbose", verboseLevel_, "scoring", "verbose");
    add("scoring", "edep", "raw_histogram", edepRawHistogramEnabled_, "scoring.edep", "raw_histogram");
    add("scoring", "edep", "weighted_histogram", edepWeightedHistogramEnabled_, "scoring.edep", "weighted_histogram");
    add("scoring", "edep", "volume_summary", edepVolumeSummaryEnabled_, "scoring.edep", "volume_summary");
    add("scoring", "edep", "particle_summary", edepParticleSummaryEnabled_, "scoring.edep", "particle_summary");
    for (bool weighted : {false, true}) {
        const auto& histogram = weighted ? weightedEdepHistogram_ : rawEdepHistogram_;
        const std::string object = weighted ? "weighted_edep_histogram" : "edep_histogram";
        add("scoring", object, "bins", histogram.bins, "scoring.edep", "bins");
        add("scoring", object, "min", histogram.min / MeV, "scoring.edep", "min", "MeV");
        add("scoring", object, "max", histogram.max / MeV, "scoring.edep", "max", "MeV");
    }
    add("scoring", "let", "particles", List({letParticles_.begin(), letParticles_.end()}), "scoring.let", "particles");
    for (const auto& item : nielTables_) {
        const auto& table = *item.second;
        // Lookup is case insensitive; canonicalization at BeginRun cannot rename the object.
        const std::string key = StringUtils::ToLower(item.first);
        const std::string object = "niel:" + key;
        add("scoring", object, "file", table.GetFile(), "scoring.displacement", key.c_str());
        auto& field = result.back();
        Origin input;
        input.kind = "external_input";
        input.file = table.GetFile();
        input.input_sha256 = table.GetInputSha256();
        input.disposition = "derived";
        if (std::none_of(field.origins.begin(), field.origins.end(), [&](const Origin& old) {
            return old.kind == input.kind && old.file == input.file && old.input_sha256 == input.input_sha256;
        })) field.origins.push_back(input);
        add("scoring", object, "input_sha256", table.GetInputSha256(), "", "");
        add("scoring", object, "energy_min", table.MinEnergy() / MeV, "", "", "MeV");
        add("scoring", object, "energy_max", table.MaxEnergy() / MeV, "", "", "MeV");
        add("scoring", object, "points", static_cast<std::int64_t>(table.Size()), "", "");
        Value::Array nodes;
        for(std::size_t i=0;i<table.Size();++i)nodes.emplace_back(Value::Array{table.Energies()[i]/MeV,table.Values()[i]});
        add("scoring", object, "data",std::move(nodes),"","","MeV,MeV cm2/g");
        add("scoring", object, "interpolation","log_log_positive_nodes_else_linear","","");
        add("scoring", object, "outside","unavailable_count_out_of_range","","");
        for (std::size_t i = result.size() - 7; i < result.size(); ++i) {
            result[i].requested_known = false;
            result[i].origins = {input};
            result[i].reason = "Derived from the same accepted NIEL input bytes";
        }
    }
    const auto& trajectory = trajectories_.GetSettings();
    add("trajectories", "", "events", trajectory.events, "output", "trajectories");
    add("trajectories", "", "min_energy", trajectory.minEnergy / MeV, "output", "trajectory_min_energy", "MeV");
    add("trajectories", "", "max_points", static_cast<std::int64_t>(trajectory.maxPoints), "output", "trajectory_max_points");
    add("phase_space", "", "volume", phaseSpaceVolume_, "phase_space", "volume");
    add("phase_space", "", "particles", List({phaseSpaceParticles_.begin(), phaseSpaceParticles_.end()}), "phase_space", "particles");
    add("phase_space", "", "kill", phaseSpaceKill_, "phase_space", "kill");
    return result;
}

void ScoringManager::ConfirmEffectiveConfigMutation(const std::string& command, effective_config::Origin origin)
{
    using namespace effective_config;
    std::istringstream words(command);
    std::string name;
    words >> name;
    const std::map<std::string, std::string> scalar{
        {"enable", "enabled"}, {"hits", "hits"}, {"eventEdep", "event_edep"},
        {"edep", "edep"}, {"let", "let"}, {"dose", "dose"}, {"fluence", "fluence"},
        {"autoCreateScorers", "auto_create_default_scorers"}, {"verbose", "verbose"}};
    const std::string prefix = "/AIHL/scoring/";
    if (name.rfind(prefix, 0) != 0) return;
    name = name.substr(prefix.size());
    auto current = ExportEffectiveConfigFields();
    for (auto& field : current) {
        const auto found = scalar.find(name);
        const bool touched = (found != scalar.end() && field.path == FieldPath("scoring", found->second)) ||
            (name == "setEdepHistogram" && field.path.rfind("/scoring/objects/edep_histogram/", 0) == 0) ||
            (name == "setWeightedEdepHistogram" && field.path.rfind("/scoring/objects/weighted_edep_histogram/", 0) == 0);
        if (!touched) continue;
        for(auto& previous:field.origins)if(previous.disposition=="accepted")previous.disposition="shadowed";
        origin.raw = command;
        field.origins.push_back(origin);
        field.requested = command;
        field.requested_known = true;
    }
    effectiveState_->Accept(effectiveState_->reader, std::move(current));
}

void ScoringManager::SuppressModule(bool trajectoriesOnly, const effective_config::Origin& origin)
{
    if (trajectoriesOnly) {
        auto settings = trajectories_.GetSettings(); settings.events = 0;
        trajectories_ = TrajectoryRecorder(settings);
    } else {
        Enable(false); EnableHitOutput(false); EnableEventEdepOutput(false);
        // Phase-space boundary output and trajectories are independent of
        // the sensitive-hit scorer gate (BeginRun initializes both separately).
    }
    auto current = ExportEffectiveConfigFields();
    for (auto& field : current) {
        const auto old = std::find_if(effectiveState_->fields.begin(), effectiveState_->fields.end(),
            [&](const effective_config::Field& value) { return value.path == field.path; });
        if (old != effectiveState_->fields.end() && old->resolved.ToJson() != field.resolved.ToJson()) {
            for(auto& previous:field.origins)if(previous.disposition=="accepted")previous.disposition="shadowed";
            field.origins.push_back(origin);
            field.reason = "Explicit module off suppresses execution; original request remains in the origin chain";
        }
    }
    effectiveState_->Accept(effectiveState_->reader, std::move(current));
}

void ScoringManager::RecordEffectiveConfigApplied(int runId, int threadId)
{
    using namespace effective_config;
    // The output filename id is a separate namespace from the Geant4 id
    // (sequential execution maps a negative Geant4 id to output t0).
    const int actualThread=G4Threading::G4GetThreadId();
    const auto record=[&](const std::string& path,Value observed,const std::string& source,
                         const std::string& status="applied",const std::string& reason="") {
        auto receipt=Receipt(path,std::move(observed),"run_begin",source,"thread_applied",status,reason);
        auto& details=std::get<Value::Object>(receipt.data);
        details["run_id"]=runId;details["thread_id"]=actualThread;details["manager_thread_id"]=threadId;
        effectiveState_->Record(std::move(receipt));
    };
    Value::Array inventory;
    for(const auto& scorer:scorers_)inventory.emplace_back(Value::Object{{"name",scorer->GetName()},{"enabled",scorer->IsEnabled()}});
    auto gate=Receipt("/scoring/enabled",enabled_,"run_begin","Successful ScoringManager::BeginRun execution gate","thread_applied");
    auto& gateDetails=std::get<Value::Object>(gate.data);
    gateDetails["run_id"]=runId;gateDetails["thread_id"]=actualThread;gateDetails["manager_thread_id"]=threadId;
    gateDetails["scorers"]=std::move(inventory);effectiveState_->Record(std::move(gate));
    const auto* edep=dynamic_cast<const EdepScorer*>(GetScorer("edep"));
    const auto* let=dynamic_cast<const LETScorer*>(GetScorer("let"));
    const auto* dose=dynamic_cast<const DoseScorer*>(GetScorer("dose"));
    const auto* fluence=dynamic_cast<const FluenceScorer*>(GetScorer("fluence"));
    const auto* displacement=dynamic_cast<const DisplacementScorer*>(GetScorer("displacement"));
    if(enabled_) {
        const auto inventoryEnabled=[&](const char* name,const ScorerBase* scorer) {
            record(FieldPath("scoring",name),scorer && scorer->IsEnabled(),"Actual typed thread-owned scorer inventory after BeginRun");
        };
        inventoryEnabled("edep",edep);inventoryEnabled("let",let);inventoryEnabled("dose",dose);
        inventoryEnabled("fluence",fluence);inventoryEnabled("displacement",displacement);
        if(edep && edep->IsEnabled()) {
            record(ObjectFieldPath("scoring","edep","raw_histogram"),edep->IsRawHistogramEnabled(),"Actual EdepScorer configuration getter");
            record(ObjectFieldPath("scoring","edep","weighted_histogram"),edep->IsWeightedHistogramEnabled(),"Actual EdepScorer configuration getter");
            record(ObjectFieldPath("scoring","edep","volume_summary"),edep->IsVolumeSummaryEnabled(),"Actual EdepScorer configuration getter");
            record(ObjectFieldPath("scoring","edep","particle_summary"),edep->IsParticleSummaryEnabled(),"Actual EdepScorer configuration getter");
        }
        if(let && let->IsEnabled())record(ObjectFieldPath("scoring","let","particles"),List({let->GetParticles().begin(),let->GetParticles().end()}),"Actual LETScorer particle-filter getter");
    }
    const auto& trajectory=trajectories_.GetSettings();
    if(trajectories_.IsEnabled()) {
        record("/trajectories/events",trajectory.events,"Actual thread-owned TrajectoryRecorder settings after successful BeginRun");
        record("/trajectories/min_energy",trajectory.minEnergy/MeV,"Actual TrajectoryRecorder minimum-energy getter");
        record("/trajectories/max_points",static_cast<std::int64_t>(trajectory.maxPoints),"Actual TrajectoryRecorder point-limit getter");
    }
    if(phaseSpaceWriter_ && phaseSpaceWriter_->IsOpen()) {
        const auto* physical=G4PhysicalVolumeStore::GetInstance()->GetVolume(phaseSpaceVolume_,false);
        if(physical)record("/phase_space/volume",std::string(physical->GetName()),"Validated actual physical volume with open thread-owned phase-space writer");
    }
    // Explain all unobserved fields without copying their Manager values into
    // runtime receipts. In particular there are no Edep histogram-bin or NIEL
    // binding getters in the scorer interfaces, and an open writer alone does
    // not prove event/hit dispatch or future physical scoring.
    for(const auto& field:ExportEffectiveConfigFields()) {
        const bool histogram=field.path.find("edep_histogram/")!=std::string::npos;
        const bool niel=field.path.find("/objects/niel:")!=std::string::npos;
        const bool dispatch=field.path=="/scoring/hits" || field.path=="/scoring/event_edep" ||
            field.path=="/phase_space/particles" || field.path=="/phase_space/kill" ||
            field.path=="/scoring/auto_create_default_scorers" || field.path=="/scoring/verbose";
        if(!histogram && !niel && !dispatch)continue;
        Value::Object unknown{{"path",field.path},{"stage","run_begin"},{"run_id",runId},{"thread_id",actualThread},
            {"application_status","unknown"},{"evidence_level","none"},
            {"evidence_source","No independent runtime getter for this configuration field"},
            {"reason",histogram?"EdepScorer does not expose histogram binning":niel?"DisplacementScorer does not expose its table bindings":"Configuration acceptance does not prove event dispatch"}};
        effectiveState_->Record(std::move(unknown));
    }
}

effective_config::Value ScoringManager::ExportEffectiveConfigEvidence() const
{
    return effectiveState_->Evidence();
}
