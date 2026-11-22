#pragma once

#include <cmath>
#include <stdexcept>

struct EqualHistogramAxis {
    int bins;
    double low;
    double high;

    double Edge(int i) const {
        return i == bins ? high : low + i * ((high - low) / bins);
    }

    void ValidateEdges() const {
        if (bins <= 0 || !std::isfinite(low) || !std::isfinite(high) ||
            !std::isfinite((high - low) / bins)) throw std::runtime_error("invalid bin width");
        double previous = low;
        for (int i = 1; i <= bins; ++i) {
            const double edge = Edge(i);
            if (!std::isfinite(edge) || !(edge > previous)) throw std::runtime_error("unrepresentable bin edges");
            previous = edge;
        }
    }

    // Return the usual bin index, with -1 / bins denoting underflow / overflow.
    int Locate(double value) const {
        if (!std::isfinite(value)) throw std::runtime_error("nonfinite histogram observation");
        if (value < low) return -1;
        if (value >= high) return bins;
        int left = 0;
        int right = bins;
        while (right - left > 1) {
            const int mid = left + (right - left) / 2;
            if (value < Edge(mid)) right = mid;
            else left = mid;
        }
        return left;
    }

    bool operator==(const EqualHistogramAxis& other) const {
        return bins == other.bins && low == other.low && high == other.high;
    }
};

