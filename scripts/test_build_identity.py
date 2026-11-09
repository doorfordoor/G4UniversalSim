#!/usr/bin/env python3
"""Exercise the production build identity and generated application version."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def invoke(*args, cwd):
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stdout
    return result.stdout.strip()


def write(path, text):
    path.write_bytes(text.encode("utf-8"))


def source_fingerprint(source):
    paths = [source / "main.cc", source / "CMakeLists.txt", source / "include/Core/BuildInfo.hh.in"]
    paths.extend((source / "src").rglob("*.cc"))
    paths.extend((source / "include").rglob("*.hh"))
    paths.extend((source / "cmake").rglob("*.cmake"))
    records = sorted((p.relative_to(source).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
                     for p in paths)
    return hashlib.sha256("".join(f"{name}:{sha}\n" for name, sha in records).encode("utf-8")).hexdigest()


def check_generated_identity(source, version, generator):
    for name in ("cmake", "src", "include/Core", "include/Scoring"):
        (source / name).mkdir(parents=True, exist_ok=True)
    for name in ("cmake/BuildIdentity.cmake", "cmake/BackendTargets.cmake", "include/Core/BuildInfo.hh.in"):
        shutil.copyfile(ROOT / name, source / name)
    write(source / "main.cc", "int main() { return 0; }\n")
    write(source / "src/source.cc", "int value = 1;\r\n")  # hash actual bytes, not normalized text
    header = source / "include/Scoring/HistoryStatistics.hh"
    write(header, "#pragma once\n")
    write(source / "CMakeLists.txt", f"""cmake_minimum_required(VERSION 3.10)
project(identity VERSION {version} LANGUAGES NONE)
include(cmake/BuildIdentity.cmake)
file(GLOB_RECURSE inputs CONFIGURE_DEPENDS "${{PROJECT_SOURCE_DIR}}/src/*.cc"
     "${{PROJECT_SOURCE_DIR}}/include/*.hh" "${{PROJECT_SOURCE_DIR}}/cmake/*.cmake")
list(APPEND inputs "${{PROJECT_SOURCE_DIR}}/main.cc" "${{PROJECT_SOURCE_DIR}}/CMakeLists.txt"
     "${{PROJECT_SOURCE_DIR}}/include/Core/BuildInfo.hh.in")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${{inputs}})
