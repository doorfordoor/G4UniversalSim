#pragma once

#include "Output/EqualHistogramAxis.hh"
#include "Output/Histogram2D.hh"

// Store flow rows and columns in regular cells of an integer-indexed grid.
// The shared Histogram2D accumulation/merge then preserves every edge and corner.
class NamedHistogram2D {
public:
    NamedHistogram2D(const std::string& name, EqualHistogramAxis x, EqualHistogramAxis y)
        : x_(x), y_(y), grid_(name, x.bins + 2, 0, x.bins + 2, y.bins + 2, 0, y.bins + 2) {}
    void Fill(double raw, double weighted) { grid_.Fill(x_.Locate(raw) + 1, y_.Locate(weighted) + 1); }
    void Merge(const NamedHistogram2D& other) {
        if (!(x_ == other.x_ && y_ == other.y_)) throw std::runtime_error("named H2 axis mismatch");
        grid_.Merge(other.grid_);
    }
    void Reset() { grid_.Reset(); }
    const std::string& GetName() const { return grid_.GetName(); }
    double GetEntries() const { return grid_.GetEntries(); }
    double Cell(int x, int y) const { return grid_.GetBinContent(x + 1, y + 1); }
    const EqualHistogramAxis& X() const { return x_; }
    const EqualHistogramAxis& Y() const { return y_; }
private:
    EqualHistogramAxis x_;
    EqualHistogramAxis y_;
    Histogram2D grid_;
};
