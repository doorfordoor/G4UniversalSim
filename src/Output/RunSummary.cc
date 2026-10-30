#include "Output/RunSummary.hh"

#include "Output/AnalysisOutput.hh"
#include "Output/CsvWriter.hh"
#include "Utils/FileUtils.hh"

#include <fstream>
#include <algorithm>
#include <cmath>
#include <limits>
#include <set>
#include <cstdlib>
#include <filesystem>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace {

std::string PathForSummary(const std::string& nativePath)
{
    return nativePath.empty() ? nativePath : std::filesystem::path(nativePath).u8string();
}

std::string GeneratedFileSchema(const std::string& path)
{
    const std::string name = FileUtils::Filename(path);
    const auto matches = [&name](const std::string& stem) {
        return name == stem + ".csv" ||
               name.rfind(stem + "_t", 0) == 0 ||
               name.rfind(stem + "_r", 0) == 0;
    };
    if (name == "run_summary.txt") return "run_summary_v1";
    if (name == "run_metadata.json") return "run_metadata_json_v1";
    if (name == "effective_config_configure.json" || name == "effective_config_finalization.json" ||
        ((name.rfind("effective_config_run_", 0) == 0 || name.rfind("effective_config_final_r", 0) == 0) &&
         name.size() > 5 && name.compare(name.size() - 5, 5, ".json") == 0))
        return "g4usim_effective_config_v1";
    if (name == "scoring_mesh.csv" || (name.rfind("scoring_mesh_r", 0) == 0 &&
                                       name.size() > 4 && name.compare(name.size() - 4, 4, ".csv") == 0))
        return "scoring_mesh_csv_v2";
    if (name == "scorer_statistics.csv" || (name.rfind("scorer_statistics_r", 0) == 0 &&
                                            name.size() > 4 && name.compare(name.size() - 4, 4, ".csv") == 0))
        return "scorer_statistics_csv_v2";
    if (name.size() > 5 && name.compare(name.size() - 5, 5, ".root") == 0 &&
        name.rfind("g4usim", 0) == 0) return "g4usim_root_v" + std::to_string(AnalysisOutput::kRootSchemaVersion);
    std::ifstream input(path);
    std::string header;
    if (!input || !std::getline(input, header)) return "unknown";
    if (!header.empty() && header.back() == '\r') header.pop_back();
    if (matches("hits")) {
        if (header == "runID,eventID,trackID,parentID,particle,edep_MeV,ndep_MeV,stepLength_mm,"
                      "x0_mm,y0_mm,z0_mm,x1_mm,y1_mm,z1_mm,px,py,pz,kineticEnergy_MeV,"
                      "process,volume,weight") return "hits_csv_v3";
        if (header == "runID,eventID,trackID,parentID,particle,edep,ndep,stepLength,"
                      "x0,y0,z0,x1,y1,z1,px,py,pz,kineticEnergy,process,volume,weight,LETcalc,LETstep")
            return "hits_csv_v2";
    }
    if (matches("event_edep")) {
        if (header == "runID,eventID,raw_edep_MeV,weighted_edep_MeV") return "event_edep_csv_v3";
        if (header == "runID,eventID,raw_edep,weighted_edep") return "event_edep_csv_v2";
    }
    if (matches("hist_edep_raw") || matches("hist_edep_weighted")) {
        if (header == "bin,low_edge_MeV,high_edge_MeV,center_MeV,count") return "histogram1d_csv_v3";
        if (header == "bin,low_edge,high_edge,center,count") return "histogram1d_csv_v2";
    }
    if (matches("edep_volume_summary") || matches("edep_particle_summary")) {
        if (header == "name,raw_edep_MeV,weighted_edep_MeV,raw_edep_sum_sq_MeV2,weighted_edep_sum_sq_MeV2,"
                      "n_events") return "edep_summary_csv_v4";
        if (header == "name,raw_edep_MeV,weighted_edep_MeV") return "edep_summary_csv_v3";
        if (header == "name,raw_edep,weighted_edep") return "edep_summary_csv_v2";
    }
    if (matches("dose_volume_summary")) {
        if (header == "runID,volume_path,volume_name,mass_kg,raw_edep_MeV,weighted_edep_MeV,"
                      "raw_dose_Gy,weighted_dose_Gy") return "dose_volume_csv_v1";
        if (header == "runID,volume_path,volume_name,mass_kg,raw_edep_MeV,weighted_edep_MeV,"
                      "raw_dose_Gy,weighted_dose_Gy,raw_edep_sum_sq_MeV2,weighted_edep_sum_sq_MeV2,"
                      "n_events") return "dose_volume_csv_v2";
    }
    if (matches("phase_space")) {
        if (header == "runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,"
                      "kineticEnergy_MeV,time_ns,weight") return "phase_space_csv_v1";
    }
    if (matches("let_volume_summary")) {
        if (header == "runID,volume_path,volume_name,particles,steps,sum_wl_mm,sum_wSl_MeV,"
                      "sum_wS2l_MeV2_per_mm,let_t_keV_per_um,let_d_keV_per_um") return "let_volume_csv_v1";
        if (header == "runID,volume_path,volume_name,particles,steps,sum_wl_mm,sum_wSl_MeV,"
                      "sum_wS2l_MeV2_per_mm,let_t_keV_per_um,let_d_keV_per_um,sum_sq_wl_mm2,"
                      "sum_sq_wSl_MeV2,sum_sq_wS2l_MeV4_per_mm2,sum_wl_x_wSl_MeV_mm,"
                      "sum_wSl_x_wS2l_MeV3_per_mm,n_events") return "let_volume_csv_v2";
    }
    if (matches("displacement_volume_summary")) {
        if (header == "runID,volume_path,volume_name,particle,niel_table,volume_mm3,track_length_mm,"
                      "out_of_range_track_length_mm,ddd_MeV_g,ddd_sum_sq_MeV2_g2,n_events")
            return "displacement_volume_csv_v1";
    }
    if (matches("fluence_volume_summary")) {
        if (header == "runID,volume_path,volume_name,volume_mm3,raw_track_length_mm,"
                      "weighted_track_length_mm,raw_fluence_mm-2,weighted_fluence_mm-2") return "fluence_volume_csv_v1";
        if (header == "runID,volume_path,volume_name,volume_mm3,raw_track_length_mm,"
                      "weighted_track_length_mm,raw_fluence_mm-2,weighted_fluence_mm-2,"
                      "raw_track_length_sum_sq_mm2,weighted_track_length_sum_sq_mm2,n_events")
            return "fluence_volume_csv_v2";
    }
    return "unknown";
}

}  // namespace

