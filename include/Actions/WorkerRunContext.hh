#pragma once

#include <memory>

class OutputManager;
class ScoringManager;

struct WorkerRunContext {
    std::unique_ptr<OutputManager> output;
    std::unique_ptr<ScoringManager> scoring;

    OutputManager* GetOutputManager() const;
    ScoringManager* GetScoringManager() const;
};
