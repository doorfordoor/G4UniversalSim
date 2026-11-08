#include "Geometry/GeometryConfig.hh"
#include "Geometry/GeometryUtils.hh"
#include "Geometry/VolumeBuilder.hh"
#include "Geometry/VolumeNode.hh"
#include "BuildInfo.hh"
#include "G4Box.hh"
#include "G4Tubs.hh"
#include "G4Orb.hh"
#include "G4SolidStore.hh"
#include "G4SystemOfUnits.hh"
#include "G4Version.hh"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>

using effective_config::Value;
using O = Value::Object;
using A = Value::Array;
namespace {
A checks;
int failed = 0;
void Check(const std::string& name, bool passed)
{
    checks.emplace_back(O{{"name", name}, {"passed", passed}});
    if (!passed) ++failed;
}
bool Near(double actual, double expected)
{
    return std::abs(actual - expected) <= 1e-12 * std::max(1., std::abs(expected));
}
void Write(const std::filesystem::path& path, const std::string& text)
{
    std::ofstream out(path, std::ios::binary);
    out << text;
    out.close();
    if (!out) throw std::runtime_error("cannot write " + path.string());
}
void Box(const std::string& name, G4VSolid* raw, double x, double y, double z)
{
    std::unique_ptr<G4VSolid> owner(raw);
    const auto* solid = dynamic_cast<G4Box*>(raw);
    Check(name, solid && Near(solid->GetXHalfLength(), x)
          && Near(solid->GetYHalfLength(), y) && Near(solid->GetZHalfLength(), z));
}
void Tubs(const std::string& name, G4VSolid* raw, double rMin, double rMax,
          double halfZ, double startPhi, double deltaPhi)
{
    std::unique_ptr<G4VSolid> owner(raw);
    const auto* solid = dynamic_cast<G4Tubs*>(raw);
    Check(name, solid && Near(solid->GetInnerRadius(), rMin)
          && Near(solid->GetOuterRadius(), rMax) && Near(solid->GetZHalfLength(), halfZ)
          && Near(solid->GetStartPhiAngle(), startPhi) && Near(solid->GetDeltaPhiAngle(), deltaPhi));
}
template<class F> void Reject(const std::string& name, F action,
                              const std::vector<std::string>& diagnostics = {})
{
    const auto before = VolumeBuilder::GetCreatedGeometryObjectCount();
    const auto storeBefore = G4SolidStore::GetInstance()->size();
    std::string error;
    try { action(); } catch (const std::exception& e) { error = e.what(); }
    Check(name + ":rejected", !error.empty());
    Check(name + ":no_builder_objects", before == VolumeBuilder::GetCreatedGeometryObjectCount());
    Check(name + ":no_kernel_solids", storeBefore == G4SolidStore::GetInstance()->size());
    for (const auto& expected : diagnostics)
        Check(name + ":diagnostic:" + expected, error.find(expected) != std::string::npos);
}
}

