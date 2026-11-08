#include "Core/RunFinalization.hh"
#include "Config/InputProvenance.hh"
#include "Output/RunSummary.hh"
#include "Utils/FileUtils.hh"
#include <algorithm>
#include <cstdlib>
#include <exception>
#include <string>
#include <utility>

namespace runtime {
PublicationOutcome PublishFinalRunEvidence(
    OutputManager& output, std::vector<OutputManager::ArtifactEvidence> artifacts)
{
    RunSummary& summary = output.GetRunSummary();
    std::vector<std::string> generated = output.GetGeneratedFiles();
    generated.push_back(FileUtils::AbsolutePath(output.MakeOutputPath("run_summary.txt")));
    generated.push_back(FileUtils::AbsolutePath(output.MakeOutputPath("run_metadata.json")));
    std::sort(generated.begin(), generated.end());
    generated.erase(std::unique(generated.begin(), generated.end()), generated.end());
    summary.SetGeneratedFiles(generated);
    summary.Set("generated_file_count", static_cast<int>(generated.size()));
    for (const std::string& path : generated) {
        if (FileUtils::Filename(path).rfind("spectrum_", 0) == 0) {
            summary.Set("spectrum_csv_schema_version", 1);
            break;
        }
    }
    summary.Set("summary_write_status", "completed");

    output.WriteRunSummary();
    OutputManager::ArtifactEvidence textArtifact;
    textArtifact.path = FileUtils::AbsolutePath(output.MakeOutputPath("run_summary.txt"));
    textArtifact.execution_id = output.GetExecutionId();
    try {
        const auto digest = input_provenance::HashFile(textArtifact.path);
        textArtifact.sha256 = digest.sha256;
        textArtifact.size_bytes = digest.size_bytes;
        textArtifact.integrity_status = "hashed";
    } catch (const std::exception& error) {
        textArtifact.integrity_status = "unavailable";
        textArtifact.reason = error.what();
        output.RecordOutputFailure("artifact_integrity", error.what());
        const auto failure = output.GetOutputFailure();
        summary.Set("status", "failed");
        summary.Set("program_exit_code", EXIT_FAILURE);
        summary.Set("output_failure_status", "failed");
        summary.Set("output_failure_run_id", std::to_string(failure.runId));
        summary.Set("output_failure_thread_id", std::to_string(failure.threadId));
        summary.Set("output_failure_stage", failure.stage);
        summary.Set("output_failure_message", failure.message);
        output.WriteRunSummary();
    }
    artifacts.push_back(std::move(textArtifact));
    std::sort(artifacts.begin(), artifacts.end(), [](const auto& a, const auto& b) { return a.path < b.path; });
    summary.SetArtifactEvidence(artifacts);
    // Metadata may fail after the first text summary was closed. Latch its
    // precise cause, then correct the still-writable text artifact instead of
    // leaving status=completed/exit=0 behind. This is not an atomic two-file
    // transaction; a failed or partial JSON file is not a generated artifact.
    try {
        output.WriteRunMetadataJson();
    } catch (const std::exception& error) {
        output.RecordOutputFailure("run_metadata_write", error.what());
        const auto failure = output.GetOutputFailure();
        summary.Set("status", "failed");
        summary.Set("program_exit_code", EXIT_FAILURE);
        summary.Set("output_failure_status", "failed");
        summary.Set("output_failure_run_id", std::to_string(failure.runId));
        summary.Set("output_failure_thread_id", std::to_string(failure.threadId));
        summary.Set("output_failure_stage", failure.stage);
        summary.Set("output_failure_message", failure.message);
        // Use only completed registrations here. In particular, an existing
        // directory or a partially written metadata file must not be listed.
        generated = output.GetGeneratedFiles();
        const auto metadata = FileUtils::AbsolutePath(output.MakeOutputPath("run_metadata.json"));
        generated.erase(std::remove(generated.begin(), generated.end(), metadata), generated.end());
        summary.SetGeneratedFiles(generated);
        summary.Set("generated_file_count", static_cast<int>(generated.size()));
        for (const std::string& path : generated) {
            if (FileUtils::Filename(path).rfind("spectrum_", 0) == 0) {
                summary.Set("spectrum_csv_schema_version", 1);
                break;
            }
        }
        // summary_write_status describes successful text-summary completion,
        // not metadata success. If this corrective write fails it throws and
        // the existing summary-failure path remains authoritative.
        output.WriteRunSummary(); // preserve the real text-summary failure path
        return PublicationOutcome::Failed;
    }
    return output.HasOutputFailure() ? PublicationOutcome::Failed : PublicationOutcome::Clean;
}
} // namespace runtime