void RunSummary::Set(const std::string& key, const std::string& value)
{
    values_[key] = value;
}

void RunSummary::Set(const std::string& key, int value)
{
    values_[key] = std::to_string(value);
}

void RunSummary::Set(const std::string& key, std::int64_t value)
{
    values_[key] = std::to_string(value);
}

void RunSummary::Set(const std::string& key, double value)
{
    std::ostringstream oss;
    oss << std::setprecision(12) << value;
    values_[key] = oss.str();
}

void RunSummary::SetPath(const std::string& key, const std::string& nativePath)
{
    values_[key] = PathForSummary(nativePath);
}

void RunSummary::SetBool(const std::string& key, bool value)
{
    values_[key] = value ? "true" : "false";
}

bool RunSummary::Has(const std::string& key) const
{
    return values_.find(key) != values_.end();
}

std::string RunSummary::Get(const std::string& key, const std::string& defaultValue) const
{
    const auto it = values_.find(key);
    return it == values_.end() ? defaultValue : it->second;
}

void RunSummary::AddMessage(const std::string& message)
{
    messages_.push_back(message);
}

void RunSummary::AddWarning(const std::string& warning)
{
    warnings_.push_back(warning);
}

void RunSummary::AddRun(int runId, std::int64_t plannedEvents, std::int64_t completedEvents)
{
    runs_.push_back({runId, plannedEvents, completedEvents});
}

void RunSummary::SetGeneratedFiles(const std::vector<std::string>& files)
{
    generatedFiles_ = files;
}

const std::vector<RunSummary::RunRecord>& RunSummary::GetRuns() const
{
    return runs_;
}

