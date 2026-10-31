"""K1 orchestration over F4 producers, F5 transactions and the existing runner.

Every action is asynchronous. File work receives a private snapshot; only the
owner thread accesses EditSession, QProcess and G4USimRunner. Records describe
separate evidence levels, never a general claim of physical correctness.
"""
from __future__ import annotations

import copy
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import statistics
import tempfile
from uuid import uuid4

from PySide6.QtCore import QFileSystemWatcher, QLocale, QObject, QProcess, QThread, QTimer, Signal

from g4usim_gui.core.config_migration import load_json_strict
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, clone_snapshot, snapshot_fingerprint
from g4usim_gui.core.evidence_job import EvidenceJob
from g4usim_gui.core.experiment_identity import canonical_digest, capture_identity, file_identity, safe_environment
from g4usim_gui.core.project_diagnostics import validate_project_report
from g4usim_gui.core.run_result import RunResult
from g4usim_gui.output.provenance import output_evidence
from g4usim_gui.output.run_summary_parser import parse_run_summary
from g4usim_gui.validators.config_validator import validate_config_builder
from g4usim_gui.writers.package_writer import create_run_package


class WorkflowBusyError(RuntimeError):
    pass


class WorkflowStaleError(RuntimeError):
    pass


class WorkflowEvidenceError(RuntimeError):
    def __init__(self, reason, facts=None, *, unobserved=False):
        super().__init__(reason)
        self.facts = facts or {}
        self.unobserved = unobserved


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json_record(record):
    return {key: copy.deepcopy(value) for key, value in record.items()
            if key != "report" and not key.startswith("_")}


def _portable_record(record):
    """Explicit export projection, separate from local operation/recovery logs."""
    keys = ("schema", "record_id", "run_id", "action", "level", "status", "revision",
            "session_id", "created_at", "finished_at", "stale", "execution_id", "metadata_sha256",
            "result", "exit_code", "comparisons", "reference_records", "evaluated_run_id",
            "evaluation_scope", "geometry_check", "initialization_mesh_identity", "build",
            "input_coverage", "input_exclusions", "requested_run_name", "observed_run_name")
    result = {key: copy.deepcopy(record[key]) for key in keys if key in record}
    result["history_trust"] = "historical_requires_local_revalidation"
    result["reason"] = record.get("reason", "").split(":", 1)[0] if re.fullmatch(
        r"experiment\.[a-z_]+(?::.*)?", record.get("reason", ""), re.DOTALL) else "experiment.historical_diagnostic"
    if "identity" in record:
        result["identity"] = {key: copy.deepcopy(value) for key, value in record["identity"].items()
                              if key not in {"snapshot_fingerprint", "declared_source_receipts"}}
    if "actual_inputs" in record:
        result["actual_inputs"] = [{key: copy.deepcopy(row[key]) for key in
            ("sequence", "kind", "role", "capture_method", "status", "sha256", "size_bytes") if key in row}
            for row in record["actual_inputs"]]
        result["input_locations"] = "historical_locations_omitted_not_rebound"
    if "random_settings" in record:
        settings = copy.deepcopy(record["random_settings"])
        for key, value in list(settings.items()):
            if (isinstance(value, str) and key.endswith(("_file", "_path"))
                    and value not in {"", "unknown", "not_applicable", "not_executed", "unset", "omitted_local_path"}):
                settings[key] = "omitted_local_path"
                settings[key + "_path_text_sha256"] = canonical_digest(value)
        result["random_settings"] = settings
        result["random_origin_locations"] = "omitted_paths_hashed_as_text_not_file_bytes"
    return result


def _persist(record):
    directory = Path(record["record_dir"])
    directory.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(_json_record(record), ensure_ascii=False, sort_keys=True,
                      allow_nan=False, indent=2) + "\n").encode("utf-8")
    descriptor, name = tempfile.mkstemp(prefix=".record-", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, directory / "record.json")
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _arguments(project):
    args = []
    for option, value in (("--config", project.configPath), ("--macro", project.macroPath),
                          ("--output", project.outputDir), ("--threads", project.threads),
                          ("--seed", project.seed), ("--run-name", project.runName)):
        if value != "" and value is not None:
            args.extend((option, str(value)))
    return [project.executable, *args]


def _observed_path(path, cwd):
    value = Path(path)
    return str((value if value.is_absolute() else Path(cwd) / value).resolve())


def _original_inspection_identity(snapshot, revision):
    """Observe declared original inputs without interpreting macro/resource syntax.

    Configure/preflight is a diagnostic operation, not a distributable closure
    or initialization proof. Unknown recursive inputs explicitly stay unknown.
    """
    project = snapshot.project
    cwd = str(Path(project.workspaceRoot or Path.cwd()).resolve())
    resources, receipts = [], {}
    for role, name in (("main", project.configPath), ("macro", project.macroPath)):
        if name:
            path = _observed_path(name, cwd)
            observed = file_identity(path)
            receipts[path] = observed
            resources.append({"path": "declared/" + role, "role": role,
                              "sha256": observed["sha256"], "source_sha256": observed["sha256"],
                              "size_bytes": observed["size_bytes"], "captured_text": False})
    identity = {"schema": "g4usim_experiment_identity_v1", "identity_scope": "original_declared_inspection",
                "coverage": "original_declared_inputs_observed", "recursive_closure": "unobserved",
                "input_observation": "declared_files_pre_post_sha_not_backend_read_receipts",
                "revision": revision, "snapshot_fingerprint": snapshot_fingerprint(snapshot),
                "configuration_fingerprint": snapshot_fingerprint(snapshot),
                "resources": resources, "declared_source_receipts": receipts,
                "resource_fingerprint": canonical_digest(resources),
                "backend": {"status": "recorded", **file_identity(project.executable)},
                "environment": {"status": "unobserved", "reason": "configure_preflight_only",
                                "working_directory_sha256": canonical_digest(cwd)}}
    identity["fingerprint"] = canonical_digest({key: identity[key] for key in
        ("identity_scope", "configuration_fingerprint", "resource_fingerprint")})
    identity["execution_fingerprint"] = canonical_digest({key: identity[key] for key in
        ("fingerprint", "backend", "environment")})
    return identity


def _verify_request_binding(record, facts):
    """A label is user data. Bind the request through its exclusive paths."""
    cwd = record["execution_bundle"]["path"]
    command = record["command"]
    expected = {"actual_output_dir": record["output_dir"]}
    for option, key in (("--config", "main_config"), ("--macro", "actual_macro_file")):
        if option in command:
            expected[key] = command[command.index(option) + 1]
    for key, value in expected.items():
        if not facts.get(key) or _observed_path(facts[key], cwd) != _observed_path(value, cwd):
            raise ValueError("experiment.request_path_mismatch: " + key)
    requested = record.get("requested_run_name", "")
    if requested and (facts.get("run_name") != requested or facts.get("effective_run_name") != requested):
        raise ValueError("experiment.requested_run_name_mismatch")


