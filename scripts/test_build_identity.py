#!/usr/bin/env python3
"""Exercise the production CMake identity capture across real Git transitions."""
from pathlib import Path
import os
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


def main():
    assert shutil.which("cmake") and shutil.which("git"), "cmake and git are required"
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
    print("Build identity: staged/unstaged, docs-only, incremental, packed refs, detached, worktree and archive passed")


if __name__ == "__main__":
    main()
