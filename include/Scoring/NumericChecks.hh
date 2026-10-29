#pragma once

#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>

// Never publish a nonfinite score or commit an overflowing accumulator.
// These checks impose no arbitrary limit on otherwise representable weights.
namespace ScoringNumeric {
inline double Finite(double value, const char* operation)
{
    if (!std::isfinite(value)) {
        throw std::runtime_error(std::string("Scoring numeric failure: ") + operation + " is not finite");
    }
    return value;
}
inline double Add(double left, double right, const char* operation)
{
    Finite(left, operation);
    Finite(right, operation);
    return Finite(left + right, operation);
}
inline double Multiply(double left, double right, const char* operation)
{
    Finite(left, operation);
    Finite(right, operation);
    return Finite(left * right, operation);
}
// Check validity before the neutral/zero-length sentinel test: comparisons with
// NaN are false and must never turn a corrupt charged step into a skipped score.
inline bool PositiveLETStep(double stoppingPower, double length, double weight)
{
    Finite(stoppingPower, "LET stopping power");
    Finite(length, "LET step length");
    Finite(weight, "LET step weight");
    return stoppingPower > 0.0 && length > 0.0;
}
inline long long AddCount(long long left, long long right, const char* operation)
{
    if (left < 0 || right < 0 || left > std::numeric_limits<long long>::max() - right) {
        throw std::runtime_error(std::string("Scoring numeric failure: ") + operation + " count overflow");
    }
    return left + right;
}
}  // namespace ScoringNumeric
