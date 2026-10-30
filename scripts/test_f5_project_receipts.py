"""Project source identity must come from the exact successful IO operation."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core import project as model


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    with tempfile.TemporaryDirectory(prefix="f5-project-receipts-") as directory:
        target = Path(directory) / "项目.json"
        project = model.G4USimProject(projectName="Original")
        receipt = model.save_project(project, target)
        original = target.read_bytes()
        assert receipt.path == str(target.absolute())
        assert receipt.sha256 == digest(original)
        loaded, observed = model.load_project_with_receipt(target)
        assert loaded.projectName == "Original"
        assert observed == receipt
        assert model.load_project(target).projectName == "Original"

        raw_read = Path.read_bytes

        def external_change_after_read(path):
            raw = raw_read(path)
            if path == target:
                path.write_bytes(b'{"external":"changed after read"}')
            return raw

        with patch.object(Path, "read_bytes", external_change_after_read):
            loaded, observed = model.load_project_with_receipt(target)
        assert loaded.projectName == "Original"
        assert observed.sha256 == digest(original)
        assert observed.sha256 != digest(target.read_bytes())

        replace = model.os.replace
        published = []

        def external_change_after_publish(source, destination):
            published.append(Path(source).read_bytes())
            replace(source, destination)
            Path(destination).write_bytes(b'{"external":"changed after publication"}')

        project.projectName = "Saved copy"
        with patch.object(model.os, "replace", external_change_after_publish):
            saved = model.save_project(project, target)
        assert saved.sha256 == digest(published[0])
        assert saved.sha256 != digest(target.read_bytes())
        assert json.loads(published[0])["projectName"] == "Saved copy"
        assert not list(target.parent.glob(".项目.json.*.tmp"))

        unlink = Path.unlink
        cleanup_calls = []

        def reject_postpublication_cleanup(path, *args, **kwargs):
            if path.suffix == ".tmp" and not path.exists():
                cleanup_calls.append(str(path))
                raise OSError("cleanup after publication must not run")
            return unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", reject_postpublication_cleanup):
            committed = model.save_project(project, target)
        assert committed.sha256 == digest(target.read_bytes())
        assert model.load_project(target).projectName == "Saved copy"
        assert cleanup_calls == []
        assert not list(target.parent.glob(".项目.json.*.tmp"))

        unchanged = target.read_bytes()
        for operation, failure in (("dump", model.json), ("replace", model.os)):
            with patch.object(failure, operation, side_effect=OSError("injected write failure")):
                try:
                    model.save_project(project, target)
                except OSError:
                    rejected = True
                else:
                    rejected = False
            assert rejected
            assert target.read_bytes() == unchanged
            assert not list(target.parent.glob(".项目.json.*.tmp"))
    print("F5 exact project read/write receipts and original-file failure protection passed")


if __name__ == "__main__":
    main()
