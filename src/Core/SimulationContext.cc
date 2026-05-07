#include "Core/SimulationContext.hh"

#include <stdexcept>

SimulationContext::SimulationContext()
{
    Clear();
}

void SimulationContext::SetMainConfig(const std::string& path)
{
    mainConfig_ = path;
}

const std::string& SimulationContext::GetMainConfig() const
{
    return mainConfig_;
}

void SimulationContext::SetOutputDir(const std::string& dir)
{
    outputDir_ = dir.empty() ? "output" : dir;
}

const std::string& SimulationContext::GetOutputDir() const
{
    return outputDir_;
}

void SimulationContext::SetSeed(unsigned long seed)
{
    seed_ = seed;
}

unsigned long SimulationContext::GetSeed() const
{
    if (!seed_) {
        throw std::runtime_error("Simulation seed has not been set");
    }
    return *seed_;
}

bool SimulationContext::HasSeed() const
{
    return seed_.has_value();
}

void SimulationContext::SetNumThreads(int n)
{
    if (n <= 0) {
        throw std::runtime_error("Simulation numThreads must be > 0");
    }
    numThreads_ = n;
}

int SimulationContext::GetNumThreads() const
{
    return numThreads_;
}

void SimulationContext::SetInteractive(bool interactive)
{
    interactive_ = interactive;
}

bool SimulationContext::IsInteractive() const
{
    return interactive_;
}

void SimulationContext::SetMacroFile(const std::string& path)
{
    macroFile_ = path;
}

const std::string& SimulationContext::GetMacroFile() const
{
    return macroFile_;
}

bool SimulationContext::HasMacroFile() const
{
    return !macroFile_.empty();
}

void SimulationContext::SetVerboseLevel(int level)
{
    verboseLevel_ = level;
}

int SimulationContext::GetVerboseLevel() const
{
    return verboseLevel_;
}

void SimulationContext::SetCheckOverlaps(bool enable)
{
    checkOverlaps_ = enable;
}

bool SimulationContext::GetCheckOverlaps() const
{
    return checkOverlaps_;
}

void SimulationContext::SetDryRun(bool enable)
{
    dryRun_ = enable;
}

bool SimulationContext::IsDryRun() const
{
    return dryRun_;
}

void SimulationContext::SetRunName(const std::string& name)
{
    runName_ = name;
}

const std::string& SimulationContext::GetRunName() const
{
    return runName_;
}

void SimulationContext::Clear()
{
    mainConfig_.clear();
    outputDir_ = "output";
    seed_.reset();
    numThreads_ = 1;
    interactive_ = false;
    macroFile_.clear();
    verboseLevel_ = 0;
    checkOverlaps_ = true;
    dryRun_ = false;
    runName_.clear();
}