def _builder_kwargs(project):
    return dict(paths=project.pathSettings, run=project.runSettings,
                geometry=project.geometrySettings, source=project.sourceSettings,
                physics=project.physicsSettings, scoring=project.scoringSettings,
                material_document=project.materialEditor, geometry_document=project.geometryEditor,
                source_model=project.sourceEditor, physics_model=project.physicsEditor,
                scoring_model=project.scoringEditor)


def _draft_value(project, binding):
    domain, name = binding.split(".", 1)
    if domain == "project":
        aliases = dict(project_name="projectName", run_input_mode="runInputMode", workspace_root="workspaceRoot",
                       config_path="configPath", macro_path="macroPath", output_dir="outputDir", runs_root="runsRoot", run_name="runName")
        return getattr(project, aliases.get(name, name))
    if domain != "config":
        raise KeyError(binding)
    for prefix, owner, aliases in (
        ("source_editor_", project.sourceEditor, {"shape": "source_shape", "position_type": "position_mode", "preview_rays": "preview_ray_count", "preview_seed": "random_seed_preview"}),
        ("physics_editor_", project.physicsEditor, {"reference": "reference_list", "biasing": "enable_biasing_physics"}),
        ("scoring_editor_", project.scoringEditor, {"raw_hist": "raw_histogram", "weighted_hist": "weighted_histogram", "trajectories": "trajectory_events", "bins": "hist_bins", "min": "hist_min", "max": "hist_max", "auto_create": "auto_create_default_scorers"}),
        ("simple_", project.geometryEditor.simple_box, {}),
        ("layered_", project.geometryEditor.layered_device, {}),
        ("source_", project.sourceSettings, {})):
        if name.startswith(prefix):
            field = name[len(prefix):]
            return getattr(owner, aliases.get(field, field))
    aliases = {"geometry_source_copy": (project.geometryEditor, "source_copy_mode"),
               "geometry_template": (project.geometrySettings, "template"),
               "physics_reference": (project.physicsSettings, "reference"),
               "default_cut": (project.physicsSettings, "default_cut"),
               "enable_biasing": (project.physicsSettings, "enable_biasing")}
    if name in aliases:
        owner, field = aliases[name]
        return getattr(owner, field)
    if name.startswith("scoring_"):
        return getattr(project.scoringSettings, name[len("scoring_"):])
    for owner in (project.runSettings, project.pathSettings, project.scoringSettings):
        if hasattr(owner, name):
            value = getattr(owner, name)
            return "" if value is None else value
    raise KeyError(binding)


def _draft_equivalent(raw, accepted, binding):
    if type(accepted) is bool:
        return raw is accepted if type(raw) is bool else str(raw).strip().lower() in (
            {"true", "yes", "on", "1"} if accepted else {"false", "no", "off", "0"})
    if type(accepted) is int:
        value = str(raw).strip()
        if binding == "config.scoring_editor_trajectories.raw" and accepted == 0:
            from g4usim_gui.core.i18n import ZH_CN
            if value in {"off", ZH_CN["off"]}:
                return True
        if re.fullmatch(r"[+-]?[0-9]+", value) is not None:
            return int(value) == accepted
        # QSpinBox renders/accepts the current QLocale's digits (e.g. zh_HK
        # Suzhou numerals). The F5 raw text is not an ASCII configuration token.
        parsed, accepted_by_locale = QLocale().toLongLong(value)
        return accepted_by_locale and parsed == accepted
    if str(raw).strip() == str(accepted).strip():
        return True
    from g4usim_gui.core.config_schema import quantity
    kind = "energy" if any(key in binding for key in ("energy", "hist_min", "hist_max", "scoring_editor_min", "scoring_editor_max")) else (
        "length" if any(key in binding for key in ("cut", "radius", "halfx", "halfy", "gap", "thickness", "dx1", "dx2", "dy1", "dy2", "dz")) else
        "angle" if any(key in binding for key in ("theta", "phi", "angle")) else None)
    if kind:
        left, right = quantity(str(raw), kind), quantity(str(accepted), kind)
        return left is not None and right is not None and left == right
    # Whitespace around vector delimiters is a display-only difference; do not
    # accept a different value, unknown unit, identifier or a changed unit scale.
    if "," in str(accepted):
        return re.sub(r"\s+", "", str(raw)) == re.sub(r"\s+", "", str(accepted))
    return False


def _raw_diagnostics(snapshot, report):
    project = snapshot.project
    for binding, value in snapshot.state["drafts"].items():
        if binding.startswith("detail.") or binding.endswith(".raw"):
            continue
        try:
            accepted = _draft_value(project, binding)
            matched = _draft_equivalent(value, accepted, binding)
        except (AttributeError, KeyError, ValueError, TypeError):
            matched = False
        if not matched:
            report.add("experiment.raw_draft.unaccepted", "error", binding, origin="experiment",
                       unavailable_reason="unaccepted_raw_draft", identity_parameters={"binding": binding})
    for name, raw_rows in snapshot.state["tables"].items():
        if name == "geometry_table":
            expected = [[v.enabled, v.name, v.parent, v.shape, v.material, v.position,
                v.parameters if v.shape.strip().lower() != "box" and v.parameters else v.size,
                v.rotation, v.sensitive, v.bias, v.region,
                *(v.shape_properties.get(key, "") for key in ("dx1", "dx2", "dy1", "dy2", "dz"))]
                for v in project.geometryEditor.volumes]
        elif name == "boolean_table":
            expected = [[v.enabled, v.target_volume, v.index, v.operation, v.tool_shape, v.tool_size,
                         v.tool_parameters, v.position, v.rotation] for v in project.geometryEditor.boolean_ops]
        else:
            expected = None
        if expected is None or len(expected) != len(raw_rows) or any(len(raw) != len(typed) or
            any(not _draft_equivalent(value, accepted, name + "." + str(column)) for column, (value, accepted)
                in enumerate(zip(raw, typed))) for raw, typed in zip(raw_rows, expected)):
            report.add("experiment.raw_table.unaccepted", "error", name, origin="experiment",
                       unavailable_reason="unaccepted_raw_draft")