void RunSummary::WriteText(const std::string& filename) const
{
    const std::string parent = FileUtils::ParentPath(filename);
    if (!parent.empty()) {
        FileUtils::CreateDirectories(parent);
    }

    std::ofstream out(filename);
    if (!out) {
        throw std::runtime_error("Failed to open run summary file: '" + filename + "'");
    }

    out << "Run Summary\n";
    out << "===========\n\n";

    out << "[Values]\n";
    for (const auto& item : values_) {
        out << item.first << " = " << item.second << '\n';
    }

    out << "\n[Runs]\n";
    for (std::size_t index = 0; index < runs_.size(); ++index) {
        const auto& run = runs_[index];
        out << "run_" << index << "_id = " << run.runId << '\n';
        out << "run_" << index << "_planned_events = " << run.plannedEvents << '\n';
        out << "run_" << index << "_completed_events = " << run.completedEvents << '\n';
    }

    out << "\n[GeneratedFiles]\n";
    for (const std::string& file : generatedFiles_) {
        out << "- " << PathForSummary(file) << '\n';
    }

    out << "\n[GeneratedFileSchemas]\n";
    for (std::size_t index = 0; index < generatedFiles_.size(); ++index) {
        out << "file_" << index << "_path = " << PathForSummary(generatedFiles_[index]) << '\n';
        out << "file_" << index << "_schema = " << GeneratedFileSchema(generatedFiles_[index]) << '\n';
    }

    out << "\n[Messages]\n";
    for (const std::string& message : messages_) {
        out << "- " << message << '\n';
    }

    out << "\n[Warnings]\n";
    for (const std::string& warning : warnings_) {
        out << "- " << warning << '\n';
    }

    if (!out) {
        throw std::runtime_error("Failed to write run summary file: '" + filename + "'");
    }
    out.flush();
    if (!out) {
        throw std::runtime_error("Failed to flush run summary file: '" + filename + "'");
    }
    out.close();
    if (!out) {
        throw std::runtime_error("Failed to close run summary file: '" + filename + "'");
    }
}

void RunSummary::WriteCSV(const std::string& filename) const
{
    CsvWriter writer(filename);
    writer.WriteHeader({"type", "key", "value"});

    for (const auto& item : values_) {
        writer.WriteRow({"value", item.first, item.second});
    }
    for (std::size_t index = 0; index < runs_.size(); ++index) {
        const auto& run = runs_[index];
        writer.WriteRow({"run", "run_" + std::to_string(index) + "_id", std::to_string(run.runId)});
        writer.WriteRow({"run", "run_" + std::to_string(index) + "_planned_events", std::to_string(run.plannedEvents)});
        writer.WriteRow({"run", "run_" + std::to_string(index) + "_completed_events", std::to_string(run.completedEvents)});
    }
    for (const std::string& file : generatedFiles_) {
        writer.WriteRow({"generated_file", "", PathForSummary(file)});
        writer.WriteRow({"generated_file_schema", GeneratedFileSchema(file), PathForSummary(file)});
    }
    for (const std::string& message : messages_) {
        writer.WriteRow({"message", "", message});
    }
    for (const std::string& warning : warnings_) {
        writer.WriteRow({"warning", "", warning});
    }
    writer.Close();
}

