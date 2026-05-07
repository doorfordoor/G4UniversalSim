#include "Output/Histogram2D.hh"

#include "Output/CsvWriter.hh"

#include <cmath>
#include <stdexcept>

Histogram2D::Histogram2D(
    const std::string& name,
    int xBins,
    double xMin,
    double xMax,
    int yBins,
    double yMin,
    double yMax
)
{
    Configure(name, xBins, xMin, xMax, yBins, yMin, yMax);
}

void Histogram2D::Configure(
    const std::string& name,
    int xBins,
    double xMin,
    double xMax,
    int yBins,
    double yMin,
    double yMax
)
{
    if (xBins <= 0 || yBins <= 0) {
        throw std::runtime_error("Histogram2D '" + name + "' requires positive bin counts");
    }
    if (!(xMax > xMin) || !(yMax > yMin)) {
        throw std::runtime_error("Histogram2D '" + name + "' requires max > min on both axes");
    }

    name_ = name;
    xBins_ = xBins;
    xMin_ = xMin;
    xMax_ = xMax;
    yBins_ = yBins;
    yMin_ = yMin;
    yMax_ = yMax;
    counts_.assign(static_cast<std::size_t>(xBins_ * yBins_), 0.0);
    Reset();
}

void Histogram2D::Fill(double x, double y, double weight)
{
    ValidateConfigured();
    ++entries_;

    if (x < xMin_ || y < yMin_) {
        underflow_ += weight;
        return;
    }
    if (x >= xMax_ || y >= yMax_) {
        overflow_ += weight;
        return;
    }

    int xBin = static_cast<int>(std::floor((x - xMin_) / XWidth()));
    int yBin = static_cast<int>(std::floor((y - yMin_) / YWidth()));
    xBin = std::max(0, std::min(xBin, xBins_ - 1));
    yBin = std::max(0, std::min(yBin, yBins_ - 1));

    counts_[Index(xBin, yBin)] += weight;
}

void Histogram2D::Merge(const Histogram2D& other)
{
    CheckCompatible(other);

    for (std::size_t i = 0; i < counts_.size(); ++i) {
        counts_[i] += other.counts_[i];
    }
    underflow_ += other.underflow_;
    overflow_ += other.overflow_;
    entries_ += other.entries_;
}

void Histogram2D::Reset()
{
    for (double& count : counts_) {
        count = 0.0;
    }
    underflow_ = 0.0;
    overflow_ = 0.0;
    entries_ = 0.0;
}

void Histogram2D::WriteCSV(const std::string& filename) const
{
    ValidateConfigured();

    CsvWriter writer(filename);
    writer.WriteHeader({"x_bin", "y_bin", "x_low", "x_high", "y_low", "y_high", "count"});

    const double xWidth = XWidth();
    const double yWidth = YWidth();
    for (int xBin = 0; xBin < xBins_; ++xBin) {
        const double xLow = xMin_ + xBin * xWidth;
        const double xHigh = xLow + xWidth;
        for (int yBin = 0; yBin < yBins_; ++yBin) {
            const double yLow = yMin_ + yBin * yWidth;
            const double yHigh = yLow + yWidth;
            writer.WriteRow({
                std::to_string(xBin),
                std::to_string(yBin),
                std::to_string(xLow),
                std::to_string(xHigh),
                std::to_string(yLow),
                std::to_string(yHigh),
                std::to_string(counts_[Index(xBin, yBin)])
            });
        }
    }
}

const std::string& Histogram2D::GetName() const
{
    return name_;
}

double Histogram2D::GetUnderflow() const
{
    return underflow_;
}

double Histogram2D::GetOverflow() const
{
    return overflow_;
}

double Histogram2D::GetEntries() const
{
    return entries_;
}

void Histogram2D::ValidateConfigured() const
{
    if (xBins_ <= 0 || yBins_ <= 0 || counts_.empty()) {
        throw std::runtime_error("Histogram2D is not configured");
    }
}

void Histogram2D::CheckCompatible(const Histogram2D& other) const
{
    ValidateConfigured();
    other.ValidateConfigured();

    if (name_ != other.name_ || xBins_ != other.xBins_ || yBins_ != other.yBins_
        || xMin_ != other.xMin_ || xMax_ != other.xMax_
        || yMin_ != other.yMin_ || yMax_ != other.yMax_) {
        throw std::runtime_error(
            "Histogram2D merge requires matching name/bins/range: '" + name_
            + "' vs '" + other.name_ + "'"
        );
    }
}

double Histogram2D::XWidth() const
{
    return (xMax_ - xMin_) / static_cast<double>(xBins_);
}

double Histogram2D::YWidth() const
{
    return (yMax_ - yMin_) / static_cast<double>(yBins_);
}

std::size_t Histogram2D::Index(int xBin, int yBin) const
{
    return static_cast<std::size_t>(xBin * yBins_ + yBin);
}
