#include "Geometry/VoxelGridDescriptor.hh"

#include "Config/IniReader.hh"
#include "Utils/StringUtils.hh"

#include <charconv>
#include <cmath>
#include <filesystem>
#include <limits>
#include <locale>
#include <sstream>
#include <stdexcept>
#include <string_view>

namespace {

std::runtime_error Error(const std::string& path, std::size_t line, const std::string& message)
{
    return std::runtime_error("Voxel descriptor '" + path + "' line " + std::to_string(line) + ": " + message);
}

std::size_t InvalidUtf8Line(std::string_view bytes)
{
    std::size_t line = 1;
    for (std::size_t i = 0; i < bytes.size();) {
        const auto lead = static_cast<unsigned char>(bytes[i++]);
        if (lead == 0) return line;
        if (lead < 0x80) {
            if (lead == '\n') ++line;
            continue;
        }
        if (lead < 0xC2 || lead > 0xF4) return line;
        const unsigned length = lead < 0xE0 ? 1 : lead < 0xF0 ? 2 : 3;
        if (bytes.size() - i < length) return line;
        const auto first = static_cast<unsigned char>(bytes[i]);
        if ((lead == 0xE0 && first < 0xA0) || (lead == 0xED && first >= 0xA0)
            || (lead == 0xF0 && first < 0x90) || (lead == 0xF4 && first >= 0x90)) return line;
        for (unsigned n = 0; n < length; ++n) {
            if ((static_cast<unsigned char>(bytes[i++]) & 0xC0) != 0x80) return line;
        }
    }
    return 0;
}

std::string RelativeTo(const std::string& source, const std::string& value)
{
    const auto path = std::filesystem::u8path(value);
    if (path.empty() || path.has_root_path() || value.find(':') != std::string::npos
        || value.front() == '\\' || value.find('\0') != std::string::npos) {
        throw std::runtime_error("Expected a relative input path beside '" + source + "': '" + value + "'");
    }
    return (std::filesystem::u8path(source).parent_path() / path).lexically_normal().u8string();
}

unsigned Integer(std::string_view value, unsigned max, const std::string& path,
                 std::size_t line, const std::string& field)
{
    unsigned number = 0;
    const auto parsed = std::from_chars(value.data(), value.data() + value.size(), number);
    if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size() || number > max) {
        throw Error(path, line, field + " must be a decimal integer in range 0.." + std::to_string(max));
    }
    return number;
}

std::array<std::string, 3> Triple(const IniFieldInfo& field, const std::string& path)
{
    const auto first = field.value.find(',');
    const auto second = first == std::string::npos ? first : field.value.find(',', first + 1);
    if (second == std::string::npos || field.value.find(',', second + 1) != std::string::npos) {
        throw Error(path, field.lineNumber, field.key + " must have exactly three comma-separated XYZ values");
    }
    return {StringUtils::Trim(field.value.substr(0, first)),
            StringUtils::Trim(field.value.substr(first + 1, second - first - 1)),
            StringUtils::Trim(field.value.substr(second + 1))};
}

std::uint32_t LittleEndian(const std::string& bytes, std::size_t offset, unsigned width)
{
    std::uint32_t value = 0;
    for (unsigned i = 0; i < width; ++i) {
        value |= static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[offset + i])) << (8 * i);
    }
    return value;
}

void Remember(VoxelGridDescriptor& grid, const input_provenance::InputFile& input)
{
    grid.inputs.push_back({input.path, {}, input.sha256});
}

}  // namespace