namespace {
std::string JsonString(const std::string& value)
{
    std::ostringstream out;
    out << '"';
    for (const unsigned char c : value) {
        switch (c) {
        case '"': out << "\\\""; break;
        case '\\': out << "\\\\"; break;
        case '\n': out << "\\n"; break;
        case '\r': out << "\\r"; break;
        case '\t': out << "\\t"; break;
        default:
            if (c < 0x20) {
                out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(c)
                    << std::dec << std::setfill(' ');
            } else {
                out << static_cast<char>(c);
            }
        }
    }
    out << '"';
    return out.str();
}
bool LowerHex(const std::string& text, std::size_t length)
{
    return text.size() == length && text.find_first_not_of("0123456789abcdef") == std::string::npos;
}

const effective_config::Value::Object& Object(const effective_config::Value& value, const char* name)
{
    const auto* object = std::get_if<effective_config::Value::Object>(&value.data);
    if (!object) throw std::invalid_argument(std::string("Invalid provenance object: ") + name);
    return *object;
}
const effective_config::Value& Required(const effective_config::Value::Object& object, const char* key)
{
    const auto found = object.find(key);
    if (found == object.end()) throw std::invalid_argument(std::string("Missing provenance field: ") + key);
    return found->second;
}
std::string Text(const effective_config::Value::Object& object, const char* key)
{
    const auto* text = std::get_if<std::string>(&Required(object,key).data);
    if (!text) throw std::invalid_argument(std::string("Provenance field must be text: ") + key);
    return *text;
}
void FiniteJson(const effective_config::Value& value)
{
    if (const auto* real=std::get_if<double>(&value.data)) {
        if (!std::isfinite(*real)) throw std::invalid_argument("Nonfinite provenance JSON value");
    } else if (const auto* array=std::get_if<effective_config::Value::Array>(&value.data)) {
        for (const auto& item:*array) FiniteJson(item);
    } else if (const auto* object=std::get_if<effective_config::Value::Object>(&value.data)) {
        for (const auto& item:*object) FiniteJson(item.second);
    }
}
void ValidateProvenance(const effective_config::Value& value)
{
    FiniteJson(value);
    const auto& object=Object(value,"provenance");
    if (Text(object,"schema")!="g4usim_provenance_v1" || !LowerHex(Text(object,"execution_id"),32))
        throw std::invalid_argument("Unsupported provenance schema or execution ID");
    if (Text(object,"input_coverage")!="project_readers_observed" ||
        Text(object,"input_observation")!="bytes_read_not_semantic_acceptance")
        throw std::invalid_argument("Unsupported input observation contract");
    const auto& build=Object(Required(object,"build"),"build");
    const auto commit=Text(build,"git_commit");
    if (commit!="unknown" && !LowerHex(commit,40) && !LowerHex(commit,64))
        throw std::invalid_argument("Invalid build Git commit");
    const auto state=Text(build,"git_source_state");
    if (state!="clean" && state!="dirty" && state!="unknown") throw std::invalid_argument("Invalid build Git state");
    const auto fingerprint=Text(build,"source_fingerprint");
    if (fingerprint!="unknown" && !LowerHex(fingerprint,64)) throw std::invalid_argument("Invalid source fingerprint");
    for (const char* key:{"compiler_id","compiler_version","configuration","geant4_version"})
        if (Text(build,key).empty()) throw std::invalid_argument("Build identity must use unknown, not empty values");
    const auto* exclusions=std::get_if<effective_config::Value::Array>(&Required(object,"input_exclusions").data);
    if (!exclusions || exclusions->size()<2) throw std::invalid_argument("Input exclusions must describe uncovered IO");
    for (const auto& item:*exclusions) {
        const auto* text=std::get_if<std::string>(&item.data);
        if (!text || text->empty()) throw std::invalid_argument("Invalid input exclusion");
    }
    const auto* inputs=std::get_if<effective_config::Value::Array>(&Required(object,"inputs").data);
    if (!inputs) throw std::invalid_argument("Provenance inputs must be an array");
    std::int64_t previous=0;
    for (const auto& input:*inputs) {
        const auto& row=Object(input,"input");
        const auto* sequence=std::get_if<std::int64_t>(&Required(row,"sequence").data);
        if (!sequence || previous==std::numeric_limits<std::int64_t>::max() || *sequence!=previous+1)
            throw std::invalid_argument("Input observation sequence must be continuous from 1");
        previous=*sequence;
        const auto path=Text(row,"path");
        if (path.empty())throw std::invalid_argument("Input path must use an explicit placeholder when unknown");
        for (const char* key:{"kind","role","capture_method"})
            if (Text(row,key).empty()) throw std::invalid_argument("Empty input observation classification");
        const auto status=Text(row,"status");
        const auto reason=Text(row,"reason");
        const auto& sha=Required(row,"sha256");const auto& size=Required(row,"size_bytes");
        if (status=="recorded") {
            const auto* count=std::get_if<std::int64_t>(&size.data);
            if (path.empty() || !LowerHex(Text(row,"sha256"),64) || !count || *count<0)
                throw std::invalid_argument("Recorded input requires original SHA256 and nonnegative byte size");
        } else if (status=="unobserved") {
            if (!std::holds_alternative<std::nullptr_t>(sha.data) ||
                !std::holds_alternative<std::nullptr_t>(size.data) || reason.empty())
                throw std::invalid_argument("Unobserved input must retain null digest/size and a reason");
        } else throw std::invalid_argument("Unknown input observation status");
    }
}
const char* ScopeName(RunSummary::ArtifactScope scope)
{
    switch (scope) {
    case RunSummary::ArtifactScope::Process:return "process";
    case RunSummary::ArtifactScope::Run:return "run";
    case RunSummary::ArtifactScope::Thread:return "thread";
    }
    throw std::invalid_argument("Invalid artifact scope");
}
void ValidateArtifact(const RunSummary::ArtifactEvidence& file)
{
    ScopeName(file.scope);
    if (file.path.empty() || !LowerHex(file.execution_id,32)) throw std::invalid_argument("Invalid artifact path/execution identity");
    if ((file.scope==RunSummary::ArtifactScope::Process && (file.run_id || file.thread_id)) ||
        (file.scope==RunSummary::ArtifactScope::Run && (!file.run_id || *file.run_id<0 || file.thread_id)) ||
        (file.scope==RunSummary::ArtifactScope::Thread && (!file.run_id || *file.run_id<0 || !file.thread_id || *file.thread_id<0)))
        throw std::invalid_argument("Artifact scope and run/thread identity disagree");
    if (file.integrity_status=="hashed") {
        if (!file.sha256 || !LowerHex(*file.sha256,64) || !file.size_bytes ||
            *file.size_bytes>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))
            throw std::invalid_argument("Hashed artifact requires SHA256 and nonnegative integer byte size");
    } else if (file.integrity_status=="unavailable" || file.integrity_status=="self_reference_excluded") {
        if (file.sha256 || file.size_bytes || file.reason.empty())
            throw std::invalid_argument("Unhashed artifact requires null digest/size and reason");
        if (file.integrity_status=="self_reference_excluded" &&
            (FileUtils::Filename(file.path)!="run_metadata.json" || file.scope!=RunSummary::ArtifactScope::Process))
            throw std::invalid_argument("Only process metadata can exclude its own identity");
    } else throw std::invalid_argument("Unknown artifact integrity status");
}
}  // namespace

