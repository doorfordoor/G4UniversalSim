"""E2-S1 editor -> writer boundary regression tests (pure Python, no Qt, no backend).

The 2026-10-27 E2 read-only audit (docs/E2多模型审计试运行.md) recorded six editor
states whose quantities overflow or collapse during unit conversion.  A run package
must never be generated from them: the writer has to raise ``ValueError`` naming the
offending field instead of writing a main.ini that silently carries an overflowed or
rounded value.

The audit kept these checks in an ignored probe under ``out/verification/``.  This
script is the正式 regression: it runs in the ``static`` test layer, needs neither Qt
nor the backend, and asserts every message fragment that identifies the field.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from g4usim_gui.editors.source_physics_scoring_model import (  # noqa: E402
    PhysicsEditableModel,
    ScoringEditableModel,
    SourceEditableModel,
)
from g4usim_gui.models.package_model import GeometrySettings, RunPackage  # noqa: E402
from g4usim_gui.models.physics_model import PhysicsSettings  # noqa: E402
from g4usim_gui.models.run_model import RunSettings  # noqa: E402
from g4usim_gui.models.scoring_model import ScoringSettings  # noqa: E402
from g4usim_gui.models.source_model import SourceSettings  # noqa: E402
from g4usim_gui.writers.main_ini_writer import build_main_ini_text  # noqa: E402


REJECTION_PREFIX = "Cannot generate main.ini with editor validation errors"


def package(base: Path) -> RunPackage:
    """Run package rooted in a temporary directory (the writer must not create files)."""
    return RunPackage(
        package_dir=str(base),
        config_dir=str(base / "config"),
        macro_dir=str(base / "macros"),
        logs_dir=str(base / "logs"),
        output_dir=str(base / "output"),
        main_ini_path=str(base / "config" / "main.ini"),
        run_macro_path=str(base / "macros" / "run.mac"),
        validation_report_path=str(base / "validation_report.txt"),
        project_snapshot_path=str(base / "project_snapshot.json"),
        materials_ini_path=str(base / "config" / "materials" / "material.ini"),
        geometry_ini_path=str(base / "config" / "geometry" / "geometry.ini"),
    )


def build(base: Path, **overrides):
    return build_main_ini_text(
        package=package(base),
        run=RunSettings(),
        geometry=GeometrySettings(),
        source=SourceSettings(),
        physics=PhysicsSettings(),
        scoring=ScoringSettings(),
        **overrides,
    )


# label -> (editor overrides, message fragments that must identify the field)
REJECTED = (
    (
        "source_energy_conversion_overflow",
        {"source_model": SourceEditableModel(energy="1e308 GeV")},
        ("[source]/energy", "must be a finite energy", "1e308 GeV"),
    ),
    (
        "source_radius_conversion_overflow",
        {"source_model": SourceEditableModel(position_mode="plane", source_shape="circle", radius="1e308 m")},
        ("[source]/radius", "must be a finite length", "1e308 m"),
    ),
    (
        "source_radius_zero",
        {"source_model": SourceEditableModel(position_mode="plane", source_shape="circle", radius="0 mm")},
        ("[source]/radius", "must be > 0"),
    ),
    (
        "physics_cut_conversion_overflow",
        {"physics_model": PhysicsEditableModel(default_cut="1e308 m")},
        ("[physics]/default_cut", "must be a finite length", "1e308 m"),
    ),
    (
        "histogram_reversed",
        {"scoring_model": ScoringEditableModel(hist_min="10 MeV", hist_max="1 MeV")},
        ("histogram max must be greater than min",),
    ),
    (
        "histogram_equal_after_conversion",
        {"scoring_model": ScoringEditableModel(hist_min="1000 keV", hist_max="1 MeV")},
        ("histogram max must be greater than min",),
    ),
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="g4usim-writer-boundary-") as name:
        base = Path(name)

        # Valid control: the baseline editor state must still produce a real main.ini
        # text (guards against a reporter that rejects everything).
        text = build(base)
        assert "[source]" in text, text[:400]
        assert "[physics]" in text, text[:400]
        assert "position_type = point" in text, text[:400]

        # Accepted neighbour: a small non-zero radius must pass, so the overflow
        # checks are not simply rejecting every plane source.
        accepted = build(
            base,
            source_model=SourceEditableModel(position_mode="plane", source_shape="circle", radius="2 mm"),
        )
        assert "radius = 2 mm" in accepted, accepted[:400]

        for label, overrides, fragments in REJECTED:
            try:
                build(base, **overrides)
            except ValueError as exc:
                message = str(exc)
                assert REJECTION_PREFIX in message, f"{label}: {message}"
                for fragment in fragments:
                    assert fragment in message, f"{label}: missing {fragment!r} in {message}"
            else:
                raise AssertionError(f"{label}: writer unexpectedly accepted the editor state")

        # The writer is a pure text builder: generating text must not create any file
        # under the package directory, let alone a half-written main.ini.
        produced = sorted(str(path.relative_to(base)) for path in base.rglob("*") if path.is_file())
        assert produced == [], f"writer created files: {produced}"

    print(f"writer boundary: {len(REJECTED)} rejected states, 2 accepted, no files generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