g4usim_capture_source_fingerprint("${{PROJECT_SOURCE_DIR}}" "${{inputs}}" G4USIM_SOURCE_FINGERPRINT)
configure_file(include/Core/BuildInfo.hh.in generated/BuildInfo.hh @ONLY)
""")
    build = source / "build"
    invoke("cmake", "-S", str(source), "-B", str(build), *generator, cwd=source)

    def check_header():
        macros = dict(re.findall(r'^#define (\w+) "([^"\n]*)"$',
                                 (build / "generated/BuildInfo.hh").read_text(encoding="utf-8"), re.M))
        assert macros.get("G4USIM_APPLICATION_VERSION") == version
        expected = source_fingerprint(source)
        assert macros.get("G4USIM_SOURCE_FINGERPRINT") == expected
        return expected

    previous = check_header()
    for path in (header, source / "cmake/BackendTargets.cmake"):
        with path.open("ab") as stream:
            stream.write(b"\n# identity input changed\n")
        invoke("cmake", "--build", str(build), cwd=source)
        current = check_header()
        assert current != previous, path
        previous = current


def main():
    if not __debug__:
        raise SystemExit("Build identity tests require assertions; do not run with -O")
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, help="also check --capabilities on a fresh application executable")
    args = parser.parse_args()
    assert shutil.which("cmake") and shutil.which("git"), "cmake and git are required"
    match = re.search(r"^project\(G4UniversalSim VERSION ([0-9.]+) LANGUAGES CXX\)$",
                      (ROOT / "CMakeLists.txt").read_text(encoding="utf-8"), re.M)
    assert match and match.group(1) == "1.1.0", "AR5 application version must be 1.1.0"
    version = match.group(1)
    with tempfile.TemporaryDirectory(prefix="g4usim-build-identity-") as tmp:
        root = Path(tmp) / "project with spaces"
        root.mkdir()
        shutil.copyfile(ROOT / "cmake/BuildIdentity.cmake", root / "BuildIdentity.cmake")
        write(root / "source.cc", "int value = 1;\n")
        write(root / ".gitignore", "build*/\narchive/\nignored.cc\n")
        write(root / ".gitattributes", "* text eol=lf\n")
        write(root / "identity.in", "@COMMIT@\n@STATE@\n")
        write(root / "CMakeLists.txt", '''cmake_minimum_required(VERSION 3.10)
project(identity NONE)
include("${CMAKE_CURRENT_SOURCE_DIR}/BuildIdentity.cmake")
file(GLOB inputs CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/*.cc")
list(APPEND inputs "${CMAKE_CURRENT_SOURCE_DIR}/BuildIdentity.cmake")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${inputs})
g4usim_capture_build_identity("${CMAKE_CURRENT_SOURCE_DIR}" "${inputs}" COMMIT STATE)
configure_file(identity.in identity.txt @ONLY)
''')
        invoke("git", "init", cwd=root)
        invoke("git", "config", "user.name", "Identity test", cwd=root)
        invoke("git", "config", "user.email", "identity@example.invalid", cwd=root)
        invoke("git", "config", "commit.gpgsign", "false", cwd=root)
        invoke("git", "add", ".", cwd=root)
        invoke("git", "commit", "-m", "fixture", cwd=root)
        head = invoke("git", "rev-parse", "HEAD", cwd=root)
        generator = ["-G", "Ninja"] if shutil.which("ninja") else []

        def configure(source=root, name="build", extra=()):
            invoke("cmake", "-S", str(source), "-B", str(source / name),
                   *generator, *extra, cwd=source)
            return (source / name / "identity.txt").read_text().splitlines()

        def rebuild(source=root):
            invoke("cmake", "--build", str(source / "build"), cwd=source)
            return (source / "build/identity.txt").read_text().splitlines()

        assert configure() == [head, "clean"]
        invoke("git", "update-index", "--assume-unchanged", "source.cc", cwd=root)
        write(root / "source.cc", "int value = 9;\n")
        assert rebuild() == [head, "dirty"], "assume-unchanged cannot hide actual changed input bytes"
        invoke("git", "update-index", "--no-assume-unchanged", "source.cc", cwd=root)
        write(root / "source.cc", "int value = 1;\n")
        write(root / "ignored.cc", "int ignored = 1;\n")
        assert rebuild() == [head, "dirty"], "ignored but compiled input is not clean"
        (root / "ignored.cc").unlink()
        assert rebuild() == [head, "clean"]
        write(root / "source.cc", "int value = 2;\n")
        assert rebuild() == [head, "dirty"], "unstaged input must regenerate identity"
        invoke("git", "add", "source.cc", cwd=root)
        assert rebuild() == [head, "dirty"], "staged input is still dirty"
        invoke("git", "commit", "-m", "source", cwd=root)
        source_head = invoke("git", "rev-parse", "HEAD", cwd=root)
        assert rebuild() == [source_head, "clean"]
        write(root / "README.md", "Documentation only.\n")
        invoke("git", "add", "README.md", cwd=root)
        assert rebuild() == [source_head, "clean"], "unrelated docs do not dirty compiled input"
        invoke("git", "commit", "-m", "docs only", cwd=root)
        docs_head = invoke("git", "rev-parse", "HEAD", cwd=root)
        assert rebuild() == [docs_head, "clean"], "HEAD movement alone must regenerate"
        invoke("git", "pack-refs", "--all", cwd=root)
        assert configure() == [docs_head, "clean"]
        invoke("git", "checkout", "--detach", source_head, cwd=root)
        assert rebuild() == [source_head, "clean"], "detached HEAD must work"
        worktree = Path(tmp) / "linked checkout"
        invoke("git", "worktree", "add", "--detach", str(worktree), docs_head, cwd=root)
        assert configure(worktree) == [docs_head, "clean"], "worktree .git file must work"
        archive = root / "archive"
        archive.mkdir()
        for name in ("source.cc", "BuildIdentity.cmake", "CMakeLists.txt", "identity.in"):
            shutil.copyfile(root / name, archive / name)
        assert configure(archive) == ["unknown", "unknown"], "archive must not inherit parent Git"
        assert configure(name="build-nogit", extra=("-DCMAKE_DISABLE_FIND_PACKAGE_Git=TRUE",)) == ["unknown", "unknown"]
        check_generated_identity(Path(tmp) / "fingerprint fixture", version, generator)
    if args.exe is not None:
        result = subprocess.run([str(args.exe.resolve()), "--capabilities"], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stderr
        caps = json.loads(result.stdout)
        assert caps.get("schema") == "G4UniversalSimCapabilities" and caps.get("version") == 1
        assert caps.get("application_version") == version
        assert caps.get("source_fingerprint") == source_fingerprint(ROOT)
        assert type(caps.get("geant4_version_number")) is int
    print("Build identity: Git transitions, raw-byte fingerprint, generated version and incremental inputs passed")


if __name__ == "__main__":
    main()