def _field_report(snapshot):
    """Use producer diagnostics; validate captured raw drafts as well as models."""
    project = snapshot.project
    if project.runInputMode == "generated":
        report = validate_config_builder(**_builder_kwargs(project))
    else:
        candidate = copy.deepcopy(project)
        base = Path(candidate.workspaceRoot or Path.cwd())
        for field in ("configPath", "macroPath"):
            value = getattr(candidate, field)
            if value and not Path(value).is_absolute():
                setattr(candidate, field, str((base / value).resolve()))
        candidate.outputDir = candidate.outputDir or str(Path(candidate.workspaceRoot or Path.cwd()) / "output")
        report = validate_project_report(candidate)
    from g4usim_gui.core.config_schema import check_value
    for kind, source in snapshot.state["sources"].items():
        document = project.materialEditor if kind == "materials" else project.geometryEditor
        if document is None or not document.source_path:
            continue
        selected = project.pathSettings.materials_config if kind == "materials" else project.geometrySettings.config_path
        base = Path(project.workspaceRoot or project.pathSettings.workspace_root or Path.cwd())
        selected_path = Path(selected)
        selected_path = selected_path if selected_path.is_absolute() else base / selected_path
        try:
            same = (source["read_success"] and selected_path.resolve() == Path(source["path"]).resolve()
                    and selected_path.read_text(encoding="utf-8", errors="replace") == source["text"])
        except OSError:
            same = False
        if not same:
            report.add("experiment.captured_source.changed", "error", kind, origin="experiment",
                       editor="setup", field=kind + "_config", unavailable_reason="source_changed")
    drafts = snapshot.state["drafts"]
    for binding in ("config.seed", "project.seed"):
        if binding in drafts and str(drafts[binding]).strip():
            problem = check_value("run", "seed", str(drafts[binding]).strip())
            if problem:
                report.add("experiment.raw_seed.invalid", "error", problem,
                           origin="experiment", editor="run", field="seed",
                           identity_parameters={"binding": binding, "value": drafts[binding]})
    # F5 raw detail and spin drafts can retain invalid input while typed models
    # retain their last accepted values. Refuse that discrepancy, never erase it.
    for binding, value in drafts.items():
        if binding.startswith("detail."):
            parts = binding.split(".")
            try:
                rows = project.materialEditor.rows if parts[1] == "material" else project.geometryEditor.layered_device.layers
                accepted = str(getattr(rows[int(parts[2])], parts[3]))
            except (AttributeError, IndexError, TypeError, ValueError):
                accepted = None
            if accepted is None or not _draft_equivalent(value, accepted, binding):
                report.add("experiment.raw_detail.unaccepted", "error", binding,
                           origin="experiment", unavailable_reason="unaccepted_raw_draft")
        elif binding.endswith(".raw"):
            accepted = drafts.get(binding[:-4])
            if accepted is not None and not _draft_equivalent(value, accepted, binding):
                report.add("experiment.raw_spin.unaccepted", "error", binding,
                           origin="experiment", unavailable_reason="unaccepted_raw_draft")
    report.snapshot_id = snapshot_fingerprint(snapshot)
    _raw_diagnostics(snapshot, report)
    return report


