#!/usr/bin/env python3
"""Check relative Markdown links (and image paths) inside the repository.

The 2026-10-27 stage-1 audit found documentation that pointed at the wrong
place for months (README claiming unimplemented features, links to state
documents that had been moved). This check is deliberately narrow: it only
verifies that every repository-relative link target exists on disk, so a
moved or renamed document cannot silently rot every reference to it.

Not checked here: anchors inside documents, external URLs, links embedded in
fenced code blocks (examples are not links), or whether the target text is
still accurate.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "data:", "#", "www.")
LINE_SUFFIX_RE = re.compile(r":\d+(-\d+)?$")


def tracked_markdown() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def strip_fenced_blocks(text: str) -> str:
    lines = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            lines.append("")
            continue
        lines.append("" if in_fence else line)
    return "\n".join(lines)


def repo_relative(target: str, root: str) -> str | None:
    """Map an absolute path under the repository root back to a relative path."""
    normalized = target.replace("\\", "/")
    root_slash = root.replace("\\", "/").rstrip("/")
    if len(normalized) > len(root_slash) and normalized.lower().startswith(root_slash.lower() + "/"):
        return normalized[len(root_slash) + 1 :]
    return None


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    files = tracked_markdown()
    assert files, "doc_links: no tracked Markdown files"
    # Behavioural self-checks: a silent regex or fence-handling regression must fail here
    # instead of quietly shrinking the checked-link count.
    assert LINK_RE.findall("[a](x.md) ![b](y.png)") == ["x.md", "y.png"]
    assert strip_fenced_blocks("a\n```\n[b](missing.md)\n```\n").count("missing.md") == 0
    # An unterminated fence runs to end of file (CommonMark), so links after it are
    # intentionally not checked; documented here so the narrowing is explicit.
    assert strip_fenced_blocks("a\n```\n[b](missing.md)\n").count("missing.md") == 0
    assert repo_relative(os.path.join(root, "docs", "a.md"), root) == "docs/a.md"
    assert repo_relative("docs/a.md", root) is None
    assert LINE_SUFFIX_RE.sub("", "src/Core/AppMessenger.cc:99") == "src/Core/AppMessenger.cc"
    broken: list[tuple[str, int, str]] = []
    checked = 0
    for path in files:
        with io.open(path, encoding="utf-8", errors="replace") as handle:
            text = strip_fenced_blocks(handle.read())
        base = os.path.dirname(path)
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in LINK_RE.finditer(line):
                target = match.group(1)
                if target.startswith(SKIP_PREFIXES):
                    continue
                target = target.split("#", 1)[0]
                if not target:
                    continue
                checked += 1
                relative = repo_relative(target, root)
                candidate = relative if relative is not None else target
                resolved = os.path.normpath(os.path.join(base if relative is None else "", candidate))
                if not os.path.exists(resolved):
                    # Documents reference code as `file.cc:123`; accept that form.
                    stripped = LINE_SUFFIX_RE.sub("", candidate)
                    if stripped != candidate:
                        resolved = os.path.normpath(os.path.join(base if relative is None else "", stripped))
                if not os.path.exists(resolved):
                    broken.append((path, lineno, target))
    for path, lineno, target in broken:
        print(f"{path}:{lineno}: broken relative link '{target}'")
    print(f"doc_links: {checked} relative links in {len(files)} files, {len(broken)} broken")
    assert checked > 0, "doc_links: no relative links were found, so the check verified nothing"
    assert not broken, f"doc_links: {len(broken)} broken relative link(s); see the lines above"
    return 0


if __name__ == "__main__":
    sys.exit(main())
