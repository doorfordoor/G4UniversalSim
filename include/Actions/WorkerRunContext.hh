#pragma once

#include <memory>

class OutputManager;
class ScoringManager;

struct WorkerRunContext {
    std::unique_ptr<OutputManager> output;
    // Sequential actions share the application's sole output/summary owner.
    // SimulationManager outlives the run manager and all of these actions.
    OutputManager* sequentialOutput = nullptr;
    std::unique_ptr<ScoringManager> scoring;

    OutputManager* GetOutputManager() const;
    ScoringManager* GetScoringManager() const;
};
