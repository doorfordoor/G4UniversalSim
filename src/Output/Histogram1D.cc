#include "Output/Histogram1D.hh"

#include "Output/CsvWriter.hh"

#include <cmath>
#include <stdexcept>

Histogram1D::Histogram1D(const std::string& name, int bins, double min, double max)
{
    Configure(name, bins, min, max);
}

void Histogram1D::Configure(const std::string& name, int bins, double min, double max)
{
    if (bins <= 0) {
        throw std::runtime_error("Histogram1D '" + name + "' requires bins > 0");
    }
    if (!(max > min)) {
        throw std::runtime_error("Histogram1D '" + name + "' requires max > min");
    }

    name_ = name;
    bins_ = bins;
    min_ = min;
    max_ = max;
    counts_.assign(static_cast<std::size_t>(bins_), 0.0);
    Reset();
}

void Histogram1D::Fill(double value, double weight)
{
    ValidateConfigured();

    ++entries_;
    sumWeight_ += weight;

    if (value < min_) {
        underflow_ += weight;
        return;
    }
    if (value >= max_) {
        overflow_ += weight;
        return;
    }

    int bin = static_cast<int>(std::floor((value - min_) / BinWidth()));
    if (bin < 0) {
        bin = 0;
    } else if (bin >= bins_) {
        bin = bins_ - 1;
    }
    counts_[static_cast<std::size_t>(bin)] += weight;
}

void Histogram1D::Merge(const Histogram1D& other)
{
    CheckCompatible(other);

    for (int i = 0; i < bins_; ++i) {
        counts_[static_cast<std::size_t>(i)] += other.counts_[static_cast<std::size_t>(i)];
    }
    underflow_ += other.underflow_;
    overflow_ += other.overflow_;
    entries_ += other.entries_;
    sumWeight_ += other.sumWeight_;
}

void Histogram1D::Reset()
{
    for (double& count : counts_) {
        count = 0.0;
    }
    underflow_ = 0.0;
    overflow_ = 0.0;
    entries_ = 0.0;
    sumWeight_ = 0.0;
}

void Histogram1D::WriteCSV(const std::string& filename) const
{
    ValidateConfigured();

    CsvWriter writer(filename);
    writer.WriteHeader({"bin", "low_edge", "high_edge", "center", "count"});

    const double width = BinWidth();
    for (int i = 0; i < bins_; ++i) {
        const double low = min_ + i * width;
        const double high = low + width;
        writer.WriteRow({
            std::to_string(i),
            std::to_string(low),
            std::to_string(high),
            std::to_string(0.5 * (low + high)),
            std::to_string(counts_[static_cast<std::size_t>(i)])
        });
    }
}

const std::string& Histogram1D::GetName() const
{
    return name_;
}

int Histogram1D::GetBins() const
{
    return bins_;
}

double Histogram1D::GetMin() const
{
    return min_;
}

double Histogram1D::GetMax() const
{
    return max_;
}

double Histogram1D::GetBinContent(int bin) const
{
    ValidateConfigured();
    if (bin < 0 || bin >= bins_) {
        throw std::runtime_error(
            "Histogram1D '" + name_ + "' bin out of range: " + std::to_string(bin)
        );
    }
    return counts_[static_cast<std::size_t>(bin)];
}

double Histogram1D::GetUnderflow() const
{
    return underflow_;
}

double Histogram1D::GetOverflow() const
{
    return overflow_;
}

double Histogram1D::GetEntries() const
{
    return entries_;
}

double Histogram1D::GetSumWeight() const
{
    return sumWeight_;
}

void Histogram1D::ValidateConfigured() const
{
    if (bins_ <= 0 || counts_.empty()) {
        throw std::runtime_error("Histogram1D is not configured");
    }
}

void Histogram1D::CheckCompatible(const Histogram1D& other) const
{
    ValidateConfigured();
    other.ValidateConfigured();

    if (name_ != other.name_ || bins_ != other.bins_
        || min_ != other.min_ || max_ != other.max_) {
        throw std::runtime_error(
            "Histogram1D merge requires matching name/bins/range: '" + name_
            + "' vs '" + other.name_ + "'"
        );
    }
}

double Histogram1D::BinWidth() const
{
    return (max_ - min_) / static_cast<double>(bins_);
}
