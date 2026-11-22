#include "Output/Histogram1D.hh"
#include "Output/NamedHistogram2D.hh"
#include <cmath>
#include <iostream>

int main()
{
    Histogram1D bins("edge", 9, 0.0, 1.0);
    const double edge = bins.EqualBinEdge(7);
    bins.FillUnitAtEdges(std::nextafter(edge, 0.0));
    bins.FillUnitAtEdges(edge);
    bins.FillUnitAtEdges(std::nextafter(edge, 1.0));
    bins.FillUnitAtEdges(1.0);
    if (bins.GetBinContent(6) != 1 || bins.GetBinContent(7) != 2 || bins.GetOverflow() != 1) {
        std::cerr << "wrong count at the exported edge or its adjacent values\n";
        return 1;
    }
    NamedHistogram2D plane("joint", {9, 0, 1}, {9, 0, 1});
    plane.Fill(edge, std::nextafter(edge, 0.0));
    plane.Fill(-1, 1);
    plane.Fill(1, -1);
    if (plane.Cell(7, 6) != 1 || plane.Cell(-1, 9) != 1 || plane.Cell(9, -1) != 1 ||
        plane.GetEntries() != 3) return 1;
    return 0;
}
