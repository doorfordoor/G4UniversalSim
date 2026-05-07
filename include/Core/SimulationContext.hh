#pragma once

#include <optional>
#include <string>

class SimulationContext {
public:
    SimulationContext();

    void SetMainConfig(const std::string& path);
    const std::string& GetMainConfig() const;

    void SetOutputDir(const std::string& dir);
    const std::string& GetOutputDir() const;

    void SetSeed(unsigned long seed);
    unsigned long GetSeed() const;
    bool HasSeed() const;

    void SetNumThreads(int n);
    int GetNumThreads() const;

    void SetInteractive(bool interactive);
    bool IsInteractive() const;

    void SetMacroFile(const std::string& path);
    const std::string& GetMacroFile() const;
    bool HasMacroFile() const;

    void SetVerboseLevel(int level);
    int GetVerboseLevel() const;

    void SetCheckOverlaps(bool enable);
    bool GetCheckOverlaps() const;

    void SetDryRun(bool enable);
    bool IsDryRun() const;

    void SetRunName(const std::string& name);
    const std::string& GetRunName() const;

    void Clear();

private:
    std::string mainConfig_;
    std::string outputDir_;
    std::optional<unsigned long> seed_;
    int numThreads_ = 1;
    bool interactive_ = false;
    std::string macroFile_;
    int verboseLevel_ = 0;
    bool checkOverlaps_ = true;
    bool dryRun_ = false;
    std::string runName_;
};
