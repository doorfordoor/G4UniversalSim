#include "Scoring/ScorerBase.hh"

#include "Utils/StringUtils.hh"

#include <stdexcept>
#include <utility>

ScorerBase::ScorerBase(std::string name)
    : name_(std::move(name))
{
    if (StringUtils::Trim(name_).empty()) {
        throw std::runtime_error("ScorerBase requires a non-empty name");
    }
}

ScorerBase::~ScorerBase() = default;

const std::string& ScorerBase::GetName() const
{
    return name_;
}

void ScorerBase::SetEnabled(bool enabled)
{
    enabled_ = enabled;
}

bool ScorerBase::IsEnabled() const
{
    return enabled_;
}

void ScorerBase::BeginRun(int) {}
void ScorerBase::EndRun(int) {}
void ScorerBase::BeginEvent(int) {}
void ScorerBase::EndEvent(int) {}
void ScorerBase::ScoreHit(const HitRecord&) {}
void ScorerBase::Write(OutputManager&) {}
void ScorerBase::Reset() {}