void RunSummary::SetProvenance(effective_config::Value provenance)
{
    ValidateProvenance(provenance);
    provenance_ = std::move(provenance);
}

void RunSummary::SetArtifactEvidence(const std::vector<ArtifactEvidence>& evidence)
{
    std::set<std::string> identities;
    std::vector<std::string> files;
    std::string execution;
    for (const auto& file:evidence) {
        ValidateArtifact(file);
        if (!identities.insert(FileUtils::AbsolutePath(file.path)).second)
            throw std::invalid_argument("Duplicate artifact identity");
        if (execution.empty())execution=file.execution_id;
        if (execution!=file.execution_id)throw std::invalid_argument("Mixed artifact execution IDs");
        files.push_back(file.path);
    }
    generatedFiles_=std::move(files);artifactEvidence_=evidence;
}

void RunSummary::WriteJson(const std::string& filename) const
{
    if (provenance_) {
        ValidateProvenance(*provenance_);
        if (artifactEvidence_.size()!=generatedFiles_.size())
            throw MetadataWriteError("run_metadata_write", "F1 artifact evidence is incomplete");
        const auto execution=Text(Object(*provenance_,"provenance"),"execution_id");
        bool self=false;
        for (std::size_t i=0;i<artifactEvidence_.size();++i) {
            const auto& file=artifactEvidence_[i];ValidateArtifact(file);
            if (file.path!=generatedFiles_[i] || file.execution_id!=execution)
                throw MetadataWriteError("run_metadata_write", "F1 artifact identity does not match provenance/list");
            if (file.run_id && std::none_of(runs_.begin(),runs_.end(),[&](const RunRecord& run){return run.runId==*file.run_id;}))
                throw MetadataWriteError("run_metadata_write", "Artifact refers to an unrecorded run");
            const bool own=FileUtils::AbsolutePath(file.path)==FileUtils::AbsolutePath(filename);
            if (own!=(file.integrity_status=="self_reference_excluded"))
                throw MetadataWriteError("run_metadata_write", "Metadata self-reference exclusion is not unique/correct");
            self=self || own;
        }
        if (!self)throw MetadataWriteError("run_metadata_write", "F1 metadata must include its self-excluded entry");
    } else if (!artifactEvidence_.empty()) {
        throw MetadataWriteError("run_metadata_write", "Artifact evidence requires provenance identity");
    }
    const std::string parent = FileUtils::ParentPath(filename);
    try {
        if (!parent.empty()) FileUtils::CreateDirectories(parent);
    } catch (const std::exception& error) {
        throw MetadataWriteError("run_metadata_open", error.what());
    }
    std::ofstream out(filename, std::ios::binary);
    if (!out) throw MetadataWriteError("run_metadata_open", "Failed to open run metadata file: '" + filename + "'");

    out << "{\n  \"schema\": \"run_metadata_json_v1\",\n  \"values\": {";
    bool first = true;
    for (const auto& item : values_) {
        out << (first ? "\n" : ",\n") << "    " << JsonString(item.first) << ": " << JsonString(item.second);
        first = false;
    }
    out << "\n  },\n  \"runs\": [";
    for (std::size_t index = 0; index < runs_.size(); ++index) {
        const auto& run = runs_[index];
        out << (index ? "," : "") << "\n    {\"run_id\": " << run.runId
            << ", \"planned_events\": " << run.plannedEvents
            << ", \"completed_events\": " << run.completedEvents << '}';
    }
    out << "\n  ],\n  \"generated_files\": [";
    for (std::size_t index = 0; index < generatedFiles_.size(); ++index) {
        out << (index ? "," : "") << "\n    {\"path\": " << JsonString(PathForSummary(generatedFiles_[index]))
            << ", \"schema\": " << JsonString(GeneratedFileSchema(generatedFiles_[index]));
        if (provenance_) {
            const auto& file=artifactEvidence_[index];
            out << ", \"execution_id\": " << JsonString(file.execution_id)
                << ", \"scope\": " << JsonString(ScopeName(file.scope))
                << ", \"run_id\": " << (file.run_id?std::to_string(*file.run_id):"null")
                << ", \"thread_id\": " << (file.thread_id?std::to_string(*file.thread_id):"null")
                << ", \"sha256\": " << (file.sha256?JsonString(*file.sha256):"null")
                << ", \"size_bytes\": " << (file.size_bytes?std::to_string(*file.size_bytes):"null")
                << ", \"integrity_status\": " << JsonString(file.integrity_status)
                << ", \"reason\": " << JsonString(file.reason);
        }
        out << '}';
    }
    const auto writeList = [&out](const char* key, const std::vector<std::string>& items) {
        out << "\n  ],\n  \"" << key << "\": [";
        for (std::size_t index = 0; index < items.size(); ++index) {
            out << (index ? "," : "") << "\n    " << JsonString(items[index]);
        }
    };
    writeList("messages", messages_);
    writeList("warnings", warnings_);
    out << "\n  ]";
    if (provenance_) out << ",\n  \"provenance\": " << provenance_->ToJson();
    out << "\n}\n";
    const char* faultValue = std::getenv("G4USIM_TEST_OUTPUT_FAULT");
    const std::string fault = faultValue ? faultValue : "";
    // Deterministic test hooks exercise these real finalization boundaries;
    // they do not represent measured disk/device failures.
    if (fault == "metadata_write_master") out.setstate(std::ios::badbit);
    out.flush();
    if (!out) throw MetadataWriteError("run_metadata_write", "Failed to write run metadata file: '" + filename + "'");
    out.close();
    if (fault == "metadata_close_master") out.setstate(std::ios::badbit);
    if (!out) throw MetadataWriteError("run_metadata_close", "Failed to close run metadata file: '" + filename + "'");
}

void RunSummary::Clear()
{
    values_.clear();
    messages_.clear();
    warnings_.clear();
    runs_.clear();
    generatedFiles_.clear();
    provenance_.reset();artifactEvidence_.clear();
}
