"""K2-2 static acceptance: standalone D:\\Geant4 project export (no GUI, no backend).

Covers the frozen contract's P1-P4, P5 (layout/commands), P7 (static), P8 and the
R1-R12 refusal codes that can be exercised without a compiler or a Geant4 run.
Real build/run evidence (P5/P6) belongs to the K2-3 limited integration slice.

The contract is docs/collab/outbox/20261107-k2-contract.md (frozen by
docs/collab/decisions/20261107-k2-contract-freeze.md).  The manifest schema
assertions below are written against section 4.3, not against whatever the
implementation happens to emit.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from g4usim_gui.core import export_project as exporter  # noqa: E402
from g4usim_gui.core import wizard  # noqa: E402
from g4usim_gui.core.project import G4USimProject  # noqa: E402

EXAMPLES = ROOT / "examples" / "07_parallel_world_box"
EXAMPLE_FILES = ("README.md", "main.ini", "geometry.ini", "materials.ini",
                 "parallel.ini", "run.mac")
MANIFEST_SCHEMA = "g4usim_export_project"
IDENTITY_ALGORITHM = "sha256_sorted_sha256_path_lines_v1"
ROLES = {"source", "header", "cmake", "tool", "schema", "doc", "license",
         "notice", "template_config", "template_macro", "project_config",
         "project_macro", "readme_export", "example"}
REWRITES = {"verbatim", "path_rewrite", "generated"}
LOCAL_COLLAB_PRESENT = (ROOT / "tools" / "collab").is_dir()
# Reuse the frozen platform-path fixture policy instead of declaring new
# drive-letter literals here: test_platform_path_fixture_policy.py pins the
# policy at four declarations in three files, and adding rows would require
# changing that frozen test (outside the authorised repair files).  The value
# below is the existing named "rejected archive member" fixture, used as
# hostile archive-member data only and never opened.
PATH_FIXTURE_POLICY = json.loads(
    (ROOT / "tools" / "platform_path_fixtures.json").read_text(encoding="utf-8"))
REJECTED_DRIVE_MEMBER = next(
    row["value"] for row in PATH_FIXTURE_POLICY["fixtures"]
    if row["constant"] == "ABSOLUTE_ARCHIVE_MEMBER_FIXTURE")
SELECTIONS = {"opened_project", "generated_package"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_of(destination: Path) -> dict:
    return read_json(destination / "export-manifest.json")


def expect_error(operation, kind: str) -> exporter.ExportError:
    try:
        operation()
    except exporter.ExportError as error:
        assert error.kind == kind, (error.kind, kind, error.message)
        return error
    raise AssertionError(f"expected ExportError({kind})")


def gui_project_for_wizard() -> G4USimProject:
    project = G4USimProject()
    result = wizard.build(wizard.default_spec("single_target"))
    wizard.apply_to_project(project, result)
    return project


def file_hashes(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): sha256(path)
            for path in sorted(root.rglob("*")) if path.is_file()}


def example_hashes() -> dict[str, str]:
    return {name: sha256(EXAMPLES / name) for name in EXAMPLE_FILES}


def make_junction(link: Path, target: Path) -> None:
    """Create a directory junction (Windows) or symlink (POSIX) for the probe."""
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise OSError(f"mklink failed: {result.stdout}{result.stderr}")
    else:
        os.symlink(target, link, target_is_directory=True)


def template_identity_of(members: list[dict]) -> dict:
    ordered = sorted(members, key=lambda member: member["path"])
    text = "".join(f"{member['sha256']}  {member['path']}\n" for member in ordered)
    return {"algorithm": IDENTITY_ALGORITHM,
            "value": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "file_count": len(ordered),
            "bytes_total": sum(int(member["bytes"]) for member in ordered)}


def poison_template_member(root: Path, key: str, value: str) -> None:
    manifest_path = root / "packaging" / exporter.TEMPLATE_MANIFEST_NAME
    manifest = read_json(manifest_path)
    members = manifest["members"]
    members[0][key] = value
    manifest["identity"] = template_identity_of(members)
    manifest_path.write_bytes(
        (json.dumps(manifest, ensure_ascii=False, allow_nan=False,
                    sort_keys=True, indent=2) + "\n").encode("utf-8"))


def template_copy(destination: Path) -> Path:
    """Copy exactly the frozen template members into a fresh directory."""
    layout = exporter.load_template_layout(ROOT)
    destination.mkdir(parents=True)
    for member in layout.members:
        source = layout.root / member.source_path
        target = destination / member.source_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    manifest = layout.manifest_path.read_bytes()
    (destination / "packaging").mkdir(parents=True, exist_ok=True)
    (destination / "packaging" / exporter.TEMPLATE_MANIFEST_NAME).write_bytes(manifest)
    return destination


def identity_from_files(files: dict[str, bytes]) -> dict:
    ordered = sorted(files)
    text = "".join(f"{hashlib.sha256(files[key]).hexdigest()}  {key}\n"
                   for key in ordered)
    return {"algorithm": IDENTITY_ALGORITHM, "file_count": len(ordered),
            "digest": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def check_manifest_schema(manifest: dict, selection: str, *, name: str) -> None:
    """Contract section 4.3 required fields, types and enums."""
    assert manifest["schema"] == MANIFEST_SCHEMA, manifest["schema"]
    assert manifest["version"] == 1
    assert isinstance(manifest["created_utc"], str) and manifest["created_utc"]

    tool = manifest["tool"]
    assert tool["name"] == "G4UniversalSim"
    assert isinstance(tool["version"], str)
    assert isinstance(tool["git_head"], str) and isinstance(tool["git_source_state"], str)
    assert tool["template_origin"] in {"packaged", "checkout"}
    assert isinstance(tool["template_root_label"], str)
    for key in ("template_manifest_digest", "template_digest"):
        assert len(tool[key]) == 64 and int(tool[key], 16) >= 0, key
    assert isinstance(tool["template_file_count"], int) and tool["template_file_count"] > 0
    assert tool["template_manifest_digest"] == tool["template_digest"]

    identity = manifest["identity"]
    assert identity["algorithm"] == IDENTITY_ALGORITHM
    assert isinstance(identity["file_count"], int) and identity["file_count"] > 0
    assert len(identity["digest"]) == 64 and int(identity["digest"], 16) >= 0
    assert identity["file_count"] == len(manifest["files"])

    template = manifest["template_identity"]
    assert isinstance(template["manifest_path"], str) and template["manifest_path"]
    for key in ("manifest_digest", "computed_digest"):
        assert len(template[key]) == 64 and int(template[key], 16) >= 0, key
    assert template["manifest_digest"] == template["computed_digest"]
    assert template["matched"] is True
    assert template["manifest_digest"] == tool["template_manifest_digest"]

    project = manifest["project"]
    assert isinstance(project["name"], str) and project["name"] == name
    assert project["selection"] in SELECTIONS
    assert project["selection"] == selection
    entry = project["entry"]
    assert entry["config"] == "project/main.ini"
    assert entry["macro"] == "project/macros/run.mac"
    assert entry["output"] == "runs/default/output"
    if selection == "opened_project":
        assert isinstance(project["original_project_root_audit"], str)
        assert project["original_project_root_audit"] == str(EXAMPLES.resolve())
    else:
        assert project["original_project_root_audit"] is None

    for entry in manifest["files"]:
        assert set(entry) == {"path", "role", "sha256", "bytes"}, entry
        assert entry["role"] in ROLES, entry
        assert len(entry["sha256"]) == 64
        assert isinstance(entry["bytes"], int) and entry["bytes"] >= 0

    for entry in manifest["inputs"]:
        assert entry["source_kind"] in {"opened_project", "generated"}
        assert isinstance(entry["role"], str) and entry["role"]
        assert isinstance(entry["original_path"], str) and entry["original_path"]
        assert isinstance(entry["copied_to"], str) and entry["copied_to"]
        assert entry["rewrite"] in REWRITES, entry
        assert entry["sha256_before"] is None or len(entry["sha256_before"]) == 64
        assert len(entry["sha256_after"]) == 64
        if entry["source_kind"] == "generated":
            assert entry["original_path"].startswith("generated:")
            assert entry["sha256_before"] is None
            assert entry["rewrite"] == "generated"
        else:
            assert os.path.isabs(entry["original_path"])
            assert entry["rewrite"] in {"verbatim", "path_rewrite"}

    build = manifest["build"]
    assert isinstance(build["requirements"], list) and len(build["requirements"]) >= 5
    assert build["standalone_flag"] == "G4USIM_STANDALONE_EXPORT=ON"
    assert isinstance(build["docs"], list) and "README-EXPORT.md" in build["docs"]
    for platform in ("windows", "linux"):
        commands = build["commands"][platform]
        assert isinstance(commands, list) and len(commands) >= 4
        for command in commands:
            assert isinstance(command, str) and command and "\\\n" not in command

    tests = manifest["tests"]
    assert tests["component_ctest_label_regex"] == "^component$"
    assert tests["component_ctest_names"] == ["h2_volume_scoring_check",
                                              "parallel_scoring_component"]
    assert isinstance(tests["smoke_runs"], list) and tests["smoke_runs"]

    licenses = manifest["licenses"]
    assert licenses["project_code"] == "not_declared_in_repository"
    assert isinstance(licenses["entries"], list) and len(licenses["entries"]) == 2
    assert isinstance(manifest["limits"], dict) and manifest["limits"]
    assert isinstance(manifest["not_included"], list) and manifest["not_included"]


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="g4usim-k2-test-"))
    originals_before = example_hashes()
    links_supported = False
    try:
        external = exporter.select_external_project(EXAMPLES)
        generated = exporter.select_generated_project(gui_project_for_wizard())

        # --- P1: S-A export -------------------------------------------------
        dest_a1 = work / "a1"
        result_a1 = exporter.export_project(dest_a1, external)
        assert result_a1["destination"] == str(dest_a1)
        assert result_a1["payload_identity"]["file_count"] > 300
        for relative in ("CMakeLists.txt", "main.cc", "CMakePresets.json",
                         "src/Core/SimulationManager.cc",
                         "include/Core/SimulationManager.hh",
                         "project/main.ini", "project/config/materials.ini",
                         "project/config/geometry.ini",
                         "project/config/parallel.ini",
                         "project/macros/run.mac", "README.md", "README-EXPORT.md",
                         "export-template-manifest.json", "export-manifest.json",
                         "licenses/Geant4-LICENSE.txt", "docs/中文使用手册.md"):
            assert (dest_a1 / relative).is_file(), relative
        main_ini = (dest_a1 / "project" / "main.ini").read_text(encoding="utf-8")
        for fragment in ("file = project/config/materials.ini",
                         "config = project/config/geometry.ini",
                         "geometry_config = config/parallel.ini",
                         "dir = runs/default/output",
                         "format = csv"):
            assert fragment in main_ini, fragment
        assert not [
            line for line in main_ini.splitlines()
            if line.strip().startswith("macro")
        ], "the opened project has no [run] macro key"
        for stale in ("D:", "C:", str(EXAMPLES)):
            assert stale not in main_ini, stale
        manifest_a1 = manifest_of(dest_a1)
        check_manifest_schema(manifest_a1, "opened_project", name="parallel_world_box")
        assert manifest_a1["identity"]["file_count"] == \
            result_a1["payload_identity"]["file_count"]
        # The public identity digest can be recomputed from the payload bytes.
        listed = {}
        for entry in manifest_a1["files"]:
            listed[entry["path"]] = (dest_a1 / entry["path"]).read_bytes()
        assert manifest_a1["identity"]["digest"] == identity_from_files(listed)["digest"]
        assert "export-manifest.json" not in listed
        exported_template_manifest = read_json(
            dest_a1 / exporter.TEMPLATE_MANIFEST_COPY)
        template_members = {entry["path"]: entry["role"]
                            for entry in exported_template_manifest["members"]}
        assert template_members.get(
            "scenarios/semiconductor/niel/si_proton.csv") == "example"
        assert not [path for path, role in template_members.items()
                    if role == "example" and path !=
                    "scenarios/semiconductor/niel/si_proton.csv"]
        assert any("si_proton.csv" in item
                   for item in manifest_a1["not_included"])
        main_input = [entry for entry in manifest_a1["inputs"]
                      if entry["copied_to"] == "project/main.ini"][0]
        assert main_input["source_kind"] == "opened_project"
        assert main_input["rewrite"] == "path_rewrite"
        assert all(entry["rewrite"] == "verbatim" for entry in manifest_a1["inputs"]
                   if entry["copied_to"] != "project/main.ini")
        licenses = [entry for entry in manifest_a1["files"] if entry["role"] == "license"]
        assert len(licenses) == 3, len(licenses)
        assert manifest_a1["files"] != []
        # The opened project's README is copied verbatim and audited correctly.
        copied_readme = (dest_a1 / "project" / "README.md").read_bytes()
        assert copied_readme == (EXAMPLES / "README.md").read_bytes()
        readme_input = [entry for entry in manifest_a1["inputs"]
                        if entry["copied_to"] == "project/README.md"][0]
        readme_sha = hashlib.sha256(copied_readme).hexdigest()
        assert readme_input["sha256_before"] == readme_sha
        assert readme_input["sha256_after"] == readme_sha
        # The frozen run command names config, macro and output explicitly.
        run_flags = ("--config project/main.ini --macro project/macros/run.mac "
                     "--output runs/default/output")
        readme_export = (dest_a1 / "README-EXPORT.md").read_text(encoding="utf-8")
        assert run_flags in readme_export
        commands = manifest_a1["build"]["commands"]
        assert run_flags in commands["windows"][-1]
        assert run_flags in commands["linux"][-1]
        assert all(run_flags in run["command"]
                   for run in manifest_a1["tests"]["smoke_runs"])

        # --- P2: S-B generated project --------------------------------------
        dest_b1 = work / "b1"
        result_b1 = exporter.export_project(dest_b1, generated)
        manifest_b1 = manifest_of(dest_b1)
        check_manifest_schema(manifest_b1, "generated_package", name="single_target")
        generated_inputs = [entry for entry in manifest_b1["inputs"]
                            if entry["source_kind"] == "generated"]
        assert len(generated_inputs) >= 4, generated_inputs
        for entry in generated_inputs:
            assert entry["original_path"].startswith("generated:"), entry
            assert entry.get("sha256_before") is None, entry
            assert entry["rewrite"] == "generated", entry
            assert (dest_b1 / entry["copied_to"]).is_file(), entry["copied_to"]
        b_main = (dest_b1 / "project" / "main.ini").read_text(encoding="utf-8")
        assert "[general]" in b_main and "schema_version = 1" in b_main
        assert "file = project/config/materials.ini" in b_main
        assert "config = project/config/geometry.ini" in b_main
        assert not [line for line in b_main.splitlines()
                    if line.strip().startswith("macro")]
        assert not [line for line in b_main.splitlines()
                    if line.strip().startswith("format")]
        assert "generated:" not in b_main
        for text_file in (dest_b1 / "project").rglob("*.ini"):
            text = text_file.read_text(encoding="utf-8")
            assert str(work) not in text, (text_file, "staging path leaked")
            assert "generated:" not in text, text_file

        # --- P3: two destinations differ only in created_utc ----------------
        dest_a2 = work / "a2"
        dest_b2 = work / "b2"
        result_a2 = exporter.export_project(dest_a2, external)
        result_b2 = exporter.export_project(dest_b2, generated)
        for first, second in ((result_a1, result_a2), (result_b1, result_b2)):
            assert first["payload_identity"]["digest"] == \
                second["payload_identity"]["digest"]
        for left_dest, right_dest in ((dest_a1, dest_a2), (dest_b1, dest_b2)):
            left = manifest_of(left_dest)
            right = manifest_of(right_dest)
            left.pop("created_utc")
            right.pop("created_utc")
            assert left == right, "two exports differ beyond created_utc"
            left_files = file_hashes(left_dest)
            right_files = file_hashes(right_dest)
            left_files.pop("export-manifest.json", None)
            right_files.pop("export-manifest.json", None)
            assert left_files == right_files
        assert result_a1["payload_identity"] != result_b1["payload_identity"]

        # --- P4: template identity is the packaged source of truth ----------
        packaged = work / "packaged-template"
        packaged.mkdir()
        sys.path.insert(0, str(ROOT / "packaging"))
        from build_export_template import build_export_template  # noqa: E402
        built = build_export_template(packaged, repo_root=ROOT)
        assert built["members"] == manifest_a1["tool"]["template_file_count"]
        assert built["identity"]["value"] == \
            manifest_a1["tool"]["template_manifest_digest"]
        layout = exporter.load_template_layout(ROOT)
        assert layout.manifest["algorithm"]["name"] == \
            exporter.TEMPLATE_IDENTITY_ALGORITHM
        assert built["identity"]["algorithm"] == \
            "sha256_sorted_sha256_path_lines_v1"
        # The builder publishes exactly the manifest bytes it validated.
        import build_export_template as builder_module  # noqa: E402
        manifest_file = ROOT / "packaging" / exporter.TEMPLATE_MANIFEST_NAME
        declared_members = builder_module._export._validate_manifest(
            read_json(manifest_file), manifest_file)
        stale_staging = work / "stale-staging"
        stale_staging.mkdir()
        expect_error(lambda: builder_module._copy_declared_template(
            ROOT, declared_members, manifest_file, b'{"late": true}\n',
            stale_staging), "input_changed_during_export")
        shutil.rmtree(stale_staging, ignore_errors=True)
        copied_manifest = read_json(dest_a1 / "export-template-manifest.json")
        assert copied_manifest["identity"]["value"] == built["identity"]["value"]
        packaged_template = packaged / "export-template"
        assert (packaged_template / "export_template_manifest.json").is_file()
        for path in sorted(packaged_template.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(packaged_template).as_posix()
            if relative == "export_template_manifest.json":
                continue
            assert (dest_a1 / relative).is_file(), relative
            assert path.read_bytes() == (dest_a1 / relative).read_bytes(), relative
        # A second build must refuse without touching the existing tree.
        before = file_hashes(packaged_template)
        expect_error(lambda: build_export_template(packaged, repo_root=ROOT),
                     "destination_exists")
        assert file_hashes(packaged_template) == before

        # --- P9: portable template closure (canonical text, direct tools) ---
        template_manifest = read_json(ROOT / "packaging" / exporter.TEMPLATE_MANIFEST_NAME)
        template_members = template_manifest["members"]
        tool_paths = [entry["path"] for entry in template_members
                      if entry["path"].startswith("tools/")]
        assert tool_paths, "tools members missing"
        assert not [path for path in tool_paths if path.count("/") > 1], tool_paths
        assert not [path for path in tool_paths if path.startswith("tools/collab/")]
        # Local collaboration helpers only exist in a developer checkout; a
        # clean source archive has none.  Only the state observed at the start of
        # the test is required here, and the test never creates that directory.
        if LOCAL_COLLAB_PRESENT:
            assert (ROOT / "tools" / "collab").is_dir(), "local collaboration files must stay"
        else:
            assert not (ROOT / "tools" / "collab").exists(), \
                "the portable fixture must not create a checkout collaboration directory"
        # A CRLF or LF checkout must produce one canonical template identity.
        # The developer checkout may be all-LF, so build both spellings inside
        # this private portable fixture instead of requiring mixed endings in ROOT.
        portable = work / "portable-template"
        portable.mkdir()
        header_member = next((entry for entry in template_members
                              if entry["path"].endswith(".hh")), None)
        source_member = next((entry for entry in template_members
                              if entry["path"].endswith(".cc")), None)
        assert header_member is not None, "template has no header member"
        assert source_member is not None, "template has no source member"
        for entry in template_members:
            raw = (ROOT / entry["source_path"]).read_bytes()
            canonical = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            target = portable / entry["source_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            if entry["path"] == header_member["path"]:
                target.write_bytes(canonical.replace(b"\n", b"\r\n"))
            elif entry["path"] == source_member["path"]:
                target.write_bytes(canonical)
            else:
                target.write_bytes(raw)
        # A private nested fixture proves tools/<subdir>/ is excluded: it is
        # never created in the checkout and never appears in the closure.
        nested = portable / "tools" / "collab"
        nested.mkdir(parents=True, exist_ok=True)
        (nested / "local_helper.py").write_bytes(b"# portable nested fixture only\n")
        portable_members = exporter.collect_template_members(portable)
        assert not [member.path for member in portable_members
                    if member.path.startswith("tools/collab/")]
        portable_identity = exporter.template_identity(portable_members)
        checkout_identity = exporter.template_identity(
            exporter.collect_template_members(ROOT))
        assert portable_identity == checkout_identity
        assert portable_identity == template_manifest["identity"]
        # Export writes canonical bytes rather than the checkout spelling.
        filter_path = "include/Scoring/VolumeFilter.hh"
        exported_filter = dest_a1 / filter_path
        assert exported_filter.is_file(), filter_path
        exported_raw = exported_filter.read_bytes()
        assert b"\r\n" not in exported_raw, "template copy kept CRLF"
        filter_sha = next(entry["sha256"] for entry in manifest_a1["files"]
                          if entry["path"] == filter_path)
        assert hashlib.sha256(exported_raw).hexdigest() == filter_sha
        # verify_export keeps hashing raw bytes: CRLF tampering is refused.
        tampered = work / "tampered-text"
        shutil.copytree(dest_a1, tampered)
        tamper_file = tampered / filter_path
        tamper_file.write_bytes(tamper_file.read_bytes().replace(b"\n", b"\r\n"))
        expect_error(lambda: exporter.verify_export(tampered),
                     "input_changed_during_export")

        # --- P5: standalone CMake layout and single-line commands -----------
        cmake = (dest_a1 / "CMakeLists.txt").read_text(encoding="utf-8")
        guided = cmake.index("if(NOT G4USIM_STANDALONE_EXPORT)")
        assert "option(G4USIM_STANDALONE_EXPORT" in cmake
        assert cmake.index("find_package(Python3", guided) > guided
        assert 'LABELS "h3;component"' in cmake and 'LABELS "h2;component"' in cmake
        h2_command = (
            "COMMAND h2VolumeScoringCheck "
            "${PROJECT_BINARY_DIR}/h2-component-output ${PROJECT_SOURCE_DIR}"
        )
        assert h2_command in cmake, "the h2 component test must receive the source root"
        readme = (dest_a1 / "README-EXPORT.md").read_text(encoding="utf-8")
        presets = json.loads((dest_a1 / "CMakePresets.json").read_text(encoding="utf-8"))
        windows_binary_dir = next(
            preset["binaryDir"] for preset in presets["configurePresets"]
            if preset.get("name") == "vs2026-x64")
        # The exported preset names the build directory relative to the export
        # root; the README quotes it without the CMake variable prefix.
        windows_binary_dir = windows_binary_dir.replace("${sourceDir}/", "")
        windows_ctest = (
            f'ctest --test-dir {windows_binary_dir} -C Release -L "^component$"')
        for fragment in ("G4USIM_STANDALONE_EXPORT=ON",
                         windows_ctest,
                         'ctest --test-dir build_linux -L "^component$"',
                         "cmake --preset vs2026-x64",
                         "Run from this directory",
                         "project/main.ini"):
            assert fragment in readme, fragment
        assert "\\\n" not in readme
        for platform in ("windows", "linux"):
            for command in manifest_a1["build"]["commands"][platform]:
                assert "\\\n" not in command

        # --- P7 (static): only project/config is referenced, not template ---
        assert (dest_a1 / "config" / "materials" / "material.ini").is_file(), \
            "template config stays"
        poisoned = work / "poisoned-project"
        shutil.copytree(dest_a1, poisoned)
        (poisoned / "config" / "materials" / "material.ini").write_text(
            "[materials]\nfile = poisoned\n", encoding="utf-8")
        assert "file = project/config/materials.ini" in (
            poisoned / "project" / "main.ini").read_text(encoding="utf-8")
        assert "file = config/materials" not in (
            poisoned / "project" / "main.ini").read_text(encoding="utf-8")

        # --- P8: moving the tree keeps the manifest verifiable --------------
        moved = work / "moved"
        shutil.move(str(dest_a1), str(moved))
        verified = exporter.verify_export(moved)
        assert verified["identity"]["digest"] == result_a1["payload_identity"]["digest"]
        assert str(moved) not in (moved / "export-manifest.json").read_text(encoding="utf-8")
        assert str(work) not in (moved / "export-manifest.json").read_text(encoding="utf-8")
        # verify_export checks the whole closure, not only the listed files.
        extra_tree = work / "verify-extra"
        shutil.copytree(moved, extra_tree)
        (extra_tree / "project" / "macros" / "unlisted.mac").write_text(
            "/run/initialize\n", encoding="utf-8")
        expect_error(lambda: exporter.verify_export(extra_tree),
                     "input_changed_during_export")

        # --- P6 (static): rewrite only the value spans ---------------------
        preserved_project = work / "preserved-project"
        shutil.copytree(EXAMPLES, preserved_project)
        preserved_main = preserved_project / "main.ini"
        source_text = preserved_main.read_text(encoding="utf-8")
        crlf_text = source_text.replace("\n", "\r\n")
        crlf_text = crlf_text.replace(
            "file = materials.ini",
            "  file   =   materials.ini   ; keep this comment", 1)
        crlf_text = "\ufeff" + crlf_text.rstrip("\r\n")
        preserved_main.write_bytes(crlf_text.encode("utf-8"))
        preserved_selection = exporter.select_external_project(preserved_project)
        exporter.export_project(work / "preserved-out", preserved_selection)
        preserved_bytes = (work / "preserved-out" / "project" / "main.ini").read_bytes()
        assert preserved_bytes.startswith("\ufeff".encode("utf-8"))
        assert not preserved_bytes.endswith(b"\n")
        assert preserved_bytes.count(b"\r\n") == crlf_text.count("\r\n")
        preserved_text = preserved_bytes.decode("utf-8")
        assert ("  file   =   project/config/materials.ini   ; keep this comment"
                in preserved_text)
        assert "dir = runs/default/output" in preserved_text
        assert "config = project/config/geometry.ini" in preserved_text
        assert "geometry_config = config/parallel.ini" in preserved_text

        # --- P7 (static): one initialize followed by one beamOn -------------
        macro_project = work / "macro-project"
        shutil.copytree(EXAMPLES, macro_project)
        macro_mac = macro_project / "run.mac"
        macro_mac.write_text(
            "/run/initialize\n/run/beamOn 200\n/run/beamOn 200\n",
            encoding="utf-8")
        macro_selection = exporter.select_external_project(macro_project)
        expect_error(lambda: exporter.export_project(work / "macro-out", macro_selection),
                     "unsupported_feature")
        macro_mac.write_text("/run/beamOn 200\n/run/initialize\n", encoding="utf-8")
        expect_error(lambda: exporter.export_project(work / "macro-out-2", macro_selection),
                     "unsupported_feature")

        # --- R1: destination exists -----------------------------------------
        expect_error(lambda: exporter.export_project(work / "a2", external),
                     "destination_exists")

        # --- R2: destination parent missing ---------------------------------
        expect_error(lambda: exporter.export_project(
            work / "missing-parent" / "child", external), "destination_parent_missing")

        # --- R3: a linked file that the INI actually references -------------
        linked_project = work / "linked-project"
        shutil.copytree(EXAMPLES, linked_project)
        real_materials = linked_project / "materials-real.ini"
        real_materials.write_bytes((linked_project / "materials.ini").read_bytes())
        (linked_project / "materials.ini").unlink()
        try:
            os.symlink("materials-real.ini", linked_project / "materials.ini")
        except (OSError, NotImplementedError):
            links_supported = False
        else:
            links_supported = True
            try:
                linked_selection = exporter.select_external_project(linked_project)
            except exporter.ExportError as error:
                assert error.kind == "linked_or_ambiguous_path", error.kind
            else:
                expect_error(lambda: exporter.export_project(
                    work / "linked-out", linked_selection),
                    "linked_or_ambiguous_path")

        if links_supported:
            link_tree = work / "verify-linked"
            shutil.copytree(moved, link_tree)
            victim = link_tree / "project" / "config" / "materials.ini"
            outside = work / "outside-materials.ini"
            outside.write_bytes(victim.read_bytes())
            victim.unlink()
            os.symlink(outside, victim)
            expect_error(lambda: exporter.verify_export(link_tree),
                         "linked_or_ambiguous_path")

        # --- R4: nothing to export ------------------------------------------
        expect_error(lambda: exporter.selection_from_project(None), "selection_unavailable")
        expect_error(lambda: exporter.select_generated_project(G4USimProject()),
                     "unsupported_feature")

        # --- R5: missing external input -------------------------------------
        broken = work / "broken-project"
        shutil.copytree(EXAMPLES, broken)
        (broken / "materials.ini").unlink()
        broken_selection = exporter.select_external_project(broken)
        expect_error(lambda: exporter.export_project(work / "broken-out", broken_selection),
                     "external_or_missing_input")

        # --- R6: unsupported feature ----------------------------------------
        unsupported = work / "unsupported-project"
        shutil.copytree(EXAMPLES, unsupported)
        text = (unsupported / "main.ini").read_text(encoding="utf-8")
        (unsupported / "main.ini").write_text(
            text.replace("particle = proton", "particle = alpha", 1), encoding="utf-8")
        unsupported_selection = exporter.select_external_project(unsupported)
        expect_error(lambda: exporter.export_project(work / "unsupported-out",
                                                     unsupported_selection),
                     "unsupported_feature")

        # --- R8: template unavailable ---------------------------------------
        empty_template = work / "empty-template"
        empty_template.mkdir()
        expect_error(lambda: exporter.export_project(work / "template-out", external,
                                                     template_root=empty_template),
                     "export_template_unavailable")

        # --- R9: destination inside the source project or template tree -----
        expect_error(lambda: exporter.export_project(EXAMPLES / "nested", external),
                     "destination_inside_source")
        # config/ is part of the portable template and therefore exists in a
        # clean source archive; out/ is gitignored and may be absent.
        inside_root = ROOT / "config" / "k2-r9-target"
        expect_error(lambda: exporter.export_project(inside_root, external),
                     "destination_inside_source")
        assert not inside_root.exists()

        # --- R3: template members are safe relative paths -------------------
        # A self-consistent manifest must not smuggle a Windows drive, UNC,
        # absolute or parent-escaping member into the write path.
        hostile_members = (
            ("path", REJECTED_DRIVE_MEMBER),
            ("path", "C:\\evil.txt"),
            ("path", "/absolute/evil.txt"),
            ("path", "../evil.txt"),
            ("source_path", REJECTED_DRIVE_MEMBER),
            ("source_path", "../../evil.txt"),
        )
        for index, (key, value) in enumerate(hostile_members):
            hostile_root = template_copy(work / f"hostile-template-{index}")
            poison_template_member(hostile_root, key, value)
            target = work / f"hostile-out-{index}"
            before = {path for path in work.rglob("*")}
            expect_error(lambda root=hostile_root, out=target: exporter.export_project(
                out, external, template_root=root), "linked_or_ambiguous_path")
            after = {path for path in work.rglob("*")}
            assert before == after, (
                f"{key}={value!r} created files outside staging: "
                f"{sorted(after - before)}")
            assert not target.exists()
            assert not [path for path in work.iterdir()
                        if path.name.startswith(f".{target.name}.k2-")]

        # --- R3: link/../ paths are refused, never folded --------------------
        junction_real = work / "junction-real"
        junction_real.mkdir()
        junctions_supported = False
        try:
            make_junction(work / "junction", junction_real)
        except (OSError, NotImplementedError):
            junctions_supported = False
        else:
            junctions_supported = True
            # Destination with a lexical link component.
            before = {path for path in work.rglob("*")}
            expect_error(lambda: exporter.export_project(
                work / "junction" / ".." / "junction-out", external),
                "linked_or_ambiguous_path")
            after = {path for path in work.rglob("*")}
            assert before == after, sorted(after - before)
            assert not (work / "junction-out").exists()
            # Input reference with a lexical link component.
            linked_examples = work / "linked-examples"
            shutil.copytree(EXAMPLES, linked_examples)
            (linked_examples / "real").mkdir()
            make_junction(linked_examples / "j", linked_examples / "real")
            linked_main = linked_examples / "main.ini"
            linked_text = linked_main.read_text(encoding="utf-8")
            linked_main.write_text(
                linked_text.replace("file = materials.ini",
                                    "file = j/../materials.ini", 1),
                encoding="utf-8")
            linked_selection = exporter.select_external_project(linked_examples)
            expect_error(lambda: exporter.export_project(
                work / "linked-examples-out", linked_selection),
                "linked_or_ambiguous_path")
            assert not (work / "linked-examples-out").exists()
            # Builder package directory with a lexical link component.
            sys.path.insert(0, str(ROOT / "packaging"))
            from build_export_template import build_export_template as builder  # noqa: E402
            linked_package = work / "linked-package"
            linked_package.mkdir()
            expect_error(lambda: builder(work / "junction" / ".." / "linked-package"),
                         "linked_or_ambiguous_path")
            assert not (linked_package / "export-template").exists()

        # --- R11: template identity mismatch --------------------------------
        poisoned_template = template_copy(work / "poisoned-template")
        (poisoned_template / "CMakeLists.txt").write_text("# tampered\n",
                                                          encoding="utf-8")
        expect_error(lambda: exporter.export_project(work / "tampered-out", external,
                                                     template_root=poisoned_template),
                     "template_identity_mismatch")

        # --- R10: an input changed after preparation (private copy only) ----
        private_project = work / "r10-project"
        shutil.copytree(EXAMPLES, private_project)
        private_selection = exporter.select_external_project(private_project)
        payload = exporter._read_external_payload(private_selection)  # noqa: SLF001
        changed_entry = [entry for entry in payload.inputs
                         if entry["rewrite"] == "verbatim"][0]
        changed = Path(changed_entry["original_path"])
        changed.write_bytes(changed.read_bytes() + b"\n")
        expect_error(lambda: exporter._verify_sources_unchanged(payload),  # noqa: SLF001
                     "input_changed_during_export")
        assert example_hashes() == originals_before, "originals must stay untouched"

        # --- R12: write failure cleans staging ------------------------------
        original_publish = exporter._publish  # noqa: SLF001

        def failing_publish(staging, target):
            raise OSError("injected write failure")

        exporter._publish = failing_publish  # type: ignore[assignment]  # noqa: SLF001
        try:
            expect_error(lambda: exporter.export_project(work / "write-failed", external),
                         "write_failed")
        finally:
            exporter._publish = original_publish  # type: ignore[assignment]  # noqa: SLF001
        assert not (work / "write-failed").exists()
        assert not [path for path in work.iterdir()
                    if path.name.startswith(".write-failed.k2-")]

        # --- R12: a denied staging parent fails fast, not after TMP_MAX -----
        blocked_parent = work / "blocked-parent"
        blocked_parent.mkdir()
        blocked_target = blocked_parent / "denied-export"
        denied_calls = []
        original_mkdir = exporter.os.mkdir

        def denied_mkdir(path, mode=0o777, *, dir_fd=None):
            denied_calls.append(str(path))
            raise PermissionError(13, "Access is denied", str(path))

        exporter.os.mkdir = denied_mkdir  # type: ignore[assignment]
        denied_started = time.monotonic()
        try:
            denied_error = expect_error(
                lambda: exporter.export_project(blocked_target, external),
                "write_failed")
        finally:
            exporter.os.mkdir = original_mkdir  # type: ignore[assignment]
        denied_elapsed = time.monotonic() - denied_started
        assert len(denied_calls) == 1, denied_calls
        assert denied_elapsed < 5.0, denied_elapsed
        assert "staging" in denied_error.message, denied_error.message
        assert not blocked_target.exists()
        assert list(blocked_parent.iterdir()) == []

        # Only genuine name collisions are retried, and only a bounded number.
        collision_calls = {"count": 0}
        original_mkdir = exporter.os.mkdir

        def colliding_mkdir(path, mode=0o777, *, dir_fd=None):
            collision_calls["count"] += 1
            if collision_calls["count"] <= 2:
                raise FileExistsError(17, "File exists", str(path))
            return original_mkdir(path, mode)

        exporter.os.mkdir = colliding_mkdir  # type: ignore[assignment]
        try:
            collision_staging = exporter._allocate_staging(  # noqa: SLF001
                work / "collision-target")
        finally:
            exporter.os.mkdir = original_mkdir  # type: ignore[assignment]
        assert collision_calls["count"] == 3, collision_calls
        assert collision_staging.is_dir() and collision_staging.parent == work
        shutil.rmtree(collision_staging, ignore_errors=True)

        exhausted_calls = {"count": 0}
        original_mkdir = exporter.os.mkdir

        def always_colliding(path, mode=0o777, *, dir_fd=None):
            exhausted_calls["count"] += 1
            raise FileExistsError(17, "File exists", str(path))

        exporter.os.mkdir = always_colliding  # type: ignore[assignment]
        try:
            expect_error(
                lambda: exporter._allocate_staging(  # noqa: SLF001
                    work / "always-colliding"),
                "write_failed")
        finally:
            exporter.os.mkdir = original_mkdir  # type: ignore[assignment]
        assert exhausted_calls["count"] == exporter.STAGING_ALLOCATION_ATTEMPTS

        # --- template manifest and checkout round-trip ----------------------
        layout = exporter.load_template_layout(ROOT)
        assert layout.label == "repository-checkout"
        exported_manifest = read_json(dest_a2 / "export-template-manifest.json")
        assert exported_manifest["identity"]["value"] == \
            layout.manifest["identity"]["value"]
        assert len(exported_manifest["members"]) == \
            layout.manifest["identity"]["file_count"]

        print(f"k2 export checks: files={result_a1['payload_identity']['file_count']} "
              f"identity={result_a1['payload_identity']['digest'][:16]} "
              f"template={layout.manifest['identity']['value'][:16]} "
              f"symlinks={'yes' if links_supported else 'skipped'} "
              f"junctions={'yes' if junctions_supported else 'skipped'}")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)
        assert example_hashes() == originals_before, "original examples must not change"


if __name__ == "__main__":
    sys.exit(main())
