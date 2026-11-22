#pragma once
#include "Geometry/GdmlIO.hh"
#include <array>
#include <map>
#include <stdexcept>

namespace GdmlIO {
class ComponentScaleError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};
struct Component {
    G4LogicalVolume* root = nullptr;
    std::map<std::string,G4LogicalVolume*> logicals;
    struct Occurrence {std::string source, path; G4LogicalVolume* logical;};
    std::vector<Occurrence> occurrences;
    std::vector<G4LogicalVolume*> sensitive;
    std::vector<AcceptedInput> inputs;
    std::vector<std::string> choices;
};
// Without construction this inspects the same native DOM and registers no solids or volumes.
Component ReadComponent(const std::string& path, const std::string& selector,
                        const std::string& instance, bool construct, bool checkOverlaps,
                        const std::string& acceptedSha = {}, const std::array<double,3>& scales = {1,1,1});
}
