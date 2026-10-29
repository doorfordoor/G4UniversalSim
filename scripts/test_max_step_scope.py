"""V-02: preserve and document default charged-only StepLimiter semantics."""
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

from test_physics_a6 import Runner, WORLD, volume


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="g4usim_max_step_") as work:
        runner = Runner(Path(work))
        geometry = WORLD + volume("Det", "shape=box\nsize=20 mm,20 mm,20 mm\nregion=DetRegion",
                                  material="G4_Galactic", sensitive=False)
        for reference in ("", "FTFP_BERT_EMZ"):
            for particle in ("proton", "gamma"):
                extra = (f"[source]\nparticle={particle}\nenergy=1 MeV\nposition_type=point\n"
                         "position=0,0,0 mm\ndirection=+x\n[physics.region.DetRegion]\nmax_step=1 mm\n"
                         "[output]\ntrajectories=4\n")
                out, dump, _ = runner.run(geometry, extra, 4, reference=reference,
                                          physics="modules=G4EmStandardPhysics_option4" if not reference else "")
                summary = dict(line.split("=", 1) for line in (out / "run_summary.txt").read_text().splitlines()
                               if "=" in line)
                summary = {key.strip(): value.strip() for key, value in summary.items()}
                assert summary["status"] == "completed" and summary["actual_completed_event_count"] == "4"
                processes = {item["name"] for item in next(p for p in dump["particles"]
                                                          if p["name"] == particle)["processes"]}
                assert ("StepLimiter" in processes) == (particle == "proton"), processes
                if particle == "gamma":
                    assert "UserSpecialCut" in processes, processes
                count = 0
                for path in out.glob("trajectories_t*.json"):
                    data = json.loads(path.read_text())
                    for event in data["events"]:
                        track = next(t for t in event["tracks"] if t["parent"] == 0)
                        points = track["points"]
                        lengths = [math.dist(a[:3], b[:3]) for a, b in zip(points, points[1:])
                                   if event["volumes"][int(b[4])] == "Det_PV"]
                        assert lengths, track
                        if particle == "proton":
                            assert max(lengths) <= 1.0 + 1e-6, lengths
                            assert len(lengths) >= 10, lengths
                        else:
                            assert len(lengths) == 1 and abs(lengths[0] - 10.0) < 1e-6, lengths
                        count += 1
                assert count == 4, count
    print("test_max_step_scope: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
