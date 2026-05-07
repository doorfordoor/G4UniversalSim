#pragma once

#include <string>
#include <vector>

class Histogram2D {
public:
    Histogram2D() = default;

    Histogram2D(
        const std::string& name,
        int xBins,
        double xMin,
        double xMax,
        int yBins,
        double yMin,
        double yMax
    );

    void Configure(
        const std::string& name,
        int xBins,
        double xMin,
        double xMax,
        int yBins,
        double yMin,
        double yMax
    );

    void Fill(double x, double y, double weight = 1.0);

    void Merge(const Histogram2D& other);

    void Reset();

    void WriteCSV(const std::string& filename) const;

    const std::string& GetName() const;
    double GetUnderflow() const;
    double GetOverflow() const;
    double GetEntries() const;

private:
    void ValidateConfigured() const;
    void CheckCompatible(const Histogram2D& other) const;
    double XWidth() const;
    double YWidth() const;
    std::size_t Index(int xBin, int yBin) const;

    std::string name_;
    int xBins_ = 0;
    double xMin_ = 0.0;
    double xMax_ = 0.0;
    int yBins_ = 0;
    double yMin_ = 0.0;
    double yMax_ = 0.0;
    std::vector<double> counts_;
    double underflow_ = 0.0;
    double overflow_ = 0.0;
    double entries_ = 0.0;
};
