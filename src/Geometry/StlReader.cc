#include "Geometry/StlReader.hh"

#include "Utils/StringUtils.hh"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <map>
#include <sstream>
#include <stdexcept>
#include <tuple>

namespace {

using Vertex = std::array<double, 3>;

std::vector<std::array<Vertex, 3>> ReadAscii(const std::string& text, const std::string& path)
{
    std::vector<std::array<Vertex, 3>> facets;
    std::istringstream input(text);
    std::string token;
    std::array<Vertex, 3> current{};
    int vertexCount = 0;
    while (input >> token) {
        const std::string lower = StringUtils::ToLower(token);
        if (lower == "vertex") {
            Vertex v{};
            if (!(input >> v[0] >> v[1] >> v[2])) {
                throw std::runtime_error("STL '" + path + "': malformed vertex line");
            }
            if (vertexCount >= 3) throw std::runtime_error("STL '" + path + "': facet with more than 3 vertices");
            current[vertexCount++] = v;
        } else if (lower == "endfacet") {
            if (vertexCount != 3) throw std::runtime_error("STL '" + path + "': facet without 3 vertices");
            facets.push_back(current);
            vertexCount = 0;
        }
    }
    return facets;
}

std::vector<std::array<Vertex, 3>> ReadBinary(const std::string& data, const std::string& path)
{
    if (data.size() < 84) throw std::runtime_error("STL '" + path + "': file too short for binary STL");
    std::uint32_t count = 0;
    std::memcpy(&count, data.data() + 80, 4);
    if (data.size() != 84 + static_cast<std::size_t>(count) * 50) {
        throw std::runtime_error("STL '" + path + "': binary size does not match its triangle count");
    }
    std::vector<std::array<Vertex, 3>> facets(count);
    for (std::uint32_t i = 0; i < count; ++i) {
        const char* record = data.data() + 84 + static_cast<std::size_t>(i) * 50 + 12;  // skip normal
        for (int corner = 0; corner < 3; ++corner) {
            for (int axis = 0; axis < 3; ++axis) {
                float value = 0.0f;
                std::memcpy(&value, record + (corner * 3 + axis) * 4, 4);
                facets[i][corner][axis] = value;
            }
        }
    }
    return facets;
}

}  // namespace

namespace StlReader {

StlMesh Read(const std::string& path, double lengthUnit)
{
    if (!(lengthUnit > 0.0)) throw std::runtime_error("STL length unit must be > 0");
    std::ifstream input(std::filesystem::u8path(path), std::ios::binary);
    if (!input) throw std::runtime_error("Cannot open STL file '" + path + "'");
    const std::string data((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());

    // Binary files may also start with "solid"; trust the size check first.
    std::vector<std::array<Vertex, 3>> facets;
    bool binary = false;
    if (data.size() >= 84) {
        std::uint32_t count = 0;
        std::memcpy(&count, data.data() + 80, 4);
        binary = data.size() == 84 + static_cast<std::size_t>(count) * 50;
    }
    facets = binary ? ReadBinary(data, path) : ReadAscii(data, path);
    if (facets.size() < 4) throw std::runtime_error("STL '" + path + "' needs at least 4 triangles");

    StlMesh mesh;
    Vertex lo{1e300, 1e300, 1e300}, hi{-1e300, -1e300, -1e300};
    for (const auto& facet : facets) {
        for (const auto& v : facet) {
            for (int axis = 0; axis < 3; ++axis) {
                if (!std::isfinite(v[axis])) throw std::runtime_error("STL '" + path + "' has a nonfinite coordinate");
                lo[axis] = std::min(lo[axis], v[axis]);
                hi[axis] = std::max(hi[axis], v[axis]);
            }
        }
    }
    const double extent = std::max({hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]});
    if (!(extent > 0.0)) throw std::runtime_error("STL '" + path + "' is degenerate");
    const double tolerance = extent * 1e-9;

    // Weld vertices on a tolerance grid.
    std::map<std::tuple<long long, long long, long long>, int> index;
    auto weld = [&](const Vertex& v) {
        const auto key = std::make_tuple(std::llround(v[0] / tolerance), std::llround(v[1] / tolerance),
                                         std::llround(v[2] / tolerance));
        const auto found = index.find(key);
        if (found != index.end()) return found->second;
        const int id = static_cast<int>(mesh.vertices.size());
        mesh.vertices.push_back({v[0] * lengthUnit, v[1] * lengthUnit, v[2] * lengthUnit});
        index.emplace(key, id);
        return id;
    };
    for (const auto& facet : facets) {
        const std::array<int, 3> tri{weld(facet[0]), weld(facet[1]), weld(facet[2])};
        if (tri[0] == tri[1] || tri[1] == tri[2] || tri[0] == tri[2]) {
            throw std::runtime_error("STL '" + path + "' contains a degenerate triangle");
        }
        mesh.triangles.push_back(tri);
    }

    // Closed manifold: each undirected edge is used by exactly two triangles,
    // once in each direction (consistent orientation).
    std::map<std::pair<int, int>, int> directed;
    for (const auto& tri : mesh.triangles) {
        for (int k = 0; k < 3; ++k) {
            const auto edge = std::make_pair(tri[k], tri[(k + 1) % 3]);
            if (++directed[edge] > 1) {
                throw std::runtime_error("STL '" + path + "' is not a consistently oriented manifold "
                                         "(an edge is used twice in the same direction)");
            }
        }
    }
    for (const auto& item : directed) {
        if (!directed.count({item.first.second, item.first.first})) {
            throw std::runtime_error("STL '" + path + "' is not closed (open edge between vertices " +
                                     std::to_string(item.first.first) + " and " + std::to_string(item.first.second) + ")");
        }
    }

    // Signed volume (divergence theorem); flip if the mesh is inside out.
    double volume = 0.0;
    for (const auto& tri : mesh.triangles) {
        const auto& a = mesh.vertices[tri[0]];
        const auto& b = mesh.vertices[tri[1]];
        const auto& c = mesh.vertices[tri[2]];
        volume += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) +
                   a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0;
    }
    if (std::abs(volume) <= 1e-12 * std::pow(extent * lengthUnit, 3)) {
        throw std::runtime_error("STL '" + path + "' encloses no volume");
    }
    if (volume < 0.0) {
        for (auto& tri : mesh.triangles) std::swap(tri[1], tri[2]);
        volume = -volume;
    }
    mesh.volume = volume;
    for (int axis = 0; axis < 3; ++axis) {
        mesh.minCorner[axis] = lo[axis] * lengthUnit;
        mesh.maxCorner[axis] = hi[axis] * lengthUnit;
    }
    return mesh;
}

}  // namespace StlReader
