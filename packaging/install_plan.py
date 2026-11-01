"""Offline install planning and explicit user-prefix installation CLI.

Run with --help. A plan never executes installation or connects to a server.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.environment_install import (  # noqa: E402
    InstallError, create_plan, execute_plan, load_catalog, recover_installation,
    uninstall_installation, verify_installation, probe_sdk, inspect_transaction,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", help="Explicit new JSON output file; otherwise print JSON")
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan", help="Read-only offline planning")
    plan_parser.add_argument("--catalog", required=True)
    plan_parser.add_argument("--profile", choices=("runtime", "sdk"), required=True)
    plan_parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    plan_parser.add_argument("--architecture", choices=("x86_64", "aarch64"), required=True)
    plan_parser.add_argument("--version", required=True)
    plan_parser.add_argument("--prefix", required=True)
    plan_parser.add_argument("--allowed-root", required=True)
    plan_parser.add_argument("--facts", help="Optional existing I1 JSON snapshot (not refreshed during planning)")
    install_parser = commands.add_parser("execute", help="Execute an explicit previously saved plan")
    install_parser.add_argument("--plan", required=True)
    install_parser.add_argument("--allow-download", action="store_true")
    install_parser.add_argument("--resume", action="store_true")
    for name in ("verify", "uninstall"):
        commands.add_parser(name).add_argument("--prefix", required=True)
    recover_parser = commands.add_parser("recover", help="Discard an owned failed transaction, preserving any committed prefix")
    recover_parser.add_argument("--prefix", required=True)
    recover_parser.add_argument("--allowed-root", required=True)
    recover_parser.add_argument("--action", choices=("discard", "uninstall"), default="discard")
    recover_parser.add_argument("--transaction-id")
    inspect_parser = commands.add_parser("inspect", help="Read the stored validated plan without resuming or discarding")
    inspect_parser.add_argument("--prefix", required=True)
    inspect_parser.add_argument("--allowed-root", required=True)
    sdk_parser = commands.add_parser("probe-sdk", help="Configure, compile and run a bundled Geant4 consumer")
    sdk_parser.add_argument("--prefix", required=True)
    sdk_parser.add_argument("--build-directory", required=True)
    sdk_parser.add_argument("--cmake", required=True)
    sdk_parser.add_argument("--generator")
    sdk_parser.add_argument("--compiler")
    sdk_parser.add_argument("--kind", choices=("consumer", "application"), default="consumer")
    sdk_parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            result = create_plan(load_catalog(args.catalog), profile=args.profile, platform=args.platform,
                                 architecture=args.architecture, version=args.version, prefix=args.prefix,
                                 allowed_root=args.allowed_root, facts=load_catalog(args.facts) if args.facts else None)
        elif args.command == "execute":
            result = execute_plan(load_catalog(args.plan), allow_download=args.allow_download, resume=args.resume)
        elif args.command == "verify":
            result = verify_installation(args.prefix)
        elif args.command == "uninstall":
            result = uninstall_installation(args.prefix)
        elif args.command == "probe-sdk":
            result = probe_sdk(args.prefix, build_directory=args.build_directory, cmake=args.cmake,
                               generator=args.generator, compiler=args.compiler, kind=args.kind, timeout=args.timeout)
        elif args.command == "inspect":
            result = dict(inspect_transaction(args.prefix, allowed_root=args.allowed_root), status="inspected")
        else:
            result = recover_installation(args.prefix, allowed_root=args.allowed_root,
                                          action=args.action, transaction_id=args.transaction_id)
    except (InstallError, OSError, ValueError) as exc:
        result = {"status": "failed", "diagnostics": [{"code": getattr(exc, "code", "invalid_input"), "message": str(exc)}]}
    raw = json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False) + "\n"
    if args.output:
        # Never replace a previously saved plan or evidence file.
        from g4usim_gui.core.environment_install import _no_links
        output = Path(args.output)
        _no_links(output)
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(raw)
    else:
        print(raw, end="")
    return 0 if result.get("status") in ("planned", "published", "published_with_warning", "verified", "uninstalled", "recovered", "inspected") else 2


if __name__ == "__main__":
    raise SystemExit(main())
