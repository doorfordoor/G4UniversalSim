#pragma once

#include "Geometry/GeometryTypes.hh"
#include <map>
#include <string>

class VolumeNode;

// Temporary validation/assembly values, never a second editable configuration.
using RegionCutPlan = std::map<std::string, ProductionCut>;
void AccumulateRegionCuts(RegionCutPlan& plan, const VolumeNode& node);
RegionCutPlan PlanRegionCuts(const VolumeNode& root);
