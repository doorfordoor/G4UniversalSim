#pragma once

#include "Geometry/GeometryTypes.hh"
#include "G4PhysicalConstants.hh"

#include <cmath>
#include <stdexcept>

// Transient values in Geant4 internal units, never a second mutable state on
// VolumeNode. Other shapes retain their named SolidRegistry compatibility factories.
namespace ShapeParameters {

struct Box {
    double halfX;
    double halfY;
    double halfZ;
};

struct Tubs {
    double rMin;
    double rMax;
    double halfZ;
    double startPhi;
    double deltaPhi;
};

inline Box NormalizeBox(const Vec3& size)
{
    if (!std::isfinite(size.x) || !std::isfinite(size.y) || !std::isfinite(size.z)) {
        throw std::runtime_error("Box size must be finite in x/y/z");
    }
    if (size.x <= 0.0 || size.y <= 0.0 || size.z <= 0.0) {
        throw std::runtime_error("Box size must be positive in x/y/z");
    }
    return {size.x * 0.5, size.y * 0.5, size.z * 0.5};
}

inline Tubs NormalizeTubs(double rMin, double rMax, double halfZ,
                          double startPhi, double deltaPhi)
{
    if (!std::isfinite(rMin) || !std::isfinite(rMax) || !std::isfinite(halfZ)
        || !std::isfinite(startPhi) || !std::isfinite(deltaPhi)) {
        throw std::runtime_error("Tubs parameters must be finite");
    }
    if (rMin < 0.0) throw std::runtime_error("Tubs rMin must be >= 0");
    if (rMax <= rMin) throw std::runtime_error("Tubs rMax must be > rMin");
    if (halfZ <= 0.0) throw std::runtime_error("Tubs halfZ must be > 0");
    if (deltaPhi <= 0.0) throw std::runtime_error("Tubs deltaPhi must be > 0");
    // Preserve kernel handling of negative startPhi and spans above 2*pi.
    return {rMin, rMax, halfZ, startPhi, deltaPhi};
}

enum class TubsInput { Ini, CppVolume, CppBooleanTool };

inline Tubs ResolveTubs(const Vec3& size, const std::vector<double>& parameters,
                        TubsInput input)
{
    if (input == TubsInput::Ini && parameters.size() != 5) {
        throw std::runtime_error("tubs requires exactly 5 parameters; got "
                                 + std::to_string(parameters.size()) + ".");
    }
    if (parameters.size() >= 5) {
        return NormalizeTubs(parameters[0], parameters[1], parameters[2],
                             parameters[3], parameters[4]);
    }
    if (input == TubsInput::CppVolume && size.x > 0.0 && size.y > 0.0 && size.z > 0.0) {
        // Legacy C++ shorthand: y is a positive admission flag, not a radius.
        return NormalizeTubs(0.0, size.x * 0.5, size.z * 0.5, 0.0, CLHEP::twopi);
    }
    if (input == TubsInput::CppBooleanTool) {
        throw std::runtime_error("tubs requires 5 parameters: rMin,rMax,halfZ,startPhi,deltaPhi");
    }
    throw std::runtime_error("requires 5 tubs parameters or positive size shorthand");
}

} // namespace ShapeParameters