class ExperimentWorkflow(QObject):
    changed = Signal()
    completed = Signal(object)
    recordChanged = Signal(object)
    stateChanged = Signal(object)
    closed = Signal()

    def __init__(self, session, runner, *, inspect_process=None, parent=None,
                 records_root=None, package_factory=None, apply_snapshot=None,
                 environment_probe=None):
        super().__init__(parent)
        self.session = session
        self.runner = runner
        self._inspect = inspect_process if inspect_process is not None else QProcess(self)
        self._factory = package_factory or create_run_package
        self._projection = apply_snapshot
        self._probe = environment_probe
        initial = session.current().project
        self.records_root = Path(records_root or (Path(initial.runsRoot or initial.pathSettings.runs_root
            or Path(initial.workspaceRoot or Path.cwd()) / "runs") / "experiment-records")).expanduser().absolute()
        self._session_id = uuid4().hex
        self._epoch = 0
        self._records = []
        self._active = None
        self._job = EvidenceJob(self)
        self._history_job = EvidenceJob(self)
        self._refresh_job = EvidenceJob(self)
        self._freshness = "as_observed"
        self._notifying = False
        self._closing = False
        self._closed = False
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(lambda path: self.refresh())
        self._watcher.directoryChanged.connect(lambda path: self.refresh())
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(5000)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start()
        self.run_project = None
        self._inspect.finished.connect(self._inspect_finished)
        self._inspect.errorOccurred.connect(self._inspect_error)
        self.runner.finished.connect(self._run_finished)
        self.runner.errorOccurred.connect(self._run_error)
        root = self.records_root
        def read_history():
            result = []
            if root.is_dir():
                for path in sorted(root.glob("*/record.json")):
                    try:
                        record = load_json_strict(path.read_bytes())
                        if record.get("schema") == "g4usim_experiment_record_v1":
                            result.append(record)
                    except (OSError, ValueError, AttributeError):
                        continue
            return result
        self._history_job.submit(read_history, self._history_loaded)

    def _owner(self):
        if QThread.currentThread() != self.thread():
            raise RuntimeError("ExperimentWorkflow must be called on its Qt owner thread")

    @property
    def busy(self):
        return (self._active is not None or self.runner.is_running() or self._inspect.state() != QProcess.NotRunning
                or self._closing and not self._closed)

    def records(self):
        self._owner()
        revision = self.session.revision
        for record in self._records:
            if record.get("session_id") != self._session_id or record.get("revision") != revision:
                record["stale"] = True
                record.setdefault("stale_reason", "revision_or_session_changed")
        return copy.deepcopy(self._records)

    history = records

    def state(self):
        self.refresh()
        return self._state()

    def _state(self):
        records = self.records()
        latest = records[-1] if records else {}
        levels = []
        for level in ("fields", "initialization", "execution", "physics"):
            candidates = [r for r in records if r.get("level") == level]
            record = candidates[-1] if candidates else {}
            levels.append({"level": level, "status": "stale" if record.get("stale") else
                           "pending" if record.get("status") == "passed" and self._freshness == "checking" else
                           record.get("status", "unobserved"), "detail": record.get("reason", "")})
        return {"revision": self.session.revision, "qualification": self._freshness,
                "environment_observation": "as_observed_dataset_bytes_unknown",
                "fingerprint": latest.get("identity", {}).get("fingerprint", "unknown"),
                "run_id": latest.get("run_id"), "status": "pending" if self.busy or self._freshness == "checking" else
                ("stale" if latest.get("stale") else latest.get("status", "unobserved")),
                "levels": levels, "history": records}

    def _notify(self, record=None):
        previous, self._notifying = self._notifying, True
        try:
            if record is not None:
                self.recordChanged.emit(copy.deepcopy(record))
            self.changed.emit()
            self.stateChanged.emit(self._state())
        finally:
            self._notifying = previous

    def refresh(self):
        """Nonblocking current-content recheck, also used by public state reads."""
        self._owner()
        if self._closing or self._notifying or self._refresh_job.pending or self._active is not None or not any(
                record.get("identity") and not record.get("stale") for record in self._records):
            return
        snapshot = self.session.current()
        revision, epoch = self.session.revision, self._epoch
        candidates = [copy.deepcopy(record) for record in self._records if record.get("identity") and not record.get("stale")]
        self._freshness = "checking"
        def verify():
            _field_report(snapshot)
            observed = {}
            retired = []
            for record in candidates:
                previous = record["identity"]
                scope = previous.get("identity_scope", "workflow")
                if scope not in observed:
                    try:
                        observed[scope] = (_original_inspection_identity(snapshot, revision)
                            if scope == "original_declared_inspection" else capture_identity(snapshot, revision))
                    except (ValueError, OSError) as error:
                        observed[scope] = error
                current = observed[scope]
                if isinstance(current, Exception):
                    retired.append(record["record_id"])
                    continue
                if (current["fingerprint"] != previous["fingerprint"] or current["backend"] != previous["backend"]
                        or current["resources"] != previous["resources"]):
                    retired.append(record["record_id"])
            return retired
        def checked(retired, error):
            if revision != self.session.revision or epoch != self._epoch:
                self._freshness = "historical"
                return
            retired = set(retired or ())
            for record in self._records:
                if error is not None or record.get("record_id") in retired:
                    record.update(stale=True, stale_reason="content_changed_or_unavailable")
            self._freshness = "as_observed"
            self._notify()
        paths = [snapshot.project.executable, snapshot.project.configPath, snapshot.project.macroPath,
                 snapshot.project.pathSettings.materials_config, snapshot.project.geometrySettings.config_path]
        for source in snapshot.state["sources"].values():
            paths.append(source["path"])
        for record in candidates:
            paths.extend(record.get("expected_inputs", {}).keys())
        watched = set(self._watcher.files())
        new_paths = [str(Path(path).resolve()) for path in paths if path and Path(path).is_file() and str(Path(path).resolve()) not in watched]
        if new_paths:
            self._watcher.addPaths(new_paths)
        directories = set(self._watcher.directories())
        new_directories = sorted({str(Path(path).resolve().parent) for path in paths if path and Path(path).is_file()} - directories)
        if new_directories:
            self._watcher.addPaths(new_directories)
        self._refresh_job.submit(verify, checked)

    def _history_loaded(self, records, error):
        if error is not None:
            return
        existing = {r["record_id"] for r in self._records}
        for record in records:
            if record.get("record_id") not in existing:
                record.update(stale=True, stale_reason="loaded_history_requires_revalidation")
                self._records.insert(0, record)
        self._records.sort(key=lambda record: record.get("created_at", ""))
        self._notify()

    def invalidate(self, reason="inputs_changed"):
        self._owner()
        self._epoch += 1
        for record in self._records:
            record.update(stale=True, stale_reason=reason)
        # Deliberately no expensive hashes, IO or recursive changed emission.

    def _begin(self, action, level, expected_revision=None):
        self._owner()
        if self._closing:
            raise WorkflowBusyError("experiment.closed")
        if self.busy:
            raise WorkflowBusyError("experiment.busy")
        revision = self.session.revision
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision != revision):
            raise WorkflowStaleError("experiment.revision_changed")
        snapshot = self.session.current()
        identifier = uuid4().hex
        record = {"schema": "g4usim_experiment_record_v1", "record_id": identifier,
                  "run_id": identifier, "action": action, "level": level, "status": "pending",
                  "reason": "experiment.preparing", "revision": revision,
                  "session_id": self._session_id, "created_at": _now(), "stale": False,
                  "record_dir": str(self.records_root / identifier)}
        self._records.append(record)
        self._active = {"record": record, "snapshot": snapshot, "revision": revision,
                        "epoch": self._epoch, "cancelled": False, "phase": "preparing"}
        self._notify(record)
        return record

    def _current(self):
        active = self._active
        return active is not None and not active["cancelled"] and active["epoch"] == self._epoch and active["revision"] == self.session.revision

    def _work(self, work, done):
        context = self._active
        def delivered(result, error):
            if self._active is not context:
                return
            if not self._current():
                return self._finish("cancelled" if context["cancelled"] else "stale", "experiment.inputs_changed")
            if error is not None:
                if isinstance(error, WorkflowEvidenceError):
                    context["record"].update(error.facts)
                status = "stale" if isinstance(error, WorkflowStaleError) else (
                    "unobserved" if isinstance(error, WorkflowEvidenceError) and error.unobserved else "failed")
                return self._finish(status, str(error))
            try:
                done(result)
            except Exception as exc:
                self._finish("failed", str(exc))
        self._job.submit(work, delivered)

    def _finish(self, status, reason, **facts):
        context = self._active
        if context is None or context.get("finishing"):
            return
        context["finishing"] = True
        record = context["record"]
        record.update(facts)
        if context["cancelled"]:
            status = "cancelled"
        elif not self._current():
            status = "stale"
        record.update(status=status, reason=reason, finished_at=_now())
        if status == "stale":
            record.update(stale=True, stale_reason=reason)
        persisted = _json_record(record)
        def published(result, error):
            if self._active is not context:
                return
            if error is not None:
                record.update(status="failed", reason="experiment.record_persistence_failed: " + str(error))
            elif context["cancelled"]:
                record["status"] = "cancelled"
            elif context["epoch"] != self._epoch or context["revision"] != self.session.revision:
                record.update(status="stale", stale=True, stale_reason="inputs_changed_during_publication")
            # A cancellation/edit arriving while the first terminal write was
            # in flight must be persisted too, before any completed receipt.
            if error is None and _json_record(record) != persisted:
                persisted.clear()
                persisted.update(_json_record(record))
                self._job.submit(lambda: _persist(copy.deepcopy(persisted)), published)
                return
            self._active = None
            self._notify(record)
            self.completed.emit(copy.deepcopy(record))
        self._job.submit(lambda: _persist(persisted), published)

    def _environment(self, snapshot, *, cwd=None):
        if self._probe is None:
            from g4usim_gui.core.environment_discovery import probe_environment
            probe = probe_environment
        else:
            probe = self._probe
        import inspect
        supports_cwd = "cwd" in inspect.signature(probe).parameters
        facts = probe(snapshot.project.executable or snapshot.project.pathSettings.executable,
                      **({"cwd": cwd} if supports_cwd and cwd is not None else {}))
        if not isinstance(facts, dict) or facts.get("status") != "ready":
            raise ValueError("experiment.environment_not_ready")
        report = (facts.get("data", {}).get("report") or {})
        if not supports_cwd and any(row.get("path") and not Path(row["path"]).is_absolute() for row in report.get("datasets", [])):
            raise ValueError("experiment.relative_dataset_probe_cwd_unknown")
        return facts, safe_environment(facts, cwd=cwd)

    def _prepare(self, snapshot, record, action, prepared=None):
        snapshot = clone_snapshot(snapshot)
        report = _field_report(snapshot)
        result = {"report": report, "diagnostics": report.to_dict(), "can_run": report.can_run}
        if not report.can_run:
            return result
        if action == "inspect" and snapshot.project.runInputMode == "external":
            project = copy.deepcopy(snapshot.project)
            project.workspaceRoot = project.workspaceRoot or str(Path.cwd())
            project.executable = str(Path(project.executable or project.pathSettings.executable).expanduser().resolve())
            identity = _original_inspection_identity(snapshot, record["revision"])
            result.update(identity=identity, coverage=identity["coverage"],
                recursive_closure="unobserved", qualifies="configure_preflight_only",
                original_input_inspection=True, requested_run_name=project.runName,
                expected_inputs=identity["declared_source_receipts"],
                command=_arguments(project), _project=project)
            _persist({**record, **{key: value for key, value in result.items() if not key.startswith("_")}})
            return result
        environment = {"status": "not_probed", "reason": "field_validation_only"}
        identity = capture_identity(snapshot, record["revision"], environment=environment)
        result["identity"] = identity
        result["coverage"] = identity["coverage"]
        if action == "fields":
            return result
        project = copy.deepcopy(snapshot.project)
        root = Path(record["record_dir"])
        root.mkdir(parents=True, exist_ok=True)
        if project.runInputMode == "generated":
            paths = copy.deepcopy(project.pathSettings)
            paths.runs_root = str(root)
            # package_factory is only a writer, never an owner of the live model.
            package, text = self._factory(project=project, **dict(_builder_kwargs(project), paths=paths))
            package = asdict(package)
            if prepared is not None:
                prior = asdict(prepared) if not isinstance(prepared, dict) else prepared
                # A supplied package cannot authorize arbitrary different inputs.
                for key in ("materials_ini_path", "geometry_ini_path", "run_macro_path"):
                    if file_identity(prior[key]) != file_identity(package[key]):
                        raise ValueError("experiment.prepared_package_mismatch: " + key)
                prior_main = Path(prior["main_ini_path"]).read_text(encoding="utf-8")
                for key in sorted(package, key=lambda key: len(str(prior.get(key, ""))), reverse=True):
                    old = str(prior.get(key, ""))
                    if old:
                        prior_main = prior_main.replace(old, str(package[key])).replace(
                            Path(old).as_posix(), Path(package[key]).as_posix())
                if prior_main != Path(package["main_ini_path"]).read_text(encoding="utf-8"):
                    raise ValueError("experiment.prepared_package_mismatch: main_ini_path")
            project.configPath = package["main_ini_path"]
            project.macroPath = package["run_macro_path"]
            project.outputDir = package["output_dir"]
            project.workspaceRoot = package["package_dir"]
            project.threads = project.runSettings.threads
            project.seed = "" if project.runSettings.seed is None else str(project.runSettings.seed)
            project.runName = project.runSettings.run_name
            result.update(package=package, package_report=text)
        else:
            project.outputDir = str(root / "output")
            (root / "config").mkdir(exist_ok=True)
        # One resource grammar also produces the actual executable input tree.
        # In particular a source-copy geometry keeps its original child base;
        # package_writer's plain copy alone cannot preserve STL/GDML/copies refs.
        if identity["coverage"] == "local_source_copy_compatibility":
            execution_bundle = Path(project.workspaceRoot)
            expected = {str(Path(path).resolve()): {**file_identity(path), "role": role}
                        for role, path in (("main", project.configPath), ("macro", project.macroPath),
                            ("materials", result["package"]["materials_ini_path"]),
                            ("geometry", result["package"]["geometry_ini_path"]))}
            manifest_digest = None
        else:
            from g4usim_gui.core.experiment_bundle import export_bundle
            execution_bundle = root / "execution-inputs"
            bundle = export_bundle(snapshot, execution_bundle)
            replay = bundle["replay_inputs"]
            project.configPath = str(execution_bundle / replay["config"]) if replay["config"] else ""
            project.macroPath = str(execution_bundle / replay["macro"]) if replay["macro"] else ""
            project.workspaceRoot = str(execution_bundle)
            expected = {str((execution_bundle / member["path"]).resolve()):
                        {"sha256": member["sha256"], "size_bytes": member["bytes"], "role": member["role"]}
                        for member in bundle["manifest"]["members"] if member["path"].startswith("resources/")}
            manifest_digest = bundle["manifest_sha256"]
        # Bind generated display paths to the same relocated executable inputs.
        if "package" in result:
            result["package"].update(main_ini_path=project.configPath, run_macro_path=project.macroPath)
        result["execution_bundle"] = {"path": str(execution_bundle), "manifest_sha256": manifest_digest,
                                      "coverage": identity["coverage"]}
        result["required_inputs"] = [path for path in (project.configPath, project.macroPath) if path]
        result["requested_run_name"] = project.runName
        project.executable = project.executable or project.pathSettings.executable
        if action == "initialization":
            result["needs_initialization_plan"] = True
        if action in {"inspect", "run", "initialization"}:
            _, environment = self._environment(snapshot, cwd=project.workspaceRoot)
            execution_identity = capture_identity(snapshot, record["revision"], environment=environment)
            if any(execution_identity[key] != identity[key] for key in
                   ("fingerprint", "resources", "backend")):
                raise WorkflowStaleError("experiment.inputs_changed_while_preparing")
            identity = execution_identity
            result["identity"] = identity
        result.update(_project=project, command=_arguments(project), expected_inputs=expected)
        result["identity_after_prepare"] = capture_identity(snapshot, record["revision"], environment=environment)
        if result["identity_after_prepare"] != identity:
            raise WorkflowStaleError("experiment.inputs_changed_while_preparing")
        _persist({**record, **{key: value for key, value in result.items() if not key.startswith("_")}})
        return result

    def _prepared(self, result, action):
        record = self._active["record"]
        record.update({key: value for key, value in result.items() if not key.startswith("_")})
        if not result["can_run"]:
            return self._finish("failed", "experiment.fields_rejected")
        # Fresh content changes permanently retire previous qualifications.
        identity = result["identity"]
        for old in self._records:
            previous = old.get("identity", {})
            if (old is not record and previous.get("identity_scope") == identity.get("identity_scope")
                    and previous.get("fingerprint") != identity["fingerprint"]):
                old.update(stale=True, stale_reason="input_or_environment_identity_changed")
        if action in {"fields", "generate"}:
            return self._finish("passed", "experiment." + action + "_completed")
        project = result["_project"]
        self.run_project = project
        self._active["project"] = project
        external_run = action == "run" and project.runInputMode == "external"
        self._active["phase"] = "initialization_inspect" if action == "initialization" else "run_inspect" if external_run else action
        if action in {"inspect", "initialization"} or external_run:
            self._inspect.setProgram(project.executable)
            self._inspect.setArguments(["--inspect-run", *result["command"][1:]])
            self._inspect.setWorkingDirectory(project.workspaceRoot or str(Path.cwd()))
            self._inspect.start()
        else:
            errors = self.runner.validate_project(project, ready_to_run=True)
            if errors:
                return self._finish("failed", "\n".join(errors))
            self.runner.start(project, result["command"])
        self._notify(record)

    def _start_action(self, action, level, expected_revision=None, prepared_package=None):
        record = self._begin("validate" if action in {"fields", "initialization"} else action, level, expected_revision)
        snapshot = self._active["snapshot"]
        frozen_record = _json_record(record)
        self._work(lambda: self._prepare(snapshot, frozen_record, action, prepared_package),
                   lambda result: self._prepared(result, action))
        return copy.deepcopy(record)

    def inspect(self, *, expected_revision=None, prepared_package=None):
        return self._start_action("inspect", "inspect", expected_revision, prepared_package)

    def validate(self, level="fields", *, expected_revision=None, prepared_package=None):
        if level not in {"fields", "initialization"}:
            raise ValueError("Use run for events and evaluate for explicit physical comparison")
        return self._start_action(level, level, expected_revision, prepared_package)

    def generate(self, *, expected_revision=None, prepared_package=None):
        return self._start_action("generate", "generation", expected_revision, prepared_package)

    def run(self, *, expected_revision=None, prepared_package=None):
        return self._start_action("run", "execution", expected_revision, prepared_package)

    def apply(self, candidate: WorkspaceSnapshot, *, label="Apply configuration", expected_revision=None, apply_snapshot=None):
        self._owner()
        if self.busy:
            raise WorkflowBusyError("experiment.busy")
        candidate = clone_snapshot(candidate)
        record = self._begin("apply", "fields", expected_revision)
        revision = self._active["revision"]
        projection = apply_snapshot if apply_snapshot is not None else self._projection
        def accept(result):
            report = result["report"]
            record.update(report=report, diagnostics=report.to_dict())
            if not report.can_run:
                return self._finish("failed", "experiment.fields_rejected")
            self.session.replace(label, candidate, expected_revision=revision, apply=projection)
            # Retire old records, but qualify this transaction at its accepted revision.
            self.invalidate("configuration_applied")
            self._active["revision"] = self.session.revision
            self._active["epoch"] = self._epoch
            record.update(revision=self.session.revision, stale=False)
            record["identity"] = result["identity"]
            record["identity"]["revision"] = self.session.revision
            record.pop("stale_reason", None)
            self._finish("passed", "experiment.configuration_applied")
        def validate_candidate():
            report = _field_report(candidate)
            return {"report": report, "identity": capture_identity(candidate, revision) if report.can_run else None}
        self._work(validate_candidate, accept)
        return copy.deepcopy(record)

    def _inspect_error(self, error):
        if self._active is not None and self._active["phase"] in {"inspect", "initialization_inspect", "run_inspect"} and error == QProcess.FailedToStart:
            self._finish("failed", self._inspect.errorString())

    def _inspect_finished(self, code, exit_status):
        if self._active is None or self._active["phase"] not in {"inspect", "initialization_inspect", "run_inspect"}:
            return
        stdout = bytes(self._inspect.readAllStandardOutput())
        stderr = bytes(self._inspect.readAllStandardError())
        record = self._active["record"]
        snapshot = self._active["snapshot"]
        def verify():
            root = Path(record["record_dir"])
            (root / "inspect.stdout.log").write_bytes(stdout)
            (root / "inspect.stderr.log").write_bytes(stderr)
            try:
                current = (_original_inspection_identity(snapshot, record["revision"])
                    if record.get("original_input_inspection") else
                    capture_identity(snapshot, record["revision"], environment=record["identity"]["environment"]))
            except OSError as error:
                raise WorkflowStaleError("experiment.inputs_changed_during_inspection") from error
            if current != record["identity"]:
                raise WorkflowStaleError("experiment.inputs_changed_during_inspection")
            if code != 0 or exit_status != QProcess.NormalExit:
                raise ValueError("experiment.inspect_failed: " + stderr.decode("utf-8", "replace"))
            plan = load_json_strict(stdout)
            if (not isinstance(plan, dict) or plan.get("schema") != "G4UniversalSimRunPlan"
                    or plan.get("version") != 1 or plan.get("configuration_phase") != "before_macro"):
                raise ValueError("experiment.inspect_protocol")
            return plan
        if self._active["phase"] == "initialization_inspect":
            self._work(verify, self._initialization_plan)
        elif self._active["phase"] == "run_inspect":
            def inspected_for_run(plan):
                self._active["record"]["plan"] = plan
                self._active["phase"] = "run"
                self.runner.start(self._active["project"], self._active["record"]["command"])
                self._notify(self._active["record"])
            self._work(verify, inspected_for_run)
        else:
            self._work(verify, lambda plan: self._finish("passed", "experiment.configure_preflight_only", plan=plan,
                                                       initialization="unobserved", simulation="unobserved"))

    def _initialization_plan(self, plan):
        record = self._active["record"]
        project = copy.deepcopy(self._active["project"])
        def prefix():
            commands = plan["macro_plan"]["commands"]
            lines = []
            for item in commands:
                if item["category"] == "beam_on":
                    break
                text = item["text"]
                command = text.split()[0].lower()
                # The backend expanded/preflighted dynamic control commands.
                # Keep that canonical sequence, never reinterpret a raw macro.
                if command in {"/run/reinitializegeometry", "/run/reinitializephysics"}:
                    raise ValueError("experiment.initialization_prefix_cannot_preserve_reinitialization")
                lines.append(text)
            if not any(line.split()[0].lower() == "/run/initialize" for line in lines):
                lines.append("/run/initialize")
            root = Path(record["record_dir"])
            mesh = root / "initialized-geometry.json"
            lines.extend(("/geometry/test/run", "/AIHL/geometry/exportMesh " + mesh.as_posix()))
            macro = root / "initialize-prefix.mac"
            macro.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            expected = copy.deepcopy(record["expected_inputs"])
            expected[str(macro.resolve())] = {**file_identity(macro), "role": "macro"}
            original = project.macroPath
            project.macroPath = str(macro)
            result = {"plan": plan, "initialization_mesh": str(mesh), "expected_inputs": expected,
                    "original_macro_identity": file_identity(original) if original else None,
                    "original_macro": original, "prefix_identity": file_identity(macro),
                    "required_inputs": [p for p in (project.configPath, str(macro)) if p],
                    "command": _arguments(project), "_project": project}
            _persist({**record, **{key: value for key, value in result.items() if not key.startswith("_")}})
            return result
        def start(result):
            record.update({key: value for key, value in result.items() if not key.startswith("_")})
            self._active.update(phase="initialization", project=result["_project"])
            self.run_project = result["_project"]
            self.runner.start(self.run_project, result["command"])
            self._notify(record)
        self._work(prefix, start)

    def _run_error(self, message):
        if self._active is not None and self._active["phase"] in {"run", "initialization"} and not self.runner.is_running():
            self._finish("failed", str(message))

    def _run_finished(self, code):
        if self._active is None or self._active["phase"] not in {"run", "initialization"}:
            return
        context = self._active
        result = self.runner.last_result
        project = copy.deepcopy(context["project"])
        record = copy.deepcopy(context["record"])
        snapshot = context["snapshot"]
        phase = context["phase"]
        context["record"].update(exit_code=code, output_dir=project.outputDir,
                                 result=asdict(result) if isinstance(result, RunResult) else None)
        def verify():
            if not isinstance(result, RunResult):
                raise ValueError("experiment.runner_result_unavailable")
            evidence = output_evidence(project.outputDir, fresh=True)
            if evidence.status != "verified":
                raise WorkflowEvidenceError("experiment.f1_provenance_unavailable", {"provenance_status": evidence.status}, unobserved=True)
            document = evidence.document
            facts = parse_run_summary(Path(project.outputDir) / "run_summary.txt").key_values
            # The legacy text reader strips Unicode whitespace. Labels are not
            # identifiers: compare exact backend JSON values instead.
            for key in ("run_name", "effective_run_name"):
                if key in document["values"]:
                    facts[key] = document["values"][key]
            record["output_dir"] = project.outputDir
            _verify_request_binding(record, facts)
            inputs = document["provenance"]["inputs"]
            read_facts = {"actual_inputs": inputs, "execution_id": document["provenance"]["execution_id"],
                          "metadata_sha256": evidence.manifest_digest,
                          "input_coverage": document["provenance"]["input_coverage"],
                          "input_exclusions": document["provenance"]["input_exclusions"]}
            for observed in inputs:
                if observed["status"] != "recorded":
                    raise WorkflowEvidenceError("experiment.actual_input_unobserved", read_facts, unobserved=True)
                path = _observed_path(observed["path"], project.workspaceRoot)
                expected = record["expected_inputs"].get(path)
                if expected is None or expected["sha256"] != observed["sha256"] or expected["size_bytes"] != observed["size_bytes"]:
                    raise WorkflowEvidenceError("experiment.actual_read_identity_mismatch: " + observed["role"], read_facts)
            for path, expected in record["expected_inputs"].items():
                if path in record["required_inputs"] and not any(_observed_path(row["path"], project.workspaceRoot) == path and row["sha256"] == expected["sha256"] for row in inputs):
                    raise ValueError("experiment.required_input_not_read")
                if file_identity(path) != {key: expected[key] for key in ("sha256", "size_bytes")}:
                    raise WorkflowStaleError("experiment.execution_inputs_changed")
            _, environment = self._environment(snapshot, cwd=project.workspaceRoot)
            current = capture_identity(snapshot, record["revision"], environment=environment)
            if current != record["identity"]:
                raise WorkflowStaleError("experiment.inputs_or_environment_changed_during_run")
            facts_out = {"result": asdict(result), "exit_code": code,
                         "output_dir": project.outputDir, "execution_id": document["provenance"]["execution_id"],
                         "metadata_sha256": evidence.manifest_digest,
                         "actual_inputs": inputs, "build": document["provenance"]["build"],
                         "random_settings": {key: value for key, value in facts.items()
                              if "seed" in key or "random_engine" in key or key in {"actual_thread_count", "effective_threads"}}}
            facts_out.update(read_facts)
            facts_out["observed_run_name"] = facts.get("run_name", "unknown")
            capabilities = record["identity"]["environment"].get("capabilities", {}).get("data", {})
            for key in ("source_fingerprint", "git_commit"):
                if key in capabilities and capabilities[key] != document["provenance"]["build"].get(key):
                    raise ValueError("experiment.running_backend_build_mismatch: " + key)
            if phase == "initialization":
                mesh = Path(record["initialization_mesh"])
                from g4usim_gui.preview3d.backend_mesh import load_backend_mesh
                load_backend_mesh(mesh)
                logs = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in
                    (Path(project.outputDir).parent / "logs").glob("*.log"))
                if re.search(r"GeomVol1002|Overlap is detected|overlap[s]? detected", logs, re.IGNORECASE):
                    raise ValueError("experiment.geometry_overlap_reported")
                if (result.state != "no_run" or code != 0 or facts.get("status") != "completed"
                        or facts.get("macro_execution_status") != "completed" or result.run_count != 0):
                    raise ValueError("experiment.initialization_not_confirmed")
                facts_out.update(initialization_mesh_identity=file_identity(mesh),
                    geometry_check="executed_no_reported_overlap", events="unobserved")
            elif result.state != "success":
                raise ValueError("experiment.events_not_completed: " + result.reason)
            return facts_out
        self._work(verify, lambda facts: self._finish("passed", "experiment." + phase + "_evidence_confirmed", **facts))

    def cancel(self, force=False):
        self._owner()
        if self._active is None:
            return
        self._active["cancelled"] = True
        if self._inspect.state() != QProcess.NotRunning:
            (self._inspect.kill if force else self._inspect.terminate)()
        elif self.runner.is_running():
            (self.runner.kill if force else self.runner.terminate)()
        # Do not cancel EvidenceJob delivery: await the worker, preserving its
        # effects and preventing another action racing an unfinished publication.
        self._notify(self._active["record"])

    def close(self):
        """Drain read workers and release file watchers without blocking Qt.

        Returns True when drained, otherwise emits closed() later. An active
        simulation is not implicitly terminated; the owner requests cancel first.
        """
        self._owner()
        if self._closed:
            return True
        self._closing = True
        self._refresh_timer.stop()
        paths = self._watcher.files() + self._watcher.directories()
        if paths:
            self._watcher.removePaths(paths)
        if (self._active is not None or self.runner.is_running() or self._inspect.state() != QProcess.NotRunning
                or any(job.pending for job in (self._job, self._history_job, self._refresh_job))):
            QTimer.singleShot(10, self.close)
            return False
        for job in (self._job, self._history_job, self._refresh_job):
            job.close()
        self._closed = True
        self.closed.emit()
        return True

    def evaluate(self, run_id=None, comparisons=None, *, expected_revision=None):
        source = next((r for r in reversed(self.records()) if r.get("action") == "run" and
                       (run_id is None or r.get("run_id") == run_id)), None)
        if (source is not None and (source.get("status") != "passed" or
                (source.get("stale") and source.get("session_id") == self._session_id))):
            raise WorkflowStaleError("experiment.current_completed_run_required")
        if not isinstance(comparisons, list) or not comparisons:
            raise ValueError("experiment.explicit_comparisons_required")
        specifications = copy.deepcopy(comparisons)
        record = self._begin("evaluate", "physics", expected_revision)
        snapshot = self._active["snapshot"]
        root, session_id = self.records_root, self._session_id
        def compare():
            candidate = source
            if candidate is None:
                history = []
                for path in root.glob("*/record.json"):
                    item = load_json_strict(path.read_bytes())
                    if item.get("action") == "run" and (run_id is None or item.get("run_id") == run_id):
                        history.append(item)
                history.sort(key=lambda item: item.get("created_at", ""))
                candidate = history[-1] if history else None
            if (candidate is None or candidate.get("status") != "passed" or
                    (candidate.get("stale") and candidate.get("session_id") == session_id)):
                raise WorkflowStaleError("experiment.completed_historical_run_required")
            execution_cwd = candidate.get("execution_bundle", {}).get("path")
            _, environment = self._environment(snapshot, cwd=execution_cwd)
            identity = capture_identity(snapshot, record["revision"], environment=environment)
            if identity["execution_fingerprint"] != candidate["identity"]["execution_fingerprint"]:
                raise WorkflowStaleError("experiment.run_identity_changed")
            evidence = output_evidence(candidate["output_dir"], fresh=True)
            if (evidence.status != "verified" or evidence.manifest_digest != candidate["metadata_sha256"] or
                    evidence.document["provenance"]["execution_id"] != candidate["execution_id"]):
                raise ValueError("experiment.run_evidence_changed")
            facts = parse_run_summary(Path(candidate["output_dir"]) / "run_summary.txt").key_values
            for key in ("run_name", "effective_run_name"):
                if key in evidence.document["values"]:
                    facts[key] = evidence.document["values"][key]
            _verify_request_binding(candidate, facts)
            outcomes = [_compare_csv(evidence, candidate, item, Path(record["record_dir"]) / "references") for item in specifications]
            return {"identity": identity, "evaluated_run_id": candidate["run_id"],
                    "evaluation_scope": "explicit_reference_only_not_general_physics_validation",
                    "comparisons": outcomes, "reference_records": [item["specification"] for item in outcomes]}
        def compared(facts):
            passed = all(item["passed"] for item in facts["comparisons"])
            self._finish("passed" if passed else "failed", "experiment.explicit_physical_comparison", **facts)
        self._work(compare, compared)
        return copy.deepcopy(record)

    def export(self, destination, resource_policy=None, *, expected_revision=None):
        record = self._begin("export", "export", expected_revision)
        snapshot = self._active["snapshot"]
        history = [_portable_record(r) for r in self.records() if r.get("record_id") != record["record_id"] and r.get("status") != "pending"]
        record["destination"] = str(Path(destination).absolute())
        def publish():
            from g4usim_gui.core.experiment_bundle import export_bundle
            return export_bundle(snapshot, destination, validation_records=history, resource_policy=resource_policy)
        self._work(publish, lambda facts: self._finish("passed", "experiment.bundle_exported", bundle=facts))
        return copy.deepcopy(record)

    def import_history(self, records):
        record = self._begin("import_history", "history")
        imported = copy.deepcopy(records)
        root = self.records_root
        def store():
            result = []
            for wrapper in imported:
                item = copy.deepcopy(wrapper.get("record", wrapper))
                item.pop("report", None)
                item.update(record_id=uuid4().hex, status="stale", stale=True,
                    stale_reason="imported_history_requires_revalidation", session_id="historical",
                    schema="g4usim_experiment_record_v1")
                item["record_dir"] = str(root / item["record_id"])
                _persist(item)
                result.append(item)
            return result
        def loaded(items):
            self._records[-1:-1] = items
            self._finish("passed", "experiment.history_imported", imported_count=len(items))
        self._work(store, loaded)
        return copy.deepcopy(record)


