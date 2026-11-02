"""Verify L1 evidence from this directory and the committed J2 baseline."""
import argparse
import hashlib
import importlib.util
import json
import tempfile
import zipfile
from pathlib import Path


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main(repo):
    here = Path(__file__).resolve().parent
    def read(name):
        return json.loads((here / name).read_bytes())
    index = read("release-index.json")
    replay = read("strict-replay.json")
    manifest = read("manifest.json")
    assert digest((here / "strict-replay.json").read_bytes()) == index["strict_replay_sha256"]
    assert digest((here / "manifest.json").read_bytes()) == replay["manifest_sha256"]
    assert digest((here / "nonvisual-evidence.zip").read_bytes()) == replay["zip_sha256"]
    spec = importlib.util.spec_from_file_location("l1_checker", here / "checker-246e4f6.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    with zipfile.ZipFile(here / "nonvisual-evidence.zip") as archive:
        entries = manifest["entries"]
        assert len(archive.namelist()) == len(entries)
        assert set(archive.namelist()) == {e["archive_path"] for e in entries}
        by_source = {e["source"]: e["archive_path"] for e in entries}
        for e in entries:
            raw = archive.read(e["archive_path"])
            assert len(raw) == e["bytes"] and digest(raw) == e["sha256_raw"]
        with tempfile.TemporaryDirectory() as tmp:
            for number, row in enumerate(replay["reports"]):
                parent = Path(tmp) / str(number)
                parent.mkdir()
                source = Path(row["report"])
                raw = archive.read(by_source[source.as_posix()])
                assert digest(raw) == row["report_sha256"]
                path = parent / "report.json"
                path.write_bytes(raw)
                report = json.loads(raw)
                for case in report["results"]:
                    name = case["log"].replace(chr(92), "/").rsplit("/", 1)[-1]
                    assert name not in ("", ".", "..") and ":" not in name
                    candidates = [source.parent / name, source.parent / "logs" / name]
                    entry = next(by_source[c.as_posix()] for c in candidates if c.as_posix() in by_source)
                    log = archive.read(entry)
                    assert digest(log) == case["log_sha256"]
                    (parent / name).write_bytes(log)
                    case["log"] = name
                base = repo / row["matching_baseline_public_member"]
                baseline = json.loads(base.read_bytes())
                assert digest(base.read_bytes()) == row["matching_baseline_sha256"]
                for case in baseline["results"]:
                    case["log"] = case["log"].replace(chr(92), "/").rsplit("/", 1)[-1]
                    assert any(p.is_file() and digest(p.read_bytes()) == case["log_sha256"]
                               for p in (base.parent / case["log"], base.parent / "logs" / case["log"]))
                checker.validate_report(baseline, report_path=base)
                checker.validate_report(report, report_path=path, baseline=baseline)
    inc = read("bootstrap-fetch-increment-manifest.json")
    package = here / "bootstrap-fetch-increment.zip"
    assert digest(package.read_bytes()) == inc["zip_sha256"]
    with zipfile.ZipFile(package) as archive:
        assert archive.namelist() == [inc["archive_path"]]
        assert digest(archive.read(inc["archive_path"])) == inc["sha256_raw"]
    print(f"Verified {len(entries)+1} original evidence members and {len(replay['reports'])} strict report/baseline pairs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    main(parser.parse_args().repo_root.resolve())
