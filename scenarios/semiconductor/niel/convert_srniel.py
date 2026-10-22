"""Converts SR-NIEL web calculator result pages into NIEL tables for [scoring.displacement].

The SR-NIEL calculators (https://www.sr-niel.org/index.php/sr-niel-web-calculators)
open a result page (http://www.sr-niel.org/Simulation/<id>niel_<p|e|n>.html) with a
table "Energy (MeV) | NIEL (MeV cm2 g-1) | NIEL Dose (MeV g-1) | NIEL Dose (Gy)".
Save that page and run

    python scenarios/semiconductor/niel/convert_srniel.py <result.html> <out.csv> "<description>"

The output has the header energy_MeV,niel_MeV_cm2_g, energies in increasing order
(neutron pages list them decreasing) and the description plus the page's input
parameters as '#' comments. When the lowest tabulated NIEL is zero (below the
displacement threshold) a zero row at 1 eV is added, marked by a comment, so that
low-energy secondaries are scored as zero damage instead of out of range.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROW = re.compile(r"(\d\.\d{4}e[+-]\d\d)\s+(\d\.\d{4}e[+-]\d\d)\s+\d\.\d{4}e[+-]\d\d\s+\d\.\d{4}e[+-]\d\d")


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    source, target, description = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    text = html.unescape(re.sub(r"<[^>]+>", " ", source.read_text(encoding="utf-8", errors="replace")))
    rows = sorted({(float(e), float(v)) for e, v in ROW.findall(text)})
    energies = [e for e, _ in rows]
    if len(rows) < 2 or len(set(energies)) != len(energies):
        raise SystemExit(f"{source}: no usable NIEL table (or repeated energies)")
    start = text.find("Input Parameters")
    end = text.find("Energy (MeV)", start)
    inputs = [re.sub(r"\s+", " ", line).strip() for line in text[start:end].splitlines()]
    lines = [f"# {description}"] + [f"# {line}" for line in inputs if line]
    if rows[0][1] == 0.0 and rows[0][0] > 1e-6:
        # The source table is already zero at its lowest energies (below the displacement
        # threshold), so NIEL is zero below it as well; this row only extends that zero.
        lines.append(f"# added: 1e-06 MeV (1 eV), NIEL 0 - below the displacement threshold, extends the "
                     f"source's zero values below {rows[0][0]:g} MeV")
        rows.insert(0, (1e-6, 0.0))
    lines.append("energy_MeV,niel_MeV_cm2_g")
    lines += [f"{e:.5g},{v:.5g}" for e, v in rows]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{target}: {len(rows)} rows, {rows[0][0]:g}-{rows[-1][0]:g} MeV")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
