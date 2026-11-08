"""Finite B3/B4 evidence admission; verified bytes are not physics validation.

Only the formats emitted by the two scenario generators are interpreted here.
No Qt, legacy downgrade, inferred sparse zeros, or global evidence cache.
"""
from __future__ import annotations

import configparser
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui"))
from g4usim_gui.output.identity import strict_object
from g4usim_gui.output.provenance import evidence_operation, output_evidence


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value, label, *, positive=False):
    require(not isinstance(value, bool), f"invalid {label}")
    result = float(value)
    require(math.isfinite(result) and (result > 0 if positive else result >= 0), f"invalid {label}")
    return result


def integer(value, label):
    require(not isinstance(value, bool) and re.fullmatch(r"[0-9]+", str(value)) is not None, f"invalid {label}")
    return int(value)


def load_json(data):
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=strict_object,
                      parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"non-finite JSON: {token}")))


def rows(data, required):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    fields = reader.fieldnames or []
    require(len(fields) == len(set(fields)) and set(required) <= set(fields), "invalid CSV columns")
    result = list(reader)
    require(all(None not in row and all(v is not None for v in row.values()) for row in result), "malformed CSV row")
    return result


def ini(data):
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    try:
        parser.read_string(data.decode("utf-8-sig"))
    except configparser.Error as error:
        raise ValueError(f"invalid generated INI: {error}") from error
    require(not parser.defaults(), "INI defaults are outside generated scenario format")
    return parser


def dimension(value, unit="mm"):
    match = re.fullmatch(r"\s*([+\-\d.eE]+)\s*([A-Za-z]+)\s*", value)
    require(match is not None, f"explicit unit required: {value}")
    scales = {"mm": 1., "cm": 10., "m": 1000., "um": .001, "nm": 1e-6} if unit == "mm" else {unit: 1.}
    require(match[2] in scales, f"unsupported unit: {value}")
    result = float(match[1]) * scales[match[2]]
    require(math.isfinite(result), "non-finite dimension")
    return result


def vector(value):
    result = [dimension(item) for item in value.split(",")]
    require(len(result) == 3, "expected three generated dimensions")
    return result


def same(actual, expected, label, tolerance=1e-11):
    require(math.isfinite(float(expected)) and math.isclose(actual, float(expected), rel_tol=tolerance, abs_tol=1e-12),
            f"scenario/input mismatch: {label}")


def quantity(value, reason="", sample_count=None, uncertainty_status="not_estimated", *, model=False):
    if value is not None:
        require(math.isfinite(value), "non-finite derived quantity")
    return {"status": "unavailable" if value is None else ("zero" if value == 0 else "available"),
            "reason": reason, "sample_count": sample_count, "uncertainty_status": uncertainty_status,
            "basis": "model_prediction" if model else "sample_estimate"}


