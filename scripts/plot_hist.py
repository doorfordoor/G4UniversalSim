#!/usr/bin/env python3
import argparse
import csv
import sys


def read_histogram(path):
    lows, highs, values = [], [], []
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        low_field = next((name for name in ("low_edge_MeV", "low_edge", "bin_low_MeV", "bin_low") if name in fields), "")
        high_field = next((name for name in ("high_edge_MeV", "high_edge", "bin_high_MeV", "bin_high") if name in fields), "")
        if low_field not in fields or high_field not in fields:
            raise ValueError(f"Unsupported histogram CSV header: {fields}")
        value_field = "count"
        for candidate in ("count", "value", "sum", "weighted_count", "raw_count"):
            if candidate in fields:
                value_field = candidate
                break
        for row in reader:
            lows.append(float(row[low_field]))
            highs.append(float(row[high_field]))
            values.append(float(row[value_field]))
    return lows, highs, values


def main():
    parser = argparse.ArgumentParser(description="Plot a G4UniversalSim histogram CSV.")
    parser.add_argument("--input", required=True, help="Input histogram CSV")
    parser.add_argument("--output", required=True, help="Output image path")
    parser.add_argument("--title", default="Histogram", help="Plot title")
    parser.add_argument("--xlabel", default="Value", help="X axis label")
    parser.add_argument("--ylabel", default="Count", help="Y axis label")
    parser.add_argument("--style", choices=("step", "line"), default="step")
    args = parser.parse_args()

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("plot_hist.py requires matplotlib. Install it with: python -m pip install matplotlib", file=sys.stderr)
        return 2

    lows, highs, values = read_histogram(args.input)
    centers = [(lo + hi) * 0.5 for lo, hi in zip(lows, highs)]

    plt.figure(figsize=(8, 5))
    if args.style == "step":
        plt.step(lows + [highs[-1]], values + [values[-1]], where="post")
    else:
        plt.plot(centers, values)
    plt.title(args.title)
    plt.xlabel(args.xlabel)
    plt.ylabel(args.ylabel)
    plt.tight_layout()
    plt.savefig(args.output, dpi=160)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
