#pragma once

#include "Config/InputProvenance.hh"
#include "Config/IniReader.hh"

#include <array>
#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <vector>

struct VoxelGridDescriptor {
    std::array<int, 3> shape{};
    std::array<double, 3> pitchMm{};
    std::array<double, 3> spanMm{};
    std::vector<std::uint16_t> labels;
    std::map<std::uint16_t, std::string> materials;
    std::map<std::string, std::vector<std::uint32_t>> rois;
    std::vector<input_provenance::InputFile> inputs;
    std::map<std::string, std::size_t> roiInputIndices;

};

// Owned by the geometry load transaction until layout and payload validation complete.
class VoxelGridDescriptorReader {
public:
    VoxelGridDescriptorReader(const std::string& geometryFile, const std::string& descriptorPath,
                              double minPitchMm);
    std::shared_ptr<const VoxelGridDescriptor> Descriptor() const { return descriptor_; }
    void ReadPayload();

private:
    std::string path_;
    std::shared_ptr<VoxelGridDescriptor> descriptor_;
    IniFieldInfo labelFile_;
    std::map<std::string, IniFieldInfo> roiFiles_;
    std::size_t cellCount_ = 1;
};
