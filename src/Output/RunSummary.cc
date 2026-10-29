#include "Output/RunSummary.hh"

#include "Output/AnalysisOutput.hh"
#include "Output/CsvWriter.hh"
#include "Utils/FileUtils.hh"

#include <fstream>
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
}  // namespace

void RunSummary::WriteJson(const std::string& filename) const
{
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
            << ", \"schema\": " << JsonString(GeneratedFileSchema(generatedFiles_[index])) << '}';
    }
    const auto writeList = [&out](const char* key, const std::vector<std::string>& items) {
        out << "\n  ],\n  \"" << key << "\": [";
        for (std::size_t index = 0; index < items.size(); ++index) {
            out << (index ? "," : "") << "\n    " << JsonString(items[index]);
        }
    };
    writeList("messages", messages_);
    writeList("warnings", warnings_);
    out << "\n  ]\n}\n";
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
}
