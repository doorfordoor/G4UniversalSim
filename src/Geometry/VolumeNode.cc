#include "Geometry/VolumeNode.hh"

#include "Geometry/GeometryUtils.hh"
#include "Utils/StringUtils.hh"

#include <sstream>
#include <stdexcept>

VolumeNode::VolumeNode() = default;

VolumeNode::VolumeNode(const std::string& nodeName)
    : name(nodeName)
{
}

bool VolumeNode::IsWorld() const
{
    return parentName.empty();
}

bool VolumeNode::HasParent() const
{
    return !parentName.empty();
}

bool VolumeNode::HasRegion() const
{
    return !regionName.empty();
}

bool VolumeNode::IsSensitive() const
{
    return sensitive;
}

bool VolumeNode::IsBiasVolume() const
{
    return bias;
}

void VolumeNode::AddChild(const VolumeNode& child)
{
    children.push_back(child);
}

bool VolumeNode::HasChildren() const
{
    return !children.empty();
}

bool VolumeNode::HasBooleanOperations() const
{
    return !booleanOperations.empty();
}

std::vector<VolumeNode*> VolumeNode::GetChildrenMutable()
{
    std::vector<VolumeNode*> result;
    result.reserve(children.size());
    for (VolumeNode& child : children) result.push_back(&child);
    return result;
}

std::vector<const VolumeNode*> VolumeNode::GetChildren() const
{
    std::vector<const VolumeNode*> result;
    result.reserve(children.size());
    for (const VolumeNode& child : children) result.push_back(&child);
    return result;
}

void VolumeNode::SetProperty(const std::string& key, const std::string& value)
{
    userProperties[key] = value;
}

bool VolumeNode::HasProperty(const std::string& key) const
{
    return userProperties.find(key) != userProperties.end();
}

std::string VolumeNode::GetProperty(const std::string& key, const std::string& defaultValue) const
{
    const auto it = userProperties.find(key);
    return it == userProperties.end() ? defaultValue : it->second;
}

std::string VolumeNode::ShapeAsString() const
{
    return GeometryUtils::ShapeToString(shape);
}

std::string VolumeNode::ToString() const
{
    std::ostringstream oss;
    oss << "VolumeNode{name='" << name << "', parent='" << parentName
        << "', shape='" << ShapeAsString() << "', material='" << materialName
        << "', sensitive=" << (sensitive ? "true" : "false")
        << ", bias=" << (bias ? "true" : "false")
        << ", booleanOps=" << booleanOperations.size() << "}";
    return oss.str();
}

void VolumeNode::ValidateBasic() const
{
    GeometryUtils::ValidateVolumeName(name);
    if (shape == VolumeShape::Unknown) {
        throw std::runtime_error("Volume '" + name + "' has unsupported or missing shape");
    }
    if (materialName.empty()) {
        throw std::runtime_error("Volume '" + name + "' is missing material");
    }
    if (shape == VolumeShape::Box) {
        GeometryUtils::ValidateBoxSize(size);
    }
    if (shape == VolumeShape::Tubs) {
        if (parameters.size() < 5) {
            throw std::runtime_error("Volume '" + name + "' requires 5 tubs parameters");
        }
        GeometryUtils::ValidateTubsParameters(
            parameters[0], parameters[1], parameters[2], parameters[3], parameters[4]
        );
    }
    if (hasProductionCuts) {
        const auto checkCut = [&](double value, const std::string& label) {
            if (value == 0.0 || value < -1.0) {
                throw std::runtime_error("Volume '" + name + "' has invalid production cut " + label);
            }
        };
        checkCut(productionCuts.gamma, "gamma");
        checkCut(productionCuts.electron, "electron");
        checkCut(productionCuts.positron, "positron");
        checkCut(productionCuts.proton, "proton");
    }
    for (const BooleanSolidOperation& op : booleanOperations) {
        const std::string opName = op.name.empty() ? "<unnamed>" : op.name;
        if (op.operation == BooleanOperation::None) {
            throw std::runtime_error("Volume '" + name + "' has boolean operation '" + opName + "' with operation=none");
        }
        if (op.tool.shape == VolumeShape::Unknown) {
            throw std::runtime_error("Volume '" + name + "' has boolean operation '" + opName + "' with missing or unsupported tool shape");
        }
        if (op.tool.shape == VolumeShape::Box) {
            GeometryUtils::ValidateBoxSize(op.tool.size);
        }
        if (op.tool.shape == VolumeShape::Tubs) {
            if (op.tool.parameters.size() < 5) {
                throw std::runtime_error("Volume '" + name + "' boolean operation '" + opName + "' requires 5 tubs parameters");
            }
            GeometryUtils::ValidateTubsParameters(
                op.tool.parameters[0],
                op.tool.parameters[1],
                op.tool.parameters[2],
                op.tool.parameters[3],
                op.tool.parameters[4]
            );
        }
    }
}
