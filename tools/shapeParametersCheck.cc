#include "Geometry/ShapeParameters.hh"
#include "G4Box.hh"
#include "G4Tubs.hh"

#include <iostream>
#include <limits>
#include <string>

namespace {
int checks = 0;
void Check(bool condition, const char* message)
{
    ++checks;
    if (!condition) throw std::runtime_error(message);
}
template<class F> void Reject(F action)
{
    bool rejected = false;
    try { action(); } catch (const std::runtime_error&) { rejected = true; }
    Check(rejected, "expected rejection");
}
}

int main()
{
    try {
        using namespace ShapeParameters;
        const auto box = NormalizeBox({10, 20, 30});
        G4Box solidBox("component_box", box.halfX, box.halfY, box.halfZ);
        Check(solidBox.GetXHalfLength() == 5, "box x");
        Check(solidBox.GetYHalfLength() == 10, "box y");
        Check(solidBox.GetZHalfLength() == 15, "box z");
        const std::vector<double> raw{1, 3, 7, 0.25, 1.5};
        for (auto policy : {TubsInput::Ini, TubsInput::CppVolume, TubsInput::CppBooleanTool}) {
            const auto tubs = ResolveTubs({-1,-1,-1}, raw, policy);
            G4Tubs solid("component_tubs", tubs.rMin, tubs.rMax, tubs.halfZ, tubs.startPhi, tubs.deltaPhi);
            Check(solid.GetInnerRadius() == 1, "inner radius");
            Check(solid.GetOuterRadius() == 3, "outer radius");
            Check(solid.GetZHalfLength() == 7, "half length");
            Check(solid.GetStartPhiAngle() == .25, "start phi");
            Check(solid.GetDeltaPhiAngle() == 1.5, "delta phi");
        }
        for (std::size_t n = 0; n < 5; ++n) {
            const std::vector<double> partial(n, -99);
            const auto shorthand = ResolveTubs({8, 123, 20}, partial, TubsInput::CppVolume);
            Check(shorthand.rMin == 0 && shorthand.rMax == 4 && shorthand.halfZ == 10
                  && shorthand.startPhi == 0 && shorthand.deltaPhi == CLHEP::twopi, "shorthand");
            Reject([&] { ResolveTubs({8, 123, 20}, partial, TubsInput::Ini); });
            Reject([&] { ResolveTubs({8, 123, 20}, partial, TubsInput::CppBooleanTool); });
        }
        auto extra = raw;
        extra.push_back(std::numeric_limits<double>::quiet_NaN());
        Check(ResolveTubs({}, extra, TubsInput::CppVolume).rMax == 3, "C++ extra ignored");
        Check(ResolveTubs({}, extra, TubsInput::CppBooleanTool).rMax == 3, "tool extra ignored");
        Reject([&] { ResolveTubs({}, extra, TubsInput::Ini); });
        for (double invalid : {0., -1., std::numeric_limits<double>::infinity(),
                               std::numeric_limits<double>::quiet_NaN()}) {
            for (int i = 0; i < 3; ++i) {
                Vec3 bad{10,20,30};
                if (i == 0) bad.x = invalid;
                if (i == 1) bad.y = invalid;
                if (i == 2) bad.z = invalid;
                Reject([&] { NormalizeBox(bad); });
            }
        }
        for (double invalid : {std::numeric_limits<double>::infinity(),
                               std::numeric_limits<double>::quiet_NaN()}) {
            for (int i = 0; i < 5; ++i) {
                auto bad = raw; bad[i] = invalid;
                Reject([&] { ResolveTubs({}, bad, TubsInput::CppVolume); });
            }
        }
        for (const auto& bad : std::vector<std::vector<double>>{
                {-1,3,7,0,1}, {3,3,7,0,1}, {0,3,0,0,1}, {0,3,7,0,0}}) {
            Reject([&] { ResolveTubs({8,8,20}, bad, TubsInput::CppVolume); });
        }
        Reject([] { ResolveTubs({8,0,20}, {}, TubsInput::CppVolume); });
        const auto wide = NormalizeTubs(0,3,7,-.5,4*CLHEP::pi);
        Check(wide.startPhi == -.5 && wide.deltaPhi == 4*CLHEP::pi, "angles not rewritten");
        std::cout << "shape parameters component: " << checks << " checks passed\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "after " << checks << " checks: " << e.what() << '\n';
        return 1;
    }
}
