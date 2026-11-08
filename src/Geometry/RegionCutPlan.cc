#include "Geometry/RegionCutPlan.hh"
#include "Geometry/VolumeNode.hh"
#include "Utils/StringUtils.hh"

#include <cmath>
#include <stdexcept>

void AccumulateRegionCuts(RegionCutPlan& plan, const VolumeNode& node)
{
    if (!node.hasProductionCuts) return;
    const auto region = StringUtils::Trim(node.regionName);
    if (region.empty())
        throw std::runtime_error("Volume '" + node.name + "' declares production cuts without a region");
    // Work on a value copy so rejection never partly updates the accumulated plan.
    const auto found = plan.find(region);
    auto candidate = found == plan.end() ? ProductionCut{} : found->second;
    const auto merge = [&](double value, double& target, const char* particle) {
        if (value == -1.0) return;
        if (!std::isfinite(value) || value <= 0.0)
            throw std::runtime_error("Volume '" + node.name + "' has invalid production cut for " + particle);
        if (target >= 0.0 && target != value)
            throw std::runtime_error("Region '" + region + "' has conflicting production cuts for " +
                                     particle + " at volume '" + node.name + "'; use one consistent value");
        target = value;
    };
    merge(node.productionCuts.gamma, candidate.gamma, "gamma");
    merge(node.productionCuts.electron, candidate.electron, "e-");
    merge(node.productionCuts.positron, candidate.positron, "e+");
    merge(node.productionCuts.proton, candidate.proton, "proton");
    plan[region] = candidate;
}

RegionCutPlan PlanRegionCuts(const VolumeNode& root)
{
    RegionCutPlan plan;
    const auto visit = [&](const auto& self, const VolumeNode& node) -> void {
        AccumulateRegionCuts(plan, node);
        for (const auto& child : node.children) self(self, child);
    };
    visit(visit, root);
    return plan;
}
