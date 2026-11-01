"""Bootstrap official Geant4 datasets from an already verified SDK's metadata.

SDK MD5 values are upstream legacy integrity checks, not source authentication.
The observed SHA-256/size receipts are inputs for a later artifact review/build;
this helper never calls a downloaded archive a reviewed installation artifact.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tarfile
import urllib.parse
import urllib.request
from uuid import uuid4

BASE_URL = "https://geant4-data.web.cern.ch/datasets/"
CHUNK = 1024 * 1024


@dataclass(frozen=True)
class Limits:
    archive_bytes: int = 4 * 1024**3
    total_archive_bytes: int = 16 * 1024**3
    file_bytes: int = 1024**3
    extracted_bytes: int = 32 * 1024**3
    members: int = 1_000_000


def no_links(path: Path) -> None:
    for candidate in (path.absolute(), *path.absolute().parents):
        try:
            facts = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(facts.st_mode) or getattr(facts, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Linked/reparse paths are not accepted: {candidate}")


def parse_config(text: str) -> list[dict]:
    assignments = re.findall(r'(?im)^\s*set\s*\(\s*Geant4_DATASET_DESCRIPTIONS\s+"([^"\r\n]*)"\s*\)', text)
    declarations = re.findall(r'(?im)^\s*set\s*\(\s*Geant4_DATASET_DESCRIPTIONS\b', text)
    if len(assignments) != 1 or len(declarations) != 1:
        raise ValueError("Exactly one literal Geant4_DATASET_DESCRIPTIONS assignment is required")
    rows = assignments[0].split(";")
    if not 1 <= len(rows) <= 32:
        raise ValueError("Unexpected number of SDK datasets")
    result, used = [], {key: set() for key in ("name", "environment", "folder", "archive")}
    for row in rows:
        fields = row.split("|")
        if len(fields) != 5 or any(field != field.strip() or not field for field in fields):
            raise ValueError("Dataset rows must contain five nonempty literal fields")
        name, environment, declared_path, archive, legacy_md5 = fields
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", name) or not re.fullmatch(r"[A-Z][A-Z0-9_]*DATA", environment):
            raise ValueError("Invalid dataset name or environment-variable name")
        path = declared_path.replace("\\", "/")
        if (not (path.startswith("/") or re.match(r"^[A-Za-z]:/", path)) or path.endswith("/")
                or any(piece in (".", "..", "") for piece in path.split("/")[1:])
                or any(char in declared_path for char in '$;\r\n\x00')):
            raise ValueError("Invalid SDK dataset path")
        prefixes = [name] + ([] if name.startswith("G4") else ["G4" + name])
        match = re.fullmatch(r"(" + "|".join(re.escape(prefix) for prefix in prefixes) +
                             r")\.((?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*)){1,3})\.tar\.gz", archive)
        if match is None or not re.fullmatch(r"[0-9a-fA-F]{32}", legacy_md5):
            raise ValueError("Invalid archive basename/version or SDK legacy MD5")
        version = match.group(2)
        folder = path.rsplit("/", 1)[-1]
        if folder != name + version:
            raise ValueError("SDK folder and archive dataset/version do not agree")
        item = dict(name=name, environment=environment, version=version, folder=folder,
                    declared_sdk_path=declared_path, archive=archive, upstream_md5=legacy_md5.lower(),
                    source=BASE_URL + archive)
        for key, names in used.items():
            folded = item[key].casefold()
            if folded in names:
                raise ValueError("Duplicate or case-conflicting SDK dataset metadata")
            names.add(folded)
        result.append(item)
    return result


def safe_https(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or any(ord(char) < 33 or char == "\\" for char in url)):
        raise ValueError("Only plain credential-free HTTPS URLs are accepted")
    return url


class HTTPSOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        target = safe_https(urllib.parse.urljoin(request.full_url, newurl))
        return super().redirect_request(request, fp, code, msg, headers, target)


def _write_report(root: Path, report: dict) -> None:
    target = root / "fetch-report.json"
    no_links(target)
    temporary = root / ("fetch-report-" + uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, target)  # Only this transaction's own report is updated.


def _download(item: dict, target: Path, opener, limits: Limits, totals: dict) -> None:
    md5, sha256, count, created = hashlib.md5(usedforsecurity=False), hashlib.sha256(), 0, False
    item.update(status="downloading", download_attempts=1, archive_path=str(target))
    request = urllib.request.Request(safe_https(item["source"]),
                                     headers={"User-Agent": "G4UniversalSim-CI-data-bootstrap"})
    try:
        with opener.open(request, timeout=30) as response, target.open("xb") as output:
            created = True
            item["resolved_source"] = safe_https(response.geturl())
            while block := response.read(CHUNK):
                if count + len(block) > limits.archive_bytes or totals["archive_bytes"] + len(block) > limits.total_archive_bytes:
                    raise ValueError("Dataset download exceeds byte limits")
                output.write(block)
                count += len(block)
                totals["archive_bytes"] += len(block)
                md5.update(block)
                sha256.update(block)
            output.flush()
            os.fsync(output.fileno())
    finally:
        item["archive_created"] = created
        if created:
            item.update(observed_size_bytes=count, observed_md5=md5.hexdigest(), observed_sha256=sha256.hexdigest())
    item["status"] = "verifying_upstream_md5"
    if item["observed_md5"] != item["upstream_md5"]:
        raise ValueError("Dataset failed upstream legacy MD5 verification")
    item["status"] = "downloaded_md5_verified"


def _member_parts(name: str) -> tuple[str, ...]:
    if name.endswith("/"):
        name = name[:-1]
    parts = name.split("/")
    if (not name or len(name) > 1024 or "\\" in name or any(ord(c) < 32 for c in name)
            or any(not part or part in (".", "..") or part.endswith((".", " "))
                   or re.search(r'[<>:"|?*]', part)
                   or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
                   for part in parts)):
        raise ValueError(f"Unsafe tar member path: {name!r}")
    return tuple(parts)


class OrdinaryTarInfo(tarfile.TarInfo):
    def _proc_member(self, bundle):
        # Both older fromtarfile/frombuf and newer _fromtarfile/_frombuf routes
        # dispatch here before processing an extended header or sparse map.
        metadata = (tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.SOLARIS_XHDTYPE,
                    tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK)
        if self.type in metadata:
            if self.size < 0 or self.size > 64 * 1024:
                raise ValueError("Tar extended metadata exceeds the per-header limit")
        elif self.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE):
            raise ValueError("Only ordinary tar files/directories are accepted; no links or special entries")
        return super()._proc_member(bundle)

    def _account_metadata(self, bundle):
        total = getattr(bundle, '_ci_metadata_bytes', 0) + self.size
        if total > 64 * 1024**2:
            raise ValueError("Tar extended metadata exceeds the archive limit")
        bundle._ci_metadata_bytes = total

    def _proc_pax(self, bundle):
        self._account_metadata(bundle)
        return super()._proc_pax(bundle)

    def _proc_gnulong(self, bundle):
        self._account_metadata(bundle)
        return super()._proc_gnulong(bundle)

    def _reject_sparse(self, *args):
        raise ValueError("Sparse tar files are not accepted")

    _proc_gnusparse_00 = _reject_sparse
    _proc_gnusparse_01 = _reject_sparse
    _proc_gnusparse_10 = _reject_sparse


def _stream_members(bundle):
    while (member := bundle.next()) is not None:
        yield member
        # TarFile normally retains every TarInfo/pax dictionary even in stream
        # mode. The collision table below is sufficient; don't retain payload metadata.
        bundle.members.clear()


def extract_archive(archive: Path, data: Path, folder: str, limits: Limits, totals: dict) -> dict:
    nodes, files, count = {}, 0, 0
    with tarfile.open(archive, "r|gz", tarinfo=OrdinaryTarInfo) as bundle:
        for member in _stream_members(bundle):
            totals["members"] += 1
            if totals["members"] > limits.members:
                raise ValueError("Dataset tar exceeds member-count limit")
            parts = _member_parts(member.name)
            if parts[0] != folder:
                raise ValueError("Tar top-level folder differs from SDK canonical folder")
            if len(parts) == 1 and not member.isdir():
                raise ValueError("The canonical top-level member must be a directory")
            if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE) or member.issparse():
                raise ValueError("Only ordinary tar files and directories are accepted")
            if member.size < 0 or member.size > limits.file_bytes or member.isdir() and member.size != 0:
                raise ValueError("Tar member exceeds size limit or has invalid directory data")
            for index in range(1, len(parts) + 1):
                path = "/".join(parts[:index])
                key, leaf = path.casefold(), index == len(parts)
                kind = "file" if leaf and member.isfile() else "directory"
                old = nodes.get(key)
                if old is not None:
                    if old[0] != path or old[1] != kind or leaf and old[2]:
                        raise ValueError("Duplicate, case-conflicting or file/directory tar paths")
                nodes[key] = (path, kind, leaf or (old[2] if old else False))
            destination = data.joinpath(*parts)
            no_links(destination)
            if not destination.resolve().is_relative_to(data.resolve()):
                raise ValueError("Tar member escaped the owned data directory")
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if totals["extracted_bytes"] + member.size > limits.extracted_bytes:
                raise ValueError("Dataset tar exceeds total extracted-byte limit")
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                raise ValueError("Tar file has no regular payload")
            written = 0
            with source, destination.open("xb") as output:
                while block := source.read(CHUNK):
                    written += len(block)
                    if written > member.size:
                        raise ValueError("Tar file exceeds declared member size")
                    output.write(block)
                    totals["extracted_bytes"] += len(block)
            if written != member.size:
                raise ValueError("Truncated tar file")
            files += 1
            count += written
    if not files or not (data / folder).is_dir():
        raise ValueError("Dataset archive did not contain a nonempty canonical folder")
    return {"file_count": files, "extracted_size_bytes": count}


def fetch(config: Path, directory: Path, *, opener=None, limits: Limits = Limits()) -> dict:
    config, directory = config.absolute(), directory.absolute()
    no_links(directory)
    directory.mkdir(parents=True, exist_ok=False)
    report = {"schema": "g4usim_ci_geant4_data_fetch_v1", "status": "running", "reviewed_artifact": False,
              "transport": "injected_test_transport" if opener is not None else "https",
              "sdk_config": {"path": str(config), "sdk_archive_verification": "caller responsibility; not performed here"},
              "md5_role": "upstream legacy integrity check; not source authentication",
              "datasets": []}
    active_item = None
    totals = dict(archive_bytes=0, extracted_bytes=0, members=0)
    report["totals"] = totals
    try:
        _write_report(directory, report)
        no_links(config)
        if config.name != "Geant4Config.cmake" or not config.is_file() or config.stat().st_size > 2 * 1024**2:
            raise ValueError("Expected a bounded Geant4Config.cmake from the verified SDK")
        raw = config.read_bytes()
        report["sdk_config"].update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        report["datasets"] = parse_config(raw.decode("utf-8-sig"))
        for item in report["datasets"]:
            item["status"] = "planned"
        archives, data = directory / "archives", directory / "data"
        archives.mkdir()
        data.mkdir()
        if opener is None:
            # No cookies, credentials, authentication handlers or inherited
            # secret-bearing proxy settings; TLS uses Python's verified defaults.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), HTTPSOnlyRedirect())
        for item in report["datasets"]:
            active_item = item
            item["status"] = "planned"
            _write_report(directory, report)
            archive = archives / item["archive"]
            _download(item, archive, opener, limits, totals)
            item["status"] = "extracting"
            _write_report(directory, report)
            item.update(extract_archive(archive, data, item["folder"], limits, totals))
            item["status"] = "extracted"
            _write_report(directory, report)
        report.update(status="completed", totals=totals, data_directory=str(data))
        _write_report(directory, report)
        return report
    except Exception as error:
        if active_item is not None:
            active_item.update(failure_stage=active_item["status"], status="failed")
        report.update(status="failed", error={"type": type(error).__name__, "message": str(error)})
        _write_report(directory, report)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = fetch(args.config, args.directory)
    except Exception as error:
        print(f"Data bootstrap failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"Fetched {len(result['datasets'])} datasets; receipt: {args.directory / 'fetch-report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
