"""AR4 scan contracts; generated inputs and controlled process evidence, no backend."""
from copy import deepcopy
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from smoke_scans import make_base, expect_error
from g4usim_gui.core import scan
from g4usim_gui.core.scan_paths import prepare_scan_inputs
from g4usim_gui.core.run_editor_model import GPSDefinition
from g4usim_gui.core.persisted_run_evidence import read_persisted_run_evidence


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def reachable_closure_cases(root, base, energy):
    """SCAN-01: traverse actual edges, including aux/ and extensionless inputs."""
    original = scan.create_scan(base, energy, ["3 MeV"], "closure", root / "closure-A")
    a = Path(original.scan_dir)
    point = original.points[0]
    package = Path(point.package_dir)
    aux = package / "aux"
    aux.mkdir()
    leaf = aux / "leaf.mac"
    leaf.write_text("# leaf\n", encoding="utf-8")
    (aux / "child.mac").write_text(f"/control/execute {leaf}\n/control/execute {leaf}\n", encoding="utf-8")
    Path(point.macro).write_text("/control/execute ../aux/child.mac\n", encoding="utf-8")
    # Reachable config semantics, not suffix guessing; leaves may be binary.
    (aux / "mesh.dat").write_bytes(b"\x00\xffnot-an-ini")
    (aux / "geometry-data").write_text("[world]\nfile = mesh.dat\n", encoding="utf-8")
    ini = Path(point.main_ini)
    text = ini.read_text(encoding="utf-8")
    old_geometry = str(package / "config/geometry/geometry.ini")
    ini.write_text(text.replace(old_geometry, str(aux / "geometry-data")), encoding="utf-8")
    # Unreachable files must not be parsed or modified.
    (package / "macros/unreachable.mac").write_text("/control/execute missing-never-used.mac\n", encoding="utf-8")
    original_hashes = hashes(a)

    def copy_case(name):
        b = root / ("closure-" + name)
        shutil.copytree(a, b)
        m = scan.load_manifest(b)
        p = Path(m.points[0].package_dir)
        return b, m, p

    b, m, p = copy_case("valid")
    require_external = prepare_scan_inputs(m)
    assert require_external == []
    assert str(a) not in (p / "aux/child.mac").read_text(encoding="utf-8")
    assert str(p / "aux/leaf.mac") in (p / "aux/child.mac").read_text(encoding="utf-8")
    assert str(p / "aux/mesh.dat") in (p / "aux/geometry-data").read_text(encoding="utf-8")
    assert (p / "aux/mesh.dat").read_bytes() == b"\x00\xffnot-an-ini"
    assert (p / "macros/unreachable.mac").read_bytes() == (package / "macros/unreachable.mac").read_bytes()
    first = hashes(b)
    prepare_scan_inputs(m)
    assert hashes(b) == first
    b, m, p = copy_case("quoted-case-slashes")
    Path(m.points[0].macro).write_text('//CONTROL///EXECUTE "../aux/child.mac" # retained\n', encoding="utf-8")
    assert prepare_scan_inputs(m) == []
    assert str(a) not in (p / "aux/child.mac").read_text(encoding="utf-8")
    assert '# retained' in Path(m.points[0].macro).read_text(encoding="utf-8")
    for name in ("cycle", "missing", "missing-config-resource"):
        b, m, p = copy_case(name)
        if name == "cycle":
            (p / "aux/leaf.mac").write_text("/control/execute child.mac\n", encoding="utf-8")
            message = "Cyclic"
        elif name == "missing":
            (p / "aux/child.mac").write_text("/control/execute absent.mac\n", encoding="utf-8")
            message = "Missing"
        else:
            (p / "aux/mesh.dat").unlink()
            message = "Missing"
        before = hashes(b)
        expect_error(lambda: prepare_scan_inputs(m), message)
        assert hashes(b) == before, "closure rejection must precede all writes"

    outside = root / "external-closure"
    outside.mkdir()
    (outside / "leaf.mac").write_text("# external leaf\n", encoding="utf-8")
    external = outside / "child.mac"
    external.write_text("/control/execute leaf.mac\n", encoding="utf-8")
    b, m, p = copy_case("external")
    Path(m.points[0].macro).write_text(f"/control/execute {external}\n", encoding="utf-8")
    ext_before = hashes(outside)
    assert prepare_scan_inputs(m) == sorted([str(external), str(outside / "leaf.mac")])
    assert hashes(outside) == ext_before
    # Read-only external macros requiring A->B rewriting cannot be admitted.
    external.write_text(f"/control/execute {leaf}\n", encoding="utf-8")
    before, ext_before = hashes(b), hashes(outside)
    expect_error(lambda: prepare_scan_inputs(m), "External scan input requires relocation")
    assert hashes(b) == before and hashes(outside) == ext_before
    # An external geometry config may retain a relative, external resource;
    # both are explicit, read-only dependencies even without INI extensions.
    external_geometry = outside / "geometry-data"
    external_geometry.write_text("[world]\nfile = resource.dat\n", encoding="utf-8")
    (outside / "resource.dat").write_bytes(b"\xffresource")
    b, m, p = copy_case("external-config")
    ini = Path(m.points[0].main_ini)
    ini.write_text(ini.read_text(encoding="utf-8").replace(str(aux / "geometry-data"), str(external_geometry)), encoding="utf-8")
    ext_before = hashes(outside)
    assert prepare_scan_inputs(m) == sorted([str(external_geometry), str(outside / "resource.dat")])
    assert hashes(outside) == ext_before and hashes(a) == original_hashes
    b, m, p = copy_case("config-cycle")
    (p / "aux/geometry-data").write_text("[geometry]\nconfig = geometry-data\n", encoding="utf-8")
    saved = hashes(b)
    expect_error(lambda: prepare_scan_inputs(m), "Cyclic")
    assert hashes(b) == saved
    print("SCAN-01 closure: aux chain/shared leaf/config resource/cycle/missing/external readonly OK")