class AnalysisEvidence:
    """An operation-local snapshot, retaining exactly the consumed output bytes."""
    def __init__(self, directory):
        self.root = Path(directory).resolve()
        with evidence_operation():
            self.evidence = output_evidence(self.root)
            require(self.evidence.status == "verified", "current integrity metadata required; rerun or inspect raw files")
            self.document = self.evidence.document
            self.content = {}
            for path, record in zip(self.evidence.files, self.evidence.records):
                if path.name == "run_metadata.json":
                    continue
                require(path.name not in self.content, f"ambiguous artifact basename: {path.name}")
                data = path.read_bytes()
                require(hashlib.sha256(data).hexdigest() == record["sha256"] and len(data) == record["size_bytes"],
                        f"artifact changed during consumption: {path.name}")
                self.content[path.name] = data
            require(hashlib.sha256((self.root / "run_metadata.json").read_bytes()).hexdigest() == self.evidence.manifest_digest,
                    "metadata changed during consumption")
        self._admit()
        data = (self.root.parent / "scenario.json").read_bytes()
        self.meta = load_json(data)
        self.scenario_sha256 = hashlib.sha256(data).hexdigest()
        self.bound_inputs = []
        self._input_cache = {}

    def _admit(self):
        sections = {}; section = None
        for line in self.content["run_summary.txt"].decode("utf-8-sig").splitlines():
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                require(section not in sections, f"duplicate summary section {section}")
                sections[section] = {}
            elif section in ("Values", "Runs") and line.strip():
                require(" = " in line, "malformed summary fact")
                key, value = line.split(" = ", 1)
                require(key not in sections[section], f"duplicate summary fact {key}")
                sections[section][key] = value
        values = sections.get("Values", {})
        require(values == self.document.get("values"), "text/metadata values mismatch")
        expected = {"status": "completed", "program_exit_code": "0", "simulation_executed": "true",
                    "macro_execution_status": "completed", "summary_write_status": "completed",
                    "output_failure_status": "none", "run_count": "1", "output_provenance_schema": "g4usim_provenance_v1",
                    "run_summary_schema_version": "1", "output_csv_schema_version": "3",
                    "macro_failure_phase": "", "macro_failure_file": "", "macro_failure_command": "",
                    "macro_failure_line": "0", "macro_failure_code": "0", "macro_failure_code_available": "false"}
        for key, value in expected.items():
            require(values.get(key) == value, f"run admission: {key} must be {value}")
        runs = self.document["runs"]
        require(len(runs) == 1, "single run required")
        run = runs[0]
        require(run["run_id"] == 0, "single generated run must have ID 0")
        self.events = integer(run.get("planned_events"), "planned events")
        require(self.events > 0 and run["completed_events"] == self.events, "incomplete/zero run")
        require(sections.get("Runs") == {"run_0_id": "0", "run_0_planned_events": str(self.events),
                                        "run_0_completed_events": str(self.events)}, "text/metadata runs mismatch")
        for key in ("planned_event_count", "actual_completed_event_count"):
            require(values.get(key) == str(self.events), f"inconsistent {key}")
        provenance = self.document["provenance"]
        self.execution_id = provenance["execution_id"]
        require(values.get("execution_id") == self.execution_id, "execution mismatch")
        build = provenance["build"]
        for key, buildkey in (("build_git_commit", "git_commit"), ("source_fingerprint", "source_fingerprint"),
                              ("build_git_source_state", "git_source_state"), ("geant4_version", "geant4_version")):
            require(values.get(key) == build[buildkey] and values[key] != "unknown", f"missing/conflicting {key}")
        threads = integer(values.get("actual_threads"), "actual_threads")
        require(threads > 0, "actual_threads must be positive")
        self.workers = set(range(threads))
        self.values = values
        for record in self.evidence.records:
            if record["scope"] != "process":
                require(record["run_id"] == 0, "cross-run artifact")
            if record["scope"] == "thread":
                require(record["thread_id"] in self.workers, "artifact worker outside actual_threads")

    def csv(self, name, required, schema):
        path = self.evidence.require(name)
        require(self.evidence.artifact(path)["schema"] == schema, f"unsupported schema: {name}")
        return rows(self.content[name], required)

    def input(self, path, kind, role):
        """Bind current candidate bytes to historical reader observations, never invent a read."""
        path = Path(path).resolve()
        key = (str(path), kind, role)
        if key in self._input_cache:
            return self._input_cache[key]
        data = path.read_bytes(); digest = hashlib.sha256(data).hexdigest()
        candidates = [r for r in self.document["provenance"]["inputs"] if r["kind"] == kind and r["role"] == role]
        # Relocation is permitted by content and role, not by the old absolute path.
        require(candidates and all(r["status"] == "recorded" and r["sha256"] == digest and r["size_bytes"] == len(data)
                                   for r in candidates if Path(r["path"]).name == path.name), f"unbound/conflicting input: {path.name}")
        matches = [r for r in candidates if r["status"] == "recorded" and r["sha256"] == digest and r["size_bytes"] == len(data)]
        require(bool(matches), f"input bytes/role not observed: {path.name}")
        self.bound_inputs.append({"path": str(path), "kind": kind, "role": role, "sha256": digest,
                                  "size_bytes": len(data), "observed_sequences": [r["sequence"] for r in matches]})
        self._input_cache[key] = data
        return data

    def bind_scenario(self, detector=False):
        base = self.root.parent
        for key, filename in (("main_config", "main.ini"), ("materials_file", "materials.ini"),
                              ("geometry_config", "geometry.ini"), ("actual_macro_file", "run.mac")):
            require(Path(self.values.get(key, "")).name == filename, f"run selected a different/unreported {key}")
        main = ini(self.input(base / "main.ini", "main_ini", "configuration_parse"))
        require(main["geometry"]["template"] == "hierarchical", "only generated hierarchical scenarios supported")
        require(not any(s.startswith(("scoring.filter.", "biasing.", "parallel_world")) for s in main.sections()),
                "filters/biasing/parallel geometry outside generated analysis contract")
        def generated_path(value):
            path = Path(value)
            if path.is_absolute():
                return path
            # Generator may prefix paths relative to --run-from; finite suffix mapping.
            direct = base / path
            return direct if direct.is_file() else base / path.name
        material = ini(self.input(generated_path(main["materials"]["file"]), "material_ini", "material_parse"))
        geo = ini(self.input(generated_path(main["geometry"]["config"]), "geometry_ini", "geometry_parse"))
        macro = self.input(generated_path(main["run"]["macro"]), "macro", "recursive_preflight").decode("utf-8-sig")
        commands = [line.split("#", 1)[0].strip() for line in macro.splitlines()]
        require([line for line in commands if line] == ["/run/initialize", f"/run/beamOn {self.events}"],
                "macro outside finite generated scenario contract (source/geometry may have changed)")
        if "events" in self.meta:
            require(integer(self.meta["events"], "scenario events") == self.events, "scenario events mismatch")
        known = {s.strip() for s in material.get("nist", "materials").split(",")}
        known.update(s.removeprefix("material.") for s in material.sections() if s.startswith("material."))
        for section in geo.sections():
            if section.startswith("volume."):
                require(geo[section]["material"] in known, "geometry material absent from bound material input")
                require("rotation" not in geo[section], "rotated geometry outside generated scenario contract")
        sources = [main[s] for s in main.sections() if s == "source" or s.startswith("source.")]
        sources = [s for s in sources if "particle" in s]
        require(bool(sources), "missing generated source")
        self.spectrum_flux = {}
        raw_energy = self.meta["energy_MeV"]
        # The device generator emits JSON null for an unset mono energy. Keep
        # that explicit sentinel distinct from false/empty/other invalid values.
        if raw_energy is None:
            energy = None
        else:
            require(isinstance(raw_energy, (int, float)) and not isinstance(raw_energy, bool),
                    "scenario energy must be a number or null")
            energy = number(raw_energy, "scenario energy")
        particles = {s["particle"] for s in sources}
        require(len(sources) == len(particles), "duplicate generated source particle")
        require(particles == ({"proton", "e-"} if self.meta["particle"] == "mixed" else {self.meta["particle"]}), "source particle mismatch")
        for source in sources:
            if energy is not None and energy > 0:
                same(dimension(source["energy"], "MeV"), energy, "source energy")
                require("energy_type" not in source, "conflicting source energy mode")
            else:
                require(source.get("energy_type") == "histogram" and "energy" not in source,
                        "unset scenario energy requires a bound histogram source")
                spectrum = self.input(generated_path(source["spectrum_file"]), "spectrum", "source_spectrum_parse")
                text = spectrum.decode("utf-8-sig")
                flux_unit = "weight = integral flux F(E_low) - F(E_high) [cm-2 s-1]"
                require(text.splitlines()[0].startswith("# histogram from ") and flux_unit in text.splitlines()[0],
                        "absolute spectrum weight units outside generated contract")
                bins = rows("\n".join(line for line in text.splitlines() if not line.startswith("#")).encode(),
                            ("e_low_MeV", "e_high_MeV", "weight"))
                require(bool(bins), "empty source spectrum")
                previous = None
                for item in bins:
                    low = number(item["e_low_MeV"], "spectrum low")
                    high = number(item["e_high_MeV"], "spectrum high")
                    require(high > low and (previous is None or low == previous), "invalid spectrum intervals")
                    previous = high
                self.spectrum_flux[source["particle"]] = sum(number(item["weight"], "spectrum weight") for item in bins)
                require(self.spectrum_flux[source["particle"]] > 0, "zero spectrum flux")
            require(source.get("direction") == "0, 0, 1", "source direction outside generated contract")
            require(not any(k in source for k in ("preset", "file", "phase_space_file", "min_theta", "halfy")),
                    "source override outside generated contract")
        if detector:
            require(main["scoring"].get("event_edep") == "true", "event deposits disabled")
            self._bind_detector(geo, sources)
        else:
            self._bind_device(main, geo, sources, generated_path)
        self.geometry = geo

    def _bind_device(self, main, geo, sources, path_for):
        meta = self.meta
        area = number(meta["source_area_cm2"], "source area", positive=True)
        for source in sources:
            require(source.get("position_type") == "plane" and source.get("shape") == "square", "source area mode mismatch")
            same((2 * dimension(source["halfx"]) / 10) ** 2, area, "source area")
            require(vector(source["center"]) == [0, 0, -1], "source centre mismatch")
        sensitive = {s for s in geo.sections() if s.startswith("volume.") and geo[s].get("sensitive") == "true"}
        require(sensitive == {"volume.GateOxide", "volume.Active", "volume.Slice"}, "unbound sensitive geometry")
        layers = meta["layers"]; slices = meta["slices"]
        require([r["name"] for r in layers] == ["GateOxide", "Active"], "generated sensitive layers required")
        for layer in layers:
            sec = geo[f"volume.{layer['name']}"]
            require(sec["material"] == layer["material"] and sec["parent"] == "world" and sec["shape"] == "box"
                    and sec["sensitive"] == "true", "layer material/placement mismatch")
            size = vector(sec["size"]); pos = vector(sec["position"])
            same(size[2], number(layer["thickness_mm"], "layer thickness", positive=True), "layer thickness")
            same(pos[2] - size[2] / 2, layer["depth_mm"], "layer depth")
            same(size[0] * size[1] / 100, area, "layer/source area")
        substrate = geo["volume.Substrate"]; replica = geo["volume.Slice"]
        require(substrate["parent"] == "world" and substrate["material"] == replica["material"] == "G4_Si"
                and replica["parent"] == "Substrate" and replica["placement"] == "replica" and replica["shape"] == "box"
                and replica["replica_axis"] == "z" and replica["sensitive"] == "true", "slice material/placement mismatch")
        require(len(slices) == integer(replica["replica_count"], "slice count") > 0, "slice count mismatch")
        width = dimension(replica["replica_width"]); size = vector(replica["size"])
        parent_size = vector(substrate["size"]); start = vector(substrate["position"])[2] - parent_size[2] / 2
        same(width * len(slices), parent_size[2], "slice partition")
        same(size[2], width, "slice width")
        for axis in (0, 1):
            same(size[axis], parent_size[axis], "slice parent lateral size")
        same(size[0] * size[1] / 100, area, "slice/source area")
        for i, item in enumerate(slices):
            require(item["copy"] == i, "slice copy mismatch")
            same(item["depth_mm"], start + i * width, "slice depth")
            same(item["thickness_mm"], width, "slice thickness")
        tables = dict(main["scoring.displacement"])
        require(tables == meta["niel_tables"], "NIEL selection mismatch")
        for table in tables.values():
            self.input(path_for(table), "niel_table", "displacement_table_parse")
        require(main["scoring"]["dose"] == main["scoring"]["displacement"] == "true", "required scorers disabled")
        flux = meta["sampled_integral_flux_cm2_s"]
        require(set(flux) == {s["particle"] for s in sources}, "scenario flux particles mismatch")
        self.flux_bound = True
        for source in sources:
            particle = source["particle"]; supplied = flux[particle]
            if particle in self.spectrum_flux:
                require(supplied is not None, "spectrum flux missing in scenario")
                # Generator encodes every histogram weight and mixed intensity at .6g.
                same(self.spectrum_flux[particle], number(supplied, "sampled flux", positive=True), "sampled flux", 5e-6)
                if len(sources) > 1:
                    same(number(source["intensity"], "mixed source intensity", positive=True), supplied, "mixed source intensity", 5e-6)
            elif supplied is not None:
                number(supplied, "unbound mono source flux")
                self.flux_bound = False

    def _bind_detector(self, geo, sources):
        require(len(sources) == 1, "one detector source required")
        source = sources[0]; meta = self.meta
        if meta["kind"] == "gamma":
            crystals = {"NaI": "G4_SODIUM_IODIDE", "CsI": "G4_CESIUM_IODIDE", "BGO": "G4_BGO", "HPGe": "G4_Ge",
                        "plastic": "G4_PLASTIC_SC_VINYLTOLUENE", "LaBr3": "LaBr3", "CZT": "CZT"}
            require(crystals.get(meta["crystal"]) == meta["material"], "crystal material annotation mismatch")
            sec = geo["volume.Crystal"]
            require(sec["material"] == meta["material"] and sec["shape"] == "tubs" and sec["sensitive"] == "true", "crystal mismatch")
            params = sec["parameters"].split(",")
            require(len(params) == 5, "invalid crystal parameters")
            same(dimension(params[0]), 0, "inner radius")
            same(dimension(params[1]), number(meta["radius_mm"], "radius", positive=True), "radius", 5e-6)
            same(dimension(params[2]) * 2, number(meta["length_mm"], "length", positive=True), "length", 5e-6)
            same(dimension(params[3], "deg"), 0, "start angle")
            same(dimension(params[4], "deg"), 360, "full crystal")
            require(source.get("position_type") == "point" and source.get("angular") == "isotropic", "cone mode mismatch")
            require(vector(source["position"]) == [0, 0, 0], "point source position mismatch")
            housing = number(meta["housing_mm"], "housing"); distance = number(meta["distance_mm"], "distance", positive=True)
            z = distance + (meta["length_mm"] + 2 * housing) / 2
            require(sec["parent"] == ("Housing" if housing else "world"), "crystal parent mismatch")
            same(vector(sec["position"])[2], 0 if housing else z, "crystal position", 5e-6)
            if housing:
                h = geo["volume.Housing"]
                require(h["parent"] == "world" and h["shape"] == "tubs" and h["material"] == "G4_Al", "housing mismatch")
                hp = h["parameters"].split(",")
                require(len(hp) == 5, "housing parameters")
                same(dimension(hp[1]), meta["radius_mm"] + housing, "housing radius", 5e-6)
                same(2 * dimension(hp[2]), meta["length_mm"] + 2 * housing, "housing length", 5e-6)
                same(vector(h["position"])[2], z, "housing position", 5e-6)
            sensitive = {s for s in geo.sections() if s.startswith("volume.") and geo[s].get("sensitive") == "true"}
            require(sensitive == {"volume.Crystal"}, "unbound sensitive geometry")
            theta = number(meta["cone_half_angle_deg"], "cone angle", positive=True)
            require(theta <= 90, "unsupported cone")
            same(dimension(source["max_theta"], "deg"), theta, "cone angle", 5e-6)
            same((1 - math.cos(math.radians(theta))) / 2, meta["cone_fraction_of_4pi"], "cone fraction")
        else:
            require(meta["kind"] == "silicon", "unknown detector kind")
            sec = geo["volume.Pad"]
            require(sec["material"] == meta["material"] == "G4_Si" and sec["shape"] == "box"
                    and sec["sensitive"] == "true", "silicon pad mismatch")
            size = vector(sec["size"])
            same(size[2], number(meta["thickness_mm"], "pad thickness", positive=True), "pad thickness", 5e-6)
            same(size[0], meta["size_mm"], "pad size", 5e-6)
            same(size[1], meta["size_mm"], "pad size", 5e-6)
            require(sec["parent"] == "world" and source.get("position_type") == "plane" and source.get("shape") == "square",
                    "pad/source placement mismatch")
            same(dimension(source["halfx"]), meta["size_mm"] / 4, "pad source area", 5e-6)
            require(vector(source["center"]) == [0, 0, -1], "pad source centre mismatch")
            same(vector(sec["position"])[2], meta["thickness_mm"] / 2, "pad position", 5e-6)
            sensitive = {s for s in geo.sections() if s.startswith("volume.") and geo[s].get("sensitive") == "true"}
            require(sensitive == {"volume.Pad"}, "unbound sensitive geometry")

    def report_header(self):
        return {"analysis_schema_version": 2, "analysis_status": "completed", "run_status": "completed",
                "provenance": "verified", "evidence_level": "verified_output_completion_summary",
                "process_exit_observed_independently": False, "execution_id": self.execution_id,
                "build": self.document["provenance"]["build"], "events": self.events, "scenario": self.meta,
                "input_binding": self.bound_inputs, "scenario_evidence": {"sha256": self.scenario_sha256,
                "backend_read": False, "meaning": "analysis_metadata_checked_against_observed_input_bytes"}}


def publish(output, files):
    """Stage every result before replacing any; JSON success marker is published last.

    Roll back on ordinary publication errors. A filesystem/process crash cannot
    provide multi-file atomicity; each individual replacement remains atomic.
    """
    staged = {}; previous = {}; replaced = []
    try:
        for name, data in files.items():
            target = output / name
            previous[name] = target.read_bytes() if target.exists() else None
            with tempfile.NamedTemporaryFile(dir=output, prefix=f".{name}.", delete=False) as handle:
                staged[name] = Path(handle.name); handle.write(data)
        for name in sorted(files, key=lambda n: n.endswith(".json")):
            os.replace(staged[name], output / name); replaced.append(name)
    except OSError:
        for name in reversed(replaced):
            if previous[name] is None:
                (output / name).unlink(missing_ok=True)
            else:
                staged[name].write_bytes(previous[name]); os.replace(staged[name], output / name)
        raise
    finally:
        for path in staged.values():
            path.unlink(missing_ok=True)


def json_bytes(report):
    return (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")