VoxelGridDescriptorReader::VoxelGridDescriptorReader(const std::string& geometryFile,
                                                     const std::string& descriptorPath,
                                                     double minPitchMm)
    : path_(RelativeTo(geometryFile, descriptorPath)), descriptor_(std::make_shared<VoxelGridDescriptor>())
{
    auto& grid = *descriptor_;
    const auto& path = path_;
    IniReader reader;
    {
        const auto input = input_provenance::ReadFile(path, "voxel_descriptor", "voxel_parse");
        Remember(grid, input);
        if (const auto line = InvalidUtf8Line(input.bytes)) {
            throw Error(path, line, "expected UTF-8 text without NUL");
        }
        reader.LoadBytes(path, input.bytes);
    }
    for (const auto& duplicate : reader.GetDuplicates()) {
        throw Error(path, duplicate.lineNumber, "duplicate declaration [" + duplicate.section + "] "
                    + duplicate.key + " (first at line " + std::to_string(duplicate.firstLine) + ")");
    }

    std::map<std::string, IniFieldInfo> geometry;
    const auto sections = reader.GetSectionInfo();
    for (const auto& section : sections) {
        const auto& name = section.normalizedSection;
        if (!section.explicitSection || name == "voxel_grid" || name == "materials") continue;
        if (name.compare(0, 4, "roi.") != 0 || name.size() == 4) {
            throw Error(path, section.lineNumber, "unknown section [" + name + "]");
        }
        if (!reader.HasKey(name, "indices_file")) {
            throw Error(path, section.lineNumber, "missing indices_file in [" + name + "]");
        }
    }
    for (const auto& field : reader.GetFields()) {
        const auto& section = field.normalizedSection;
        const auto& key = field.normalizedKey;
        if (section == "voxel_grid" && (key == "format_version" || key == "shape"
                                        || key == "pitch_mm" || key == "labels_file")) {
            geometry.emplace(key, field);
        } else if (section == "materials") {
            const auto label = Integer(key, std::numeric_limits<std::uint16_t>::max(), path, field.lineNumber, "material label");
            if (field.value.empty()) throw Error(path, field.lineNumber, "material name must not be empty");
            if (!grid.materials.emplace(static_cast<std::uint16_t>(label), field.value).second) {
                throw Error(path, field.lineNumber, "duplicate numeric material label " + std::to_string(label));
            }
        } else if (section.compare(0, 4, "roi.") == 0 && key == "indices_file") {
            roiFiles_.emplace(section.substr(4), field);
        } else {
            throw Error(path, field.lineNumber, "unknown field [" + section + "] " + key);
        }
    }
    for (const std::string key : {"format_version", "shape", "pitch_mm", "labels_file"}) {
        if (!geometry.count(key)) throw Error(path, 0, "missing [voxel_grid] " + key);
    }
    const auto& version = geometry.at("format_version");
    if (version.value != "1") throw Error(path, version.lineNumber, "unsupported format_version '" + version.value + "'");

    const auto& shape = geometry.at("shape");
    const auto& pitch = geometry.at("pitch_mm");
    const auto dimensions = Triple(shape, path);
    const auto pitches = Triple(pitch, path);
    constexpr auto maxCount = std::numeric_limits<int>::max();
    for (std::size_t axis = 0; axis < grid.shape.size(); ++axis) {
        const auto count = Integer(dimensions[axis], maxCount, path, shape.lineNumber, "shape axis");
        if (count == 0 || cellCount_ > static_cast<std::size_t>(maxCount) / count) {
            throw Error(path, shape.lineNumber, "shape must be positive and fit the Geant4 copy-number interface");
        }
        grid.shape[axis] = static_cast<int>(count);
        cellCount_ *= count;
        std::istringstream value(pitches[axis]);
        value.imbue(std::locale::classic());
        value >> std::noskipws >> grid.pitchMm[axis];
        const double span = grid.pitchMm[axis] * count;
        if (!value || !value.eof() || !std::isfinite(grid.pitchMm[axis]) || grid.pitchMm[axis] <= minPitchMm
            || grid.pitchMm[axis] / 2 == 0 || !std::isfinite(span)) {
            throw Error(path, pitch.lineNumber, "pitch_mm must exceed the geometry tolerance and its span must be finite");
        }
        grid.spanMm[axis] = span;
    }
    if (cellCount_ > std::numeric_limits<std::size_t>::max() / 4) {
        throw Error(path, shape.lineNumber, "grid byte count overflows size_t");
    }

    labelFile_ = geometry.at("labels_file");
}

void VoxelGridDescriptorReader::ReadPayload()
{
    auto& grid = *descriptor_;
    const auto& path = path_;
    const auto cellCount = cellCount_;
    const auto payloadPath = [&](const IniFieldInfo& field) {
        try { return RelativeTo(path, field.value); }
        catch (const std::exception& error) {
            throw Error(path, field.lineNumber, field.key + ": " + error.what());
        }
    };
    const auto readPayload = [&](const IniFieldInfo& field, const std::string& payload,
                                 std::size_t limit, const std::string& kind) {
        try {
            auto input = input_provenance::ReadFile(payload, kind, "voxel_parse", limit);
            Remember(grid, input);
            return input;
        } catch (const std::exception& error) {
            throw Error(path, field.lineNumber, field.key + ": " + error.what());
        }
    };
    {
        const auto& labelField = labelFile_;
        const auto input = readPayload(labelField, payloadPath(labelField), cellCount * 2, "voxel_labels");
        if (input.bytes.size() != cellCount * 2) {
            throw Error(path, labelField.lineNumber, "labels_file byte length must be exactly "
                        + std::to_string(cellCount * 2) + ": '" + input.path + "'");
        }
        grid.labels.reserve(cellCount);
        for (std::size_t q = 0; q < cellCount; ++q) {
            const auto label = static_cast<std::uint16_t>(LittleEndian(input.bytes, q * 2, 2));
            if (!grid.materials.count(label)) {
                throw Error(path, labelField.lineNumber, "unmapped material label " + std::to_string(label)
                            + " at q=" + std::to_string(q) + ": '" + input.path + "'");
            }
            grid.labels.push_back(label);
        }
    }
    std::map<std::string, std::string> roiByPath;
    for (const auto& item : roiFiles_) {
        const auto& field = item.second;
        const auto payload = payloadPath(field);
        const auto first = roiByPath.emplace(payload, item.first);
        if (!first.second) {
            grid.rois.emplace(item.first, grid.rois.at(first.first->second));
            grid.roiInputIndices.emplace(item.first, grid.roiInputIndices.at(first.first->second));
            continue;
        }
        const auto input = readPayload(field, payload, cellCount * 4, "voxel_roi");
        grid.roiInputIndices.emplace(item.first, grid.inputs.size() - 1);
        if (input.bytes.empty() || input.bytes.size() % 4 != 0) {
            throw Error(path, field.lineNumber, "indices_file must have a nonempty whole number of uint32 entries: '" + input.path + "'");
        }
        auto& indices = grid.rois[item.first];
        indices.reserve(input.bytes.size() / 4);
        for (std::size_t offset = 0; offset < input.bytes.size(); offset += 4) {
            const auto q = LittleEndian(input.bytes, offset, 4);
            if (q >= cellCount || (!indices.empty() && q <= indices.back())) {
                throw Error(path, field.lineNumber, "indices_file must be strictly increasing with q in range at entry "
                            + std::to_string(offset / 4) + ": '" + input.path + "'");
            }
            indices.push_back(q);
        }
    }
}
