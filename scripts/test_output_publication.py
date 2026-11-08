"""R2-10 controlled IO faults; no backend or physics claims."""
from __future__ import annotations

from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import merge_outputs, run_output_extension


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="g4usim-publication-") as directory:
        root = Path(directory)
        source = root / "input.csv"
        source.write_text("id,value\n0,1\n", encoding="utf-8")
        payload = {"value": 1, "name": "test"}
        publishers = (
            ("csv", merge_outputs, lambda p: merge_outputs.merge([source], p)),
            ("json", run_output_extension, lambda p: run_output_extension.write_exclusive(p, payload)),
        )
        for kind, module, publish in publishers:
            normal = root / f"normal.{kind}"
            result = publish(normal)
            expected = normal.read_bytes()
            assert result.published and not result.warnings
            assert result.residual_temporary is None
            target = root / f"warning.{kind}"
            diagnostics = io.StringIO()
            with redirect_stderr(diagnostics), patch.object(
                    Path, "unlink", side_effect=PermissionError("injected cleanup denial")):
                result = publish(target)
            assert result.published and len(result.warnings) == 1
            residual = result.residual_temporary
            assert residual is not None and residual.is_file()
            assert target.read_bytes() == residual.read_bytes() == expected
            assert str(residual) in diagnostics.getvalue()
            assert "[PublicationWarning] published:" in diagnostics.getvalue()
            records = [json.loads(line.split(" ", 1)[1]) for line in diagnostics.getvalue().splitlines()
                       if line.startswith("G4USIM_PUBLICATION_RESULT ")]
            assert records == [{"schema": "g4usim_publication_v1", "published": True,
                                "output": str(target), "warnings": list(result.warnings),
                                "residual_temporary": str(residual)}]
            try:
                publish(target)
            except FileExistsError:
                pass
            else:
                raise AssertionError("Retry overwrote published output")
            assert target.read_bytes() == expected
            residual.unlink()
            assert target.read_bytes() == expected  # cleanup never deletes the target

            closed_stderr = io.StringIO()
            closed_stderr.close()
            closed_target = root / f"closed-stderr.{kind}"
            with redirect_stderr(closed_stderr), patch.object(
                    Path, "unlink", side_effect=PermissionError("cleanup")):
                result = publish(closed_target)
            assert result.published and result.warnings
            assert closed_target.read_bytes() == expected
            assert result.residual_temporary is not None
            result.residual_temporary.unlink()
            first_error = OSError("original link error with closed stderr")
            with redirect_stderr(closed_stderr), patch.object(Path, "unlink", side_effect=PermissionError("cleanup")), \
                    patch.object(module.os, "link", side_effect=first_error):
                try:
                    publish(root / f"closed-stderr-link-failed.{kind}")
                except OSError as error:
                    assert error is first_error
                else:
                    raise AssertionError("Original publication failure was lost")
            assert not (root / f"closed-stderr-link-failed.{kind}").exists()
            for path in root.glob(".*.tmp"):
                path.unlink()

            for cleanup_fails in (False, True):
                failed = root / f"link-failed-{cleanup_fails}.{kind}"
                first_error = OSError("injected link failure")
                diagnostics = io.StringIO()
                with redirect_stderr(diagnostics), patch.object(module.os, "link", side_effect=first_error):
                    cleanup = patch.object(Path, "unlink", side_effect=PermissionError("cleanup"))
                    if cleanup_fails:
                        cleanup.start()
                    try:
                        try:
                            publish(failed)
                        except OSError as error:
                            assert error is first_error, "Cleanup replaced the first failure"
                        else:
                            raise AssertionError("Link failure was hidden")
                    finally:
                        if cleanup_fails:
                            cleanup.stop()
                assert not failed.exists()
                leftovers = list(root.glob(".*.tmp"))
                assert bool(leftovers) == cleanup_fails
                if cleanup_fails:
                    assert "not published:" in diagnostics.getvalue()
                    assert str(leftovers[0]) in diagnostics.getvalue()
                for path in leftovers:
                    path.unlink()

            # Failure while writing an already-created temporary file.
            failed = root / f"write-failed.{kind}"
            first_error = OSError("injected write failure")
            if kind == "csv":
                writer = patch.object(module.csv, "writer")
                fake = writer.start()
                fake.return_value.writerow.side_effect = first_error
            else:
                real_fdopen = module.os.fdopen
                class FailingStream:
                    def __init__(self, fd, mode):
                        self.stream = real_fdopen(fd, mode)
                    def __enter__(self):
                        return self
                    def __exit__(self, *args):
                        self.stream.close()
                    def write(self, data):
                        self.stream.write(data[:1])
                        raise first_error
                writer = patch.object(module.os, "fdopen", FailingStream)
                writer.start()
            try:
                with redirect_stderr(io.StringIO()), patch.object(
                        Path, "unlink", side_effect=PermissionError("cleanup")):
                    try:
                        publish(failed)
                    except OSError as error:
                        assert error is first_error
                    else:
                        raise AssertionError("Write failure was hidden")
            finally:
                writer.stop()
            assert not failed.exists()
            leftovers = list(root.glob(".*.tmp"))
            assert len(leftovers) == 1
            leftovers[0].unlink()
            assert not list(root.glob(".*.tmp"))
        assert json.loads((root / "normal.json").read_text(encoding="utf-8")) == payload
    print("test_output_publication: OK (two publishers; controlled IO faults)")


if __name__ == "__main__":
    main()
