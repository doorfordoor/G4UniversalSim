#!/usr/bin/env python3
import argparse
import csv
import sys


def read_histogram(path):
    lows, highs, values = [], [], []
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        value_field = "count"
        for candidate in ("count", "value", "sum", "weighted_count", "raw_count"):
            if candidate in fields:
                value_field = candidate
                break
        for row in reader:
            lows.append(float(row["bin_low"]))
            highs.append(float(row["bin_high"]))
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