int main(int argc, char** argv)
{
    try {
        if (argc == 2 && std::string(argv[1]) == "--identity") {
            std::cout << Value(O{{"source_fingerprint", G4USIM_SOURCE_FINGERPRINT},
                {"probe_sha256", G4USIM_SHAPES_PROBE_SHA256}, {"geant4_version_number", G4VERSION_NUMBER},
                {"compiler", G4USIM_COMPILER_ID}, {"compiler_version", G4USIM_COMPILER_VERSION}}).ToJson() << '\n';
            return 0;
        }
        if (argc != 2) throw std::runtime_error("usage: geometryShapesCheck OUTPUT_DIR | --identity");
        const auto dir = std::filesystem::absolute(argv[1]);
        std::filesystem::create_directories(dir);
        VolumeBuilder builder;
        VolumeNode node("direct");
        node.shape = VolumeShape::Box;
        node.size = {10,20,30};
        node.parameters = {-99}; // C++ box ignores parameters; INI must not.
        Box("direct_box", builder.CreateSolid(node), 5,10,15);
        node.size.x = 12;
        Box("direct_box_after_edit", builder.CreateSolid(node), 6,10,15);
        node.shape = VolumeShape::Tubs;
        node.parameters = {1,3,7,.25,1.5};
        Tubs("direct_tubs_parameters_win", builder.CreateSolid(node), 1,3,7,.25,1.5);
        node.parameters.push_back(-99);
        Tubs("direct_tubs_extra_ignored", builder.CreateSolid(node), 1,3,7,.25,1.5);
        for (int count = 0; count < 5; ++count) {
            node.parameters.assign(count, -99);
            Tubs("direct_shorthand_" + std::to_string(count), builder.CreateSolid(node),
                 0,6,15,0,CLHEP::twopi);
        }
        BooleanOperand operand;
        operand.shape = VolumeShape::Box;
        operand.size = {2,4,6};
        Box("boolean_box", builder.CreatePrimitiveSolidFromOperand("owner",0,operand),1,2,3);
        operand.shape = VolumeShape::Tubs;
        operand.parameters = {0,2,3,.25,1.5,999};
        Tubs("boolean_tubs_extra_ignored", builder.CreatePrimitiveSolidFromOperand("owner",0,operand),
             0,2,3,.25,1.5);
        operand.parameters.clear();
        Reject("boolean_no_shorthand", [&] {
            std::unique_ptr<G4VSolid> s(builder.CreatePrimitiveSolidFromOperand("owner",0,operand));
        }, {"owner", "tubs"});
        VolumeNode composite("composite");
        composite.shape = VolumeShape::Box; composite.size = {20,20,20};
        BooleanSolidOperation op; op.operation = BooleanOperation::Subtraction; op.tool = operand;
        composite.booleanOperations.push_back(op);
        Reject("composite_no_shorthand", [&] {
            std::unique_ptr<G4VSolid> s(builder.CreateSolid(composite));
        });
        composite.booleanOperations[0].tool.shape = VolumeShape::Box;
        composite.booleanOperations[0].tool.size.x = -1;
        Reject("composite_bad_box_tool", [&] {
            std::unique_ptr<G4VSolid> s(builder.CreateSolid(composite));
        });
        for (double bad : {0., -1., std::numeric_limits<double>::infinity(),
                           std::numeric_limits<double>::quiet_NaN()}) {
            node.shape = VolumeShape::Box; node.size = {bad,20,30};
            Reject("direct_bad_box", [&] { std::unique_ptr<G4VSolid> s(builder.CreateSolid(node)); });
        }
        node.shape = VolumeShape::Tubs; node.size = {10,20,30};
        for (const auto& bad : std::vector<std::vector<double>>{
                {-1,3,7,0,1}, {3,3,7,0,1}, {0,3,0,0,1}, {0,3,7,0,0},
                {0,3,7,std::numeric_limits<double>::quiet_NaN(),1}}) {
            node.parameters = bad;
            Reject("direct_bad_tubs", [&] { std::unique_ptr<G4VSolid> s(builder.CreateSolid(node)); });
            operand.parameters = bad;
            Reject("boolean_bad_tubs", [&] {
                std::unique_ptr<G4VSolid> s(builder.CreatePrimitiveSolidFromOperand("owner",0,operand));
            });
        }
        node.shape = VolumeShape::Orb; node.parameters = {4};
        { std::unique_ptr<G4VSolid> s(builder.CreateSolid(node));
          auto* orb = dynamic_cast<G4Orb*>(s.get());
          Check("legacy_orb", orb && orb->GetRadius() == 4); }
        operand.shape = VolumeShape::Ellipsoid; operand.parameters = {1,2,3};
        Reject("legacy_boolean_a5_refused", [&] {
            std::unique_ptr<G4VSolid> s(builder.CreatePrimitiveSolidFromOperand("owner",0,operand));
        });

        const std::string world = "[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_AIR\n";
        const auto load = [&](const std::string& name, const std::string& body) {
            auto path = dir/(name + ".ini"); Write(path, world + body);
            GeometryConfig config; config.Load(path.string()); return config;
        };
        for (const auto& alias : {"box", "cube"}) {
            auto config = load(alias, "[volume.test]\nparent=world\nshape=" + std::string(alias)
                + "\nsize=1 cm,20 mm,0.03 m\nmaterial=G4_AIR\n");
            Box("ini_" + std::string(alias), builder.CreateSolid(config.GetVolume("test")),5,10,15);
        }
        for (const auto& alias : {"tubs", "tube", "cylinder"}) {
            auto config = load(alias, "[volume.test]\nparent=world\nshape=" + std::string(alias)
                + "\nparameters=1 mm,0.3 cm,7 mm,30 deg,1.5 rad\nmaterial=G4_AIR\n"
                + "[volume.test.boolean.0]\noperation=subtraction\nshape=" + alias
                + "\nparameters=0 mm,2 mm,3 mm,30 deg,1.5 rad\n");
            const auto& parsed = config.GetVolume("test");
            Tubs("ini_" + std::string(alias), builder.CreatePrimitiveSolid(parsed),1,3,7,30*CLHEP::deg,1.5);
            Tubs("ini_boolean_" + std::string(alias),
                 builder.CreatePrimitiveSolidFromOperand("test",0,parsed.booleanOperations.at(0).tool),
                 0,2,3,30*CLHEP::deg,1.5);
            std::unique_ptr<G4VSolid> combined(builder.CreateSolid(parsed));
            Check("ini_boolean_composed_" + std::string(alias), combined->GetEntityType() == "G4SubtractionSolid");
        }
        const std::vector<std::pair<std::string,std::string>> invalid = {
            {"box_parameters", "shape=box\nsize=1 mm,2 mm,3 mm\nparameters=1\n"},
            {"box_zero", "shape=box\nsize=0 mm,2 mm,3 mm\n"},
            {"tubs_short", "shape=tubs\nparameters=0,3,7,0\n"},
            {"tubs_long", "shape=tubs\nparameters=0,3,7,0,1,9\n"},
            {"tubs_size", "shape=tubs\nparameters=0,3,7,0,1\nsize=10,20,30\n"},
            {"tubs_radius", "shape=tubs\nparameters=3,3,7,0,1\n"},
            {"tubs_nan", "shape=tubs\nparameters=0,3,7,nan,1\n"}
        };
        for (const auto& item : invalid) {
            Reject("ini_" + item.first, [&] {
                load(item.first, "[volume.test]\nparent=world\nmaterial=G4_AIR\n" + item.second);
            }, {item.first + ".ini", "line ", "volume.test"});
            Reject("ini_boolean_" + item.first, [&] {
                load("tool_" + item.first, "[volume.test]\nparent=world\nmaterial=G4_AIR\nshape=box\nsize=10,20,30\n"
                    "[volume.test.boolean.0]\noperation=subtraction\n" + item.second);
            }, {"tool_" + item.first + ".ini", "line ", "volume.test.boolean.0"});
        }
        Write(dir/"results.json", Value(O{{"checks",checks},{"failed_checks",failed},
            {"source_fingerprint",G4USIM_SOURCE_FINGERPRINT},{"probe_sha256",G4USIM_SHAPES_PROBE_SHA256}}).ToJson());
        std::cout << checks.size() << " checks; " << failed << " failed\n";
        return failed ? 1 : 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 2; }
}
