#!/usr/bin/env python3
"""Dump an agent session log into a readable Markdown digest.

Two formats are supported, so that the Codex side and this side can read each
other's conversations without copying text by hand:

  DSH (this agent)  $DHS_HOME/sessions/<workspace-key>/<session-id>/session.v4.jsonl.zstd
                    --dsh <file> [--unzstd PATH_TO_ZSTD]

  Codex             ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl
                    --codex <file>

Only conversation text is emitted by default (user messages and assistant
text); reasoning, tool calls and tool results are omitted unless --tools is
given, in which case each tool call becomes a one-line bullet.  The output is
meant for the other agent to read: it is a summary of what was said, not a
replacement for the repository's own records.

Usage examples (Git Bash):
  python -B tools/dump_agent_session.py --dsh ~/.dsh/sessions/<key>/<id>/session.v4.jsonl.zstd \
      --out out/collab/dsh-digest.md
  python -B tools/dump_agent_session.py --codex ~/.codex/sessions/2026/10/27/rollout-*.jsonl \
      --out out/collab/codex-digest.md

Exit codes: 0 success, 2 bad arguments or unreadable input.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _texts(content) -> list[str]:
    if isinstance(content, str):
        return [content]
    out = []
    for item in content or []:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind in ("text", "input_text", "output_text"):
            value = item.get("text")
            if value:
                out.append(value)
    return out


def _fence(text: str) -> list[str]:
    return ["```text", text.rstrip(), "```", ""]


def iter_dsh(path: Path, zstd: str | None):
    if path.suffix == ".zstd":
        binary = zstd or shutil.which("zstd")
        if not binary:
            raise SystemExit(
                "cannot read a .zstd session: pass --unzstd <path to zstd.exe>"
            )
        data = subprocess.run(
            [binary, "-dc", str(path)], check=True, capture_output=True
        ).stdout
        lines = data.decode("utf-8", "replace").splitlines()
    else:
        lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        data = event.get("data") or {}
        if kind == "user/message":
            for text in _texts(data.get("content")):
                yield ("user", text)
        elif kind == "assistant/message":
            message = data.get("message") or {}
            for text in _texts(message.get("content")):
                yield ("assistant", text)
        elif kind == "tool/call":
            yield ("tool", f"{data.get('name')}: {str(data.get('arguments'))[:160]}")


def iter_codex(path: Path):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "response_item":
            continue
        payload = event.get("payload") or {}
        if payload.get("type") != "message":
            continue
        role = payload.get("role")
        if role not in ("user", "assistant"):
            continue
        for text in _texts(payload.get("content")):
            yield (role, text)
        for item in payload.get("content") or []:
            if isinstance(item, dict) and item.get("type") in (
                "function_call",
                "custom_tool_call",
                "local_shell_call",
            ):
                yield ("tool", f"{item.get('name')}: {str(item.get('arguments'))[:160]}")


def render(items, title: str, tools: bool) -> str:
    out = [f"# {title}", ""]
    for role, text in items:
        if role == "tool" and not tools:
            continue
        if role == "user":
            out += ["## 用户", ""] + _fence(text)
        elif role == "assistant":
            out += ["## 助手", ""] + _fence(text)
        else:
            out += [f"- 工具调用 {text}", ""]
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dsh", type=Path, help="session.v4.jsonl[.zstd]")
    source.add_argument("--codex", type=Path, help="rollout-*.jsonl")
    parser.add_argument("--out", type=Path, help="write Markdown here (default stdout)")
    parser.add_argument("--title", default="Agent session digest")
    parser.add_argument("--unzstd", help="zstd executable for --dsh .zstd files")
    parser.add_argument("--tools", action="store_true", help="include tool calls")
    args = parser.parse_args(argv)

    try:
        if args.dsh:
            items = list(iter_dsh(args.dsh, args.unzstd))
        else:
            if not args.codex.is_file():
                print(f"not a file: {args.codex}", file=sys.stderr)
                return 2
            items = list(iter_codex(args.codex))
    except OSError as error:
        print(f"cannot read session: {error}", file=sys.stderr)
        return 2

    markdown = render(items, args.title, args.tools)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8", newline="")
        print(f"wrote {args.out} ({len(markdown)} bytes)")
    else:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
