#pragma once

#include <string>
#include <vector>

class Histogram1D {
public:
    Histogram1D() = default;

    Histogram1D(const std::string& name, int bins, double min, double max);

    void Configure(const std::string& name, int bins, double min, double max);

    void Fill(double value, double weight = 1.0);

    void Merge(const Histogram1D& other);

    void Reset();

    void WriteCSV(const std::string& filename) const;

    const std::string& GetName() const;
    int GetBins() const;
    double GetMin() const;
    double GetMax() const;

    double GetBinContent(int bin) const;
    double GetUnderflow() const;
    double GetOverflow() const;
    double GetEntries() const;
    double GetSumWeight() const;

private:
    void ValidateConfigured() const;
    void CheckCompatible(const Histogram1D& other) const;
    double BinWidth() const;

    std::string name_;
    int bins_ = 0;
    double min_ = 0.0;
    double max_ = 0.0;
    std::vector<double> counts_;
    double underflow_ = 0.0;
    double overflow_ = 0.0;
    double entries_ = 0.0;
    double sumWeight_ = 0.0;
};
