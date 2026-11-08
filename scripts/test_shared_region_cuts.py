"""Read actual shared-region kernel cuts, including reversed declarations."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def exercise(root, executable):
    receipts, failures = [], []
    for mode in ("same", "complement", "conflict"):
        for reverse in (False, True):
            name = mode + ("-reversed" if reverse else "-forward")
            work = root / name
            work.mkdir(parents=True, exist_ok=False)
            requested = [{"e-": .001}, {"e-": .001} if mode == "same" else
                         {"gamma": .002} if mode == "complement" else {"e-": 1.0}]
            # Swap name-to-cut assignment too: the parser may sort sibling names,
            # so reversing INI sections alone does not reverse build precedence.
            labels = "BA" if reverse else "AB"
            volumes = []
            for index, cuts in enumerate(requested):
                label = labels[index]
                volumes.append(f"[volume.{label}]\nparent=world\nshape=box\nsize=10 mm,10 mm,10 mm\n"
                    f"position={-20 if index == 0 else 20} mm,0,0\nmaterial=G4_Si\nregion=shared\n" +
                    "".join(f"cut.{particle}={value:.17g} mm\n" for particle, value in cuts.items()))
            geometry = work / "geometry.ini"
            geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n" +
                "".join(reversed(volumes) if reverse else volumes), encoding="utf-8")
            output = work / "output"
            config, macro = work / "main.ini", work / "run.mac"
            config.write_text(f"[geometry]\ntemplate=hierarchical\nconfig={geometry.as_posix()}\n"
                f"[run]\nthreads=1\n[output]\ndir={output.as_posix()}\n", encoding="utf-8")
            macro.write_text("/run/initialize\n", encoding="utf-8")
            argv = [str(executable), "--config", str(config), "--macro", str(macro)]
            result = subprocess.run(argv, cwd=work, capture_output=True, timeout=120)
            (work / "stdout.log").write_bytes(result.stdout)
            (work / "stderr.log").write_bytes(result.stderr)
            row = {"case": name, "argv": argv, "exit_code": result.returncode,
                   "geometry_sha256": hashlib.sha256(geometry.read_bytes()).hexdigest(), "observed": {}}
            try:
                if mode == "conflict":
                    text = (result.stdout + result.stderr).decode("utf-8", errors="replace")
                    assert result.returncode != 0, "conflicting cuts accepted"
                    assert "shared" in text and "conflict" in text.lower(), text[-1500:]
                    assert "created_geometry_object_count=0" in text, "conflict not proven before objects"
                else:
                    assert result.returncode == 0, result.stderr[-1000:]
                    snapshot = json.loads((output / "effective_config_finalization.json").read_text(encoding="utf-8"))
                    for index, cuts in enumerate(requested):
                        path = f"/geometry/objects/{labels[index]}/production_cuts"
                        found = [r for r in snapshot["evidence"] if r["path"] == path and r["stage"] == "geometry_construct"]
                        assert found, path
                        row["observed"][path] = found[-1]["observed"]
                        assert found[-1]["evidence_level"] == "kernel_constructed"
                        assert found[-1]["observed"] == cuts, (path, found[-1]["observed"], cuts)
                        assert found[-1]["matches_resolved_value"] is True
                row["status"] = "pass"
            except AssertionError as error:
                row.update(status="fail", error=str(error))
                failures.append(name + ": " + str(error))
            receipts.append(row)
            (root / "receipt.json").write_text(json.dumps({"executable": str(executable),
                "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
                "cases": receipts, "failures": failures}, indent=2), encoding="utf-8")
    assert not failures, failures
    print("Shared region cuts: 6 real kernel cases passed")


def main():
    executable = Path(os.environ["G4USIM_EXE"]).resolve()
    assert executable.is_file(), executable
    evidence = os.environ.get("G4USIM_TEST_EVIDENCE_DIR")
    if evidence:
        root = Path(evidence).resolve()
        root.mkdir(parents=True, exist_ok=True)
        exercise(root, executable)
    else:
        with tempfile.TemporaryDirectory(prefix="g4usim-region-") as directory:
            exercise(Path(directory), executable)


if __name__ == "__main__":
    main()