def _compare_csv(evidence, run_record, specification, reference_store=None):
    """Narrow explicit estimator: complete per-event total sensitive energy.

    No external observed/pass/sigma is accepted. Unknown sampling errors remain
    unavailable; reference uncertainty is explicit and never silently zero.
    """
    required = {"artifact", "column", "quantity", "unit", "reference", "reference_unit",
                "absolute_tolerance", "relative_tolerance", "source", "statistical_method",
                "sigma_multiplier", "weighted", "normalization", "run", "object", "reference_file"}
    optional = {"reference_sha256"}
    if not isinstance(specification, dict) or set(specification) - required - optional or required - set(specification):
        raise ValueError("experiment.comparison_fields_required")
    item = specification
    for key in ("quantity", "unit", "source", "object"):
        if not isinstance(item[key], str) or not item[key].strip():
            raise ValueError("experiment.comparison_text_required: " + key)
    if item["unit"] != "MeV" or item["reference_unit"] != "MeV":
        raise ValueError("experiment.comparison_unit_mismatch")
    for key in ("reference", "absolute_tolerance", "relative_tolerance", "sigma_multiplier"):
        if type(item[key]) not in (float, int) or not math.isfinite(item[key]) or (key != "reference" and item[key] < 0):
            raise ValueError("experiment.comparison_finite_value_required: " + key)
    if (type(item["weighted"]) is not bool or item["normalization"] != "per_event"
            or item["quantity"] != "energy_deposition" or item["object"] != "sensitive_total"
            or item["column"] != ("weighted_edep_MeV" if item["weighted"] else "raw_edep_MeV")
            or item["statistical_method"] != "mean_standard_error"
            or type(item["run"]) is not int or item["run"] < 0):
        raise ValueError("experiment.comparison_estimator_required")
    reference_raw = Path(item["reference_file"]).read_bytes()
    if len(reference_raw) > 1024 * 1024:
        raise ValueError("experiment.reference_size_limit")
    import hashlib
    reference = {"sha256": hashlib.sha256(reference_raw).hexdigest(), "size_bytes": len(reference_raw)}
    if item.get("reference_sha256", reference["sha256"]) != reference["sha256"]:
        raise ValueError("experiment.reference_hash_mismatch")
    reference_data = load_json_strict(reference_raw)
    if (not isinstance(reference_data, dict) or reference_data.get("schema") != "g4usim_physical_reference_v1"
            or not reference_data.get("conditions") or reference_data.get("source_kind") not in {"user_supplied", "analytic"}
            or type(reference_data.get("value")) not in (int, float)
            or not math.isfinite(reference_data["value"]) or reference_data["value"] != item["reference"]):
        raise ValueError("experiment.reference_json_required")
    for key in ("quantity", "unit", "weighted", "normalization", "object", "run", "source"):
        if type(reference_data.get(key)) is not type(item[key]) or reference_data.get(key) != item[key]:
            raise ValueError("experiment.reference_definition_mismatch: " + key)
    runs = [row for row in evidence.document["runs"] if row["run_id"] == item["run"]]
    if len(runs) != 1 or runs[0]["completed_events"] <= 0:
        raise ValueError("experiment.reference_run_missing")
    complete_n = runs[0]["completed_events"]
    paths = item["artifact"] if isinstance(item["artifact"], list) else [item["artifact"]]
    values, identifiers = [], set()
    for name in paths:
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError("experiment.registered_artifact_required")
        path = evidence.require(name)
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            if item["column"] not in row:
                raise ValueError("experiment.comparison_column_missing")
            value = float(row[item["column"]])
            if not math.isfinite(value):
                raise ValueError("experiment.comparison_nonfinite_observation")
            values.append(value)
            if not name.startswith("event_edep_"):
                raise ValueError("experiment.independent_events_required")
            raw_identity = (row.get("runID"), row.get("eventID"))
            if any(value is None or re.fullmatch(r"[0-9]+", value) is None for value in raw_identity):
                raise ValueError("experiment.event_sample_identity_invalid")
            identity = tuple(int(value) for value in raw_identity)
            if identity in identifiers or item["run"] != identity[0]:
                raise ValueError("experiment.event_sample_identity_invalid")
            if not 0 <= identity[1] < complete_n:
                raise ValueError("experiment.event_id_outside_completed_run")
            identifiers.add(identity)
    if len(values) != complete_n or (len(values) < 2 and item["sigma_multiplier"] > 0):
        raise ValueError("experiment.complete_event_sample_required_sigma_unknown")
    observed = statistics.mean(values)
    sigma = statistics.stdev(values) / math.sqrt(len(values)) if len(values) >= 2 else None
    threshold = item["absolute_tolerance"] + item["relative_tolerance"] * abs(item["reference"])
    if sigma is not None:
        threshold += item["sigma_multiplier"] * sigma
    if not math.isfinite(threshold) or not math.isfinite(observed) or (sigma is not None and not math.isfinite(sigma)):
        raise ValueError("experiment.comparison_numeric_overflow")
    bound = copy.deepcopy(item)
    bound["reference_sha256"] = reference["sha256"]
    if reference_store is not None:
        reference_store.mkdir(parents=True, exist_ok=True)
        preserved = reference_store / (reference["sha256"] + ".json")
        if not preserved.exists():
            with preserved.open("xb") as handle:
                handle.write(reference_raw)
        elif file_identity(preserved) != reference:
            raise ValueError("experiment.preserved_reference_changed")
        bound["reference_file"] = str(preserved)
    return {"specification": bound, "reference_identity": reference,
            "reference_source_verification": "user_supplied_unverified_source",
            "reference_conditions": reference_data["conditions"],
            "estimator": "complete_per_event_mean", "uncertainty_status": "available" if sigma is not None else "insufficient_events",
            "observed": observed, "standard_error": sigma, "sample_count": len(values),
            "threshold": threshold, "passed": abs(observed - item["reference"]) <= threshold}
