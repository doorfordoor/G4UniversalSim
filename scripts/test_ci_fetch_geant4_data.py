"""Small bootstrap fixtures; no real dataset download or installation."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tarfile
import tempfile
import urllib.request
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))
import ci_fetch_geant4_data as fetcher


class Response(io.BytesIO):
    def __init__(self, payload, url):
        super().__init__(payload)
        self.url = url

    def geturl(self):
        return self.url


class FixtureOpener:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        assert request.full_url == fetcher.BASE_URL + "G4TEST.1.0.tar.gz"
        assert not any(key.lower() in ("authorization", "cookie", "proxy-authorization")
                       for key in request.headers)
        return Response(self.payload, request.full_url)


def archive(entries):
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w:gz", format=tarfile.GNU_FORMAT) as output:
        for name, kind, payload in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.linkname = "../outside" if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) else ""
            member.size = len(payload) if kind in (tarfile.REGTYPE, tarfile.AREGTYPE) else 0
            output.addfile(member, io.BytesIO(payload) if member.isfile() else None)
    return result.getvalue()


def config_text(payload):
    digest = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    return ('set(Geant4_DATASET_DESCRIPTIONS "G4TEST|G4TESTDATA|'
            'D:/verified-sdk/share/Geant4/data/G4TEST1.0|G4TEST.1.0.tar.gz|' + digest + '")\n')


def main():
    good = archive([("G4TEST1.0", tarfile.DIRTYPE, b""),
                    ("G4TEST1.0/sub/value.dat", tarfile.REGTYPE, b"data\n")])
    text = config_text(good)
    parsed = fetcher.parse_config(text)
    assert parsed[0]["folder"] == "G4TEST1.0" and parsed[0]["version"] == "1.0"
    assert parsed[0]["source"] == fetcher.BASE_URL + "G4TEST.1.0.tar.gz"
    for bad in (text.replace("G4TEST.1.0.tar.gz", "../G4TEST.1.0.tar.gz"),
                text.replace("G4TEST1.0|", "G4TEST2.0|"), text + text,
                text.replace(parsed[0]["upstream_md5"], "invalid-md5"),
                text.replace("G4TEST.1.0.tar.gz", "G4TEST.1.tar.gz"),
                text.replace("D:/verified-sdk", "D:/../sdk"),
                text.replace("D:/verified-sdk", "${SDK}"),
                text.replace('")', ';' + text.split('"')[1] + '")')):
        try:
            fetcher.parse_config(bad)
        except ValueError:
            pass
        else:
            assert False, "unsafe/duplicate SDK metadata must reject"
    redirects = fetcher.HTTPSOnlyRedirect()
    request = urllib.request.Request(fetcher.BASE_URL + "G4TEST.1.0.tar.gz")
    for bad_url in ("http://example.com/a", "https://user:secret@example.com/a", "https://example.com/a?token=x"):
        try:
            redirects.redirect_request(request, None, 302, "found", {}, bad_url)
        except ValueError:
            pass
        else:
            assert False, "redirect must reject insecure or credential-bearing URLs"
    with tempfile.TemporaryDirectory(prefix="g4usim-ci-data-test-") as temporary:
        root = Path(temporary)
        config = root / "Geant4Config.cmake"
        config.write_text(text, encoding="utf-8")
        transport = FixtureOpener(good)
        report = fetcher.fetch(config, root / "success", opener=transport)
        item = report["datasets"][0]
        assert report["status"] == "completed" and report["reviewed_artifact"] is False
        assert report["transport"] == "injected_test_transport"
        assert item["status"] == "extracted" and item["download_attempts"] == 1
        assert item["observed_sha256"] == hashlib.sha256(good).hexdigest()
        assert item["observed_size_bytes"] == len(good) and item["file_count"] == 1
        assert (root / "success/data/G4TEST1.0/sub/value.dat").read_bytes() == b"data\n"
        assert len(transport.calls) == 1
        existing = root / "existing"
        existing.mkdir()
        (existing / "sentinel").write_bytes(b"preserve")
        try:
            fetcher.fetch(config, existing, opener=transport)
        except FileExistsError:
            pass
        else:
            assert False, "existing destination must never be overwritten"
        assert (existing / "sentinel").read_bytes() == b"preserve" and len(transport.calls) == 1
        real_parent, alias_parent = root / "real-parent", root / "linked-parent"
        real_parent.mkdir()
        (real_parent / "Geant4Config.cmake").write_text(text, encoding="utf-8")
        if os.name == 'nt':
            linked = subprocess.run([os.environ.get('COMSPEC', 'cmd.exe'), '/c', 'mklink', '/J',
                                     str(alias_parent), str(real_parent)], capture_output=True, text=True, timeout=15)
            assert linked.returncode == 0, (linked.stdout, linked.stderr)
        else:
            alias_parent.symlink_to(real_parent, target_is_directory=True)
        no_network = FixtureOpener(good)
        for selected_config, selected_destination in ((config, alias_parent / 'new-data'),
                                                       (alias_parent / 'Geant4Config.cmake', root / 'linked-config')):
            try:
                fetcher.fetch(selected_config, selected_destination, opener=no_network)
            except ValueError as error:
                assert 'Linked/reparse' in str(error)
            else:
                assert False, 'Linked ancestors must reject before download/extraction'
        assert not (real_parent / 'new-data').exists() and no_network.calls == []
        assert (real_parent / 'Geant4Config.cmake').read_text(encoding='utf-8') == text
        config.write_text(text.replace(parsed[0]["upstream_md5"], "0" * 32), encoding="utf-8")
        try:
            fetcher.fetch(config, root / "md5-failure", opener=transport)
        except ValueError as error:
            assert "MD5" in str(error)
        else:
            assert False, "upstream MD5 mismatch must stop before extraction"
        failed = json.loads((root / "md5-failure/fetch-report.json").read_text())
        assert failed["status"] == "failed" and failed["datasets"][0]["status"] == "failed"
        assert failed["datasets"][0]["observed_sha256"] == hashlib.sha256(good).hexdigest()
        assert (root / "md5-failure/archives/G4TEST.1.0.tar.gz").read_bytes() == good
        assert not list((root / "md5-failure/data").iterdir())
        for label, attributes, accepted in (("pax", {"mtime": "1.25"}, True),
                                             ("pax-sparse", {"GNU.sparse.map": "0,1", "GNU.sparse.size": "1"}, False),
                                             ("pax-limit", {"comment": "x" * 70000}, False)):
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode="w:gz", format=tarfile.PAX_FORMAT) as output:
                member = tarfile.TarInfo("G4TEST1.0/value")
                member.size = 1
                member.pax_headers = attributes
                output.addfile(member, io.BytesIO(b"x"))
            payload = stream.getvalue()
            config.write_text(config_text(payload), encoding="utf-8")
            try:
                result = fetcher.fetch(config, root / label, opener=FixtureOpener(payload))
            except ValueError:
                assert accepted is False
            else:
                assert accepted is True and result["status"] == "completed", (label, result["status"])
        unreachable = FixtureOpener(good)
        with patch.object(unreachable, "open", side_effect=OSError("fixture connection failure")) as attempted:
            config.write_text(text, encoding="utf-8")
            try:
                fetcher.fetch(config, root / "network-failure", opener=unreachable)
            except OSError:
                pass
            else:
                assert False, "transport failure must propagate without retry"
            assert attempted.call_count == 1
        failed = json.loads((root / "network-failure/fetch-report.json").read_text())
        assert failed["status"] == "failed" and failed["datasets"][0]["archive_created"] is False
        assert "observed_sha256" not in failed["datasets"][0]

        entries = [
            [("../escape", tarfile.REGTYPE, b"x")],
            [("/absolute", tarfile.REGTYPE, b"x")],
            [("G4TEST1.0/../escape", tarfile.REGTYPE, b"x")],
            [("G4TEST1.0\\escape", tarfile.REGTYPE, b"x")],
            [("wrong1.0/file", tarfile.REGTYPE, b"x")],
            [("G4TEST1.0/link", tarfile.SYMTYPE, b"")],
            [("G4TEST1.0/link", tarfile.LNKTYPE, b"")],
            [("G4TEST1.0/device", tarfile.CHRTYPE, b"")],
            [("G4TEST1.0/fifo", tarfile.FIFOTYPE, b"")],
            [("G4TEST1.0/A/x", tarfile.REGTYPE, b"first"), ("G4TEST1.0/a/y", tarfile.REGTYPE, b"second")],
            [("G4TEST1.0/x", tarfile.REGTYPE, b"first"), ("G4TEST1.0/x", tarfile.REGTYPE, b"second")],
            [("G4TEST1.0/x", tarfile.REGTYPE, b"first"), ("G4TEST1.0/x/y", tarfile.REGTYPE, b"second")],
            [("G4TEST1.0/CON.txt", tarfile.REGTYPE, b"x")],
        ]
        for index, contents in enumerate(entries):
            payload = archive(contents)
            config.write_text(config_text(payload), encoding="utf-8")
            destination = root / f"bad-tar-{index}"
            try:
                fetcher.fetch(config, destination, opener=FixtureOpener(payload))
            except ValueError:
                pass
            else:
                assert False, f"unsafe tar fixture accepted: {index}"
            assert json.loads((destination / "fetch-report.json").read_text())["status"] == "failed"
            assert not (root / "escape").exists()
            if index == 10:
                assert (destination / "data/G4TEST1.0/x").read_bytes() == b"first"
        for label, limits in (("archive", replace(fetcher.Limits(), archive_bytes=1)),
                              ("archive-total", replace(fetcher.Limits(), total_archive_bytes=1)),
                              ("file", replace(fetcher.Limits(), file_bytes=1)),
                              ("total", replace(fetcher.Limits(), extracted_bytes=1)),
                              ("members", replace(fetcher.Limits(), members=1))):
            config.write_text(text, encoding="utf-8")
            destination = root / ("limit-" + label)
            try:
                fetcher.fetch(config, destination, opener=FixtureOpener(good), limits=limits)
            except ValueError:
                pass
            else:
                assert False, "limit must reject: " + label
            receipt = json.loads((destination / "fetch-report.json").read_text())
            assert receipt["status"] == "failed"
            if label in ("archive", "archive-total"):
                archive_path = destination / "archives/G4TEST.1.0.tar.gz"
                assert receipt["datasets"][0]["observed_size_bytes"] == archive_path.stat().st_size == 0
    print("CI dataset bootstrap: strict SDK metadata, fixture hashes, HTTPS redirects, owned paths and tar limits passed")


if __name__ == "__main__":
    main()
