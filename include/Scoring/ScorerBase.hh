#pragma once

#include "Output/OutputRecord.hh"

#include <string>

class OutputManager;

class ScorerBase {
public:
    explicit ScorerBase(std::string name);
    virtual ~ScorerBase();

    const std::string& GetName() const;

    void SetEnabled(bool enabled);
    bool IsEnabled() const;

    virtual void BeginRun(int runID);
    virtual void EndRun(int runID);

    virtual void BeginEvent(int eventID);
    virtual void EndEvent(int eventID);

    virtual void ScoreHit(const HitRecord& hit);
    virtual void Write(OutputManager& output);
    virtual void Reset();

protected:
    std::string name_;
    bool enabled_ = true;
};
