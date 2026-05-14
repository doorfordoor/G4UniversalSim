#pragma once

#include "Output/CsvWriter.hh"
#include "Output/Histogram1D.hh"
#include "Output/OutputRecord.hh"
#include "Output/RunSummary.hh"

#include <map>
#include <memory>
#include <string>
#include <vector>

class OutputManager {
public:
    OutputManager() = default;
    ~OutputManager() noexcept;

    void SetOutputDir(const std::string& outputDir);
    const std::string& GetOutputDir() const;

    void SetThreadId(int threadId);
    int GetThreadId() const;

    void EnableThreadSuffix(bool enable);
    bool IsThreadSuffixEnabled() const;

    bool IsInitialized() const;
    bool IsHitFileOpen() const;
    bool IsEventEdepFileOpen() const;
    bool HasOpenFiles() const;
    std::string GetHitFilename() const;
    std::string GetEventEdepFilename() const;

    std::string MakeOutputPath(const std::string& filename) const;
    std::string MakeThreadFilename(const std::string& baseName) const;

    void Initialize();

    void OpenHitFile();
    void OpenEventEdepFile();

    void WriteHit(const HitRecord& record);
    void WriteEventEdep(const EventEdepRecord& record);

    void WriteHitRow(const std::vector<std::string>& values);
    void WriteEventEdepRow(const std::vector<std::string>& values);

    void AddHistogram1D(const Histogram1D& hist);
    Histogram1D& GetHistogram1D(const std::string& name);
    const Histogram1D& GetHistogram1D(const std::string& name) const;
    bool HasHistogram1D(const std::string& name) const;
    void WriteHistogram1D(const std::string& name);
    void WriteAllHistograms();

    RunSummary& GetRunSummary();
    const RunSummary& GetRunSummary() const;
    void WriteRunSummary();

    void Flush();
    void Close();

private:
    static std::vector<std::string> HitHeader();
    static std::vector<std::string> EventEdepHeader();
    static std::string ToString(double value);

    std::string outputDir_ = "output";
    int threadId_ = 0;
    bool threadSuffixEnabled_ = true;
    // True once Initialize() has created the output directory; current file-open state is HasOpenFiles().
    bool initialized_ = false;
    std::unique_ptr<CsvWriter> hitWriter_;
    std::unique_ptr<CsvWriter> eventEdepWriter_;
    std::map<std::string, Histogram1D> histograms1D_;
    RunSummary runSummary_;
};
