#pragma once

#include "Geometry/GeometryTypes.hh"

#include <map>
#include <string>
#include <vector>

namespace GeometryUtils {

VolumeShape ParseShape(const std::string& text);
std::string ShapeToString(VolumeShape shape);

PlacementType ParsePlacementType(const std::string& text);
std::string PlacementTypeToString(PlacementType type);

Vec3 ParseVec3(const std::string& text, bool parseAsLength = true);
Rotation3 ParseRotation3(const std::string& text);
std::vector<double> ParseParameterList(const std::string& text, bool parseWithUnits = true);
ProductionCut ParseProductionCuts(const std::map<std::string, std::string>& values);

bool IsValidVolumeName(const std::string& name);
std::string NormalizeVolumeName(const std::string& name);
void ValidateVolumeName(const std::string& name);
void ValidateBoxSize(const Vec3& size);
void ValidateTubsParameters(double rMin, double rMax, double halfZ, double startPhi, double deltaPhi);
std::string MakePath(const std::string& parentPath, const std::string& childName);

}  // namespace GeometryUtils
