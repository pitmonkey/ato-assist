"""The `ato` command line.

Skills call this rather than reimplementing anything in prose: a skill that computes a
count in its head is a skill that will disagree with the file on disk.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .repo import find_root_from
from .scaffold import ScaffoldError, Spec, create
from .schema import SCHEMAS
from .validate import Finding, schema_for_path, validate_document

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2
    handler = {"init": _init, "validate": _validate, "next-id": _next_id}[args.command]
    return handler(args)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ato", description="ATO assessment workbench.")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="scaffold an assessment repository")
    init.add_argument("root", nargs="?", default=".")
    init.add_argument("--name", required=True)
    init.add_argument("--short-name", required=True)
    init.add_argument("--owner", required=True)
    init.add_argument("--assessor", required=True)
    init.add_argument("--data", required=True, help="classification of the data processed")
    init.add_argument("--environment", required=True, help="classification of the environment")
    init.add_argument("--marking", required=True, help="marking the artefacts carry")
    init.add_argument("--framework", default="ism")
    init.add_argument("--profile", default="PROTECTED")
    init.add_argument("--retain", default="gitignore",
                      choices=("gitignore", "commit", "reference"))

    check = sub.add_parser("validate", help="validate an assessment against the contract")
    check.add_argument("root", nargs="?", default=".")
    check.add_argument("--json", action="store_true", dest="as_json")

    nid = sub.add_parser("next-id", help="the next unused ID in a contract directory")
    nid.add_argument("directory", choices=sorted(SCHEMAS))
    nid.add_argument("--root", default=".")
    return parser


def _init(args: argparse.Namespace) -> int:
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    spec = Spec(
        name=args.name,
        short_name=args.short_name,
        owner=args.owner,
        assessor=args.assessor,
        data=args.data,
        environment=args.environment,
        marking=args.marking,
        framework=args.framework,
        profile=args.profile,
        retain=args.retain,
    )
    try:
        create(root, spec)
    except ScaffoldError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Assessment scaffolded at {root} [{spec.marking}]. Next: /ato-interview.")
    return 0


def _validate(args: argparse.Namespace) -> int:
    root = find_root_from(args.root)
    if root is None:
        print(f"{args.root} is not inside an assessment (no assessment.yaml)", file=sys.stderr)
        return 2

    findings = [
        finding
        for path in sorted(root.rglob("*.md"))
        for finding in _validate_one(root, path)
    ]
    if args.as_json:
        print(json.dumps({"findings": [f._asdict() for f in findings]}, indent=2))
    else:
        for finding in findings:
            where = f" ({finding.field})" if finding.field else ""
            print(f"{finding.code} {finding.path}{where}: {finding.message}")
        print(f"{len(findings)} problems")
    return 1 if any(f.level == "error" for f in findings) else 0


def _validate_one(root: Path, path: Path) -> list[Finding]:
    relative = path.relative_to(root).as_posix()
    if schema_for_path(relative) is None:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [Finding("error", "ATO-E100", relative, None, f"unreadable: {exc}")]
    return validate_document(relative, text)


def _next_id(args: argparse.Namespace) -> int:
    root = find_root_from(args.root)
    if root is None:
        print(f"{args.root} is not inside an assessment", file=sys.stderr)
        return 2
    schema = SCHEMAS[args.directory]
    if schema.prefix is None:
        print(f"{args.directory} uses framework IDs, not generated ones", file=sys.stderr)
        return 2
    pattern = re.compile(rf"^{schema.prefix}-(\d{{4}})")
    highest = max(
        (int(match.group(1))
         for entry in (root / args.directory).glob(f"{schema.prefix}-*")
         if (match := pattern.match(entry.name))),
        default=0,
    )
    print(f"{schema.prefix}-{highest + 1:04d}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through bin/ato
    raise SystemExit(main())