def main():
    retained = os.environ.get("G4USIM_SCAN_CONTRACT_ROOT")
    if retained:
        Path(retained).mkdir(parents=True, exist_ok=False)
    with (nullcontext(retained) if retained else tempfile.TemporaryDirectory(prefix="ar4-scan-contract-")) as temp:
        root = Path(temp)
        base = make_base(root)
        energy = next(p for p in scan.parameters(base) if p.key == "source.energy")
        reachable_closure_cases(root, base, energy)
        original = scan.create_scan(base, energy, ["10 MeV", "20 MeV"], "A", root)
        a = Path(original.scan_dir)
        b = root / "copy B"
        shutil.copytree(a, b)
        before = hashes(a)
        copied = scan.load_manifest(b)
        for point in copied.points:
            for attr in ("package_dir", "main_ini", "macro", "output_dir"):
                assert Path(getattr(point, attr)).is_relative_to(b)
        assert hashes(a) == before
        assert prepare_scan_inputs(copied) == []
        for point in copied.points:
            text = Path(point.main_ini).read_text(encoding="utf-8")
            assert str(a) not in text and str(b) in text
            assert (Path(point.package_dir) / "logs").is_relative_to(b)
            Path(point.output_dir, "only-B.txt").write_text("B", encoding="utf-8")
        assert hashes(a) == before, "A survives B preparation/writes byte-for-byte"
        stable = hashes(b)
        prepare_scan_inputs(copied)
        assert hashes(b) == stable, "preparation is idempotent"
        external = root / "external.ini"
        external.write_text("# explicit external dependency\n", encoding="utf-8")
        ini = Path(copied.points[0].main_ini)
        ini.write_text(ini.read_text(encoding="utf-8") + f"\n[external_test]\nfile = {external}\n", encoding="utf-8")
        assert prepare_scan_inputs(copied) == [str(external.resolve())]
        macro = Path(copied.points[0].macro)
        nested = macro.parent / "child.mac"
        nested.write_text("# nested input\n", encoding="utf-8")
        macro.write_text("/control/execute child.mac\n", encoding="utf-8")
        prepare_scan_inputs(copied)
        assert str(nested.resolve()) in macro.read_text(encoding="utf-8")
        missing = deepcopy(copied)
        missing.points[0].main_ini += ".missing"
        saved = hashes(b)
        try:
            prepare_scan_inputs(missing)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("missing copied input must not fall back to A")
        assert hashes(b) == saved
        escaped = deepcopy(copied)
        escaped.points[0].output_dir = original.points[0].output_dir
        expect_error(lambda: prepare_scan_inputs(escaped), "outside")
        assert hashes(a) == before

        # Match the authoritative persisted service, including replaced summaries.
        point = copied.points[0]
        summary = Path(point.output_dir) / "run_summary.txt"
        status = Path(point.package_dir) / "logs/run_status.json"
        summary.write_text("status = completed\nsimulation_executed = true\n"
            "program_exit_code = 0\nsummary_write_status = completed\nmacro_execution_status = completed\n"
            "planned_event_count = 2\nactual_completed_event_count = 2\nrun_count = 1\n"
            "run_0_id = 0\nrun_0_planned_events = 2\nrun_0_completed_events = 2\n", encoding="utf-8")
        single = deepcopy(copied)
        single.points = [point]
        assert scan.collect(single)[0].trust_level == "summary_only"
        stamp = summary.stat()
        normal = dict(state="success", exitCode=0, exitStatus="normal", resultVersion=1,
                      summaryFresh=True, summaryFingerprint=[stamp.st_mtime_ns, stamp.st_size])
        records = [normal, {**normal, "exitCode": 1}, {**normal, "exitStatus": "crashed"},
                   {**normal, "state": "stopped"}, {**normal, "state": "killed"},
                   {**normal, "summaryFresh": False}, {**normal, "exitCode": None}]
        for record in records:
            status.write_text(json.dumps(record), encoding="utf-8")
            expected = read_persisted_run_evidence(summary, status)
            actual = scan.collect(single)[0]
            assert (actual.state, actual.trust_level, actual.exit_code) == (
                expected.result.state, expected.trust_level, expected.exit_code)
        status.write_text(json.dumps(normal), encoding="utf-8")
        assert scan.collect(single)[0].state == "success"
        summary.write_text(summary.read_text(encoding="utf-8") + "replacement = true\n", encoding="utf-8")
        assert scan.collect(single)[0].state != "success"
        status.write_text("not-json", encoding="utf-8")
        assert scan.collect(single)[0].trust_level == "invalid_process_record"

        # Named fields target one stable identity, leaving inactive legacy data intact.
        named = deepcopy(base)
        named.source.gps_sources = [GPSDefinition(name="one"), GPSDefinition(name="two")]
        named_before = deepcopy(named)
        keys = {p.key: p for p in scan.parameters(named)}
        assert "source.energy" not in keys
        target = keys[f"source.named.{named.source.gps_sources[1].editor_id}.energy"]
        changed = scan.apply_value(named, target, "17 MeV")
        assert changed.source.gps_sources[1].energy == "17 MeV"
        assert changed.source.gps_sources[0] == named.source.gps_sources[0]
        assert changed.source.energy == named.source.energy and named == named_before
        generated = scan.create_scan(named, target, ["17 MeV", "19 MeV"], "named", root)
        for item, value in zip(generated.points, ("17", "19")):
            text = Path(item.main_ini).read_text(encoding="utf-8")
            assert f"energy = {value} MeV" in text.split("[source.two]", 1)[1]
        particle = keys[f"source.named.{named.source.gps_sources[0].editor_id}.particle"]
        assert scan.apply_value(named, particle, "gamma").source.gps_sources[0].particle == "gamma"
        reject_root = root / "must-not-exist"
        expect_error(lambda: scan.create_scan(named, energy, ["2 MeV"], "bad", reject_root), "active")
        expect_error(lambda: scan.create_scan(named, energy, [], "bad", reject_root), "no scan values")
        assert not reject_root.exists()
        named.source.gps_sources[1].energy_type = "histogram"
        expect_error(lambda: scan.apply_value(named, target, "2 MeV"), "active")
        named.source.phase_space_file = "inactive-test.csv"
        expect_error(lambda: scan.create_scan(named, particle, ["gamma"], "bad", reject_root), "active")
        reference = next(p for p in scan.parameters(base) if p.key == "physics.reference")
        named.physics.mode = "manual"
        expect_error(lambda: scan.create_scan(named, reference, ["FTFP_BERT"], "bad", reject_root), "active")
        assert not reject_root.exists()
    print("smoke_scan_contract: OK (controlled; no backend)")


if __name__ == "__main__":
    main()
