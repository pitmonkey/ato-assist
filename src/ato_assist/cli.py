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

from .gitops import GitError
from .gitops import commit as git_commit
from .ingest import IngestError
from .ingest import run as ingest_run
from .oscal import CatalogueError
from .oscal import load as load_catalogue
from .repo import find_root_from
from .scaffold import ScaffoldError, Spec, create
from .schema import SCHEMAS
from .status import render as status_render
from .status import summary as status_summary
from .tracking import (
    TrackingError,
    close_rfi,
    export_rfis,
    next_phase,
    open_rfi,
    open_rfis,
    set_phase,
)
from .validate import Finding, schema_for_path, validate_document

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2
    handler = {
        "init": _init,
        "validate": _validate,
        "next-id": _next_id,
        "ingest": _ingest,
        "status": _status,
        "controls": _controls,
        "phase": _phase,
        "rfi": _rfi,
        "commit": _commit,
    }[args.command]
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

    show = sub.add_parser("status", help="where the assessment stands, derived from files")
    show.add_argument("root", nargs="?", default=".")
    show.add_argument("--json", action="store_true", dest="as_json")

    take = sub.add_parser("ingest", help="process inbox/ into sources/")
    take.add_argument("root", nargs="?", default=".")

    cat = sub.add_parser("controls", help="read the framework control catalogue")
    cat.add_argument("control", nargs="?", help="a control ID to show in full")
    cat.add_argument("--search", help="find controls mentioning this text")
    cat.add_argument("--profile", help="controls applying at a classification")
    cat.add_argument("--limit", type=int, default=20)

    move = sub.add_parser("phase", help="move the phase marker (an assessor assertion)")
    move.add_argument("to", help="'next', or the id of a phase in process.yaml")
    move.add_argument("--root", default=".")

    ask = sub.add_parser("rfi", help="register, close, list or export requests for information")
    ask.add_argument("action", choices=("new", "close", "list", "export"))
    ask.add_argument("identifier", nargs="?", help="the RFI to close")
    ask.add_argument("--question")
    ask.add_argument("--asked-of")
    ask.add_argument("--reason", action="append", default=[],
                     help="a claim, control or risk this unblocks")
    ask.add_argument("--source", help="the source that answered it")
    ask.add_argument("--root", default=".")

    save = sub.add_parser("commit", help="commit the assessment with a structured message")
    save.add_argument("--kind", required=True)
    save.add_argument("--summary", required=True)
    save.add_argument("--detail", default="")
    save.add_argument("--root", default=".")

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


def _status(args: argparse.Namespace) -> int:
    root = find_root_from(args.root)
    if root is None:
        print(f"{args.root} is not inside an assessment", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(status_summary(root), indent=2, default=str))
    else:
        print(status_render(root), end="")
    return 0


def _ingest(args: argparse.Namespace) -> int:
    root = find_root_from(args.root)
    if root is None:
        print(f"{args.root} is not inside an assessment", file=sys.stderr)
        return 2
    try:
        report = ingest_run(root)
    except IngestError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not report.ingested and not report.skipped:
        print("Nothing in inbox/ to ingest.")
        return 0
    for source_id in report.ingested:
        change = report.changes.get(source_id)
        detail = (
            f" (revision: {change['added']} added, {change['changed']} changed, "
            f"{change['removed']} removed)"
            if change
            else ""
        )
        print(f"ingested {source_id}{detail}")
    for name in report.skipped:
        print(f"skipped {name} — already ingested, unchanged")
    if report.queued_terms:
        plural = "s" if report.queued_terms != 1 else ""
        print(f"{report.queued_terms} term{plural} queued in glossary/unresolved.md")
    for gap in report.gaps:
        print(f"gap logged: {gap.split('—')[0].strip()}")
    for question in report.questions:
        print(f"question: {question}")
    return 0


_CONTROL_LIST_HEADER = "{count} controls apply at {profile} (ISM {version})"


def _controls(args: argparse.Namespace) -> int:
    """Read the catalogue. Never recite control text from memory — read it from here."""
    try:
        catalogue = load_catalogue()
    except CatalogueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.control:
        control = catalogue.control(args.control)
        if control is None:
            print(f"{args.control} is not in the ISM {catalogue.version} catalogue",
                  file=sys.stderr)
            return 1
        print(f"{control.id}  [{control.topic}]")
        print(f"  {control.statement}")
        print(f"  applies at {', '.join(control.applicability)}", end="")
        print(f"; Essential Eight {', '.join(control.essential_eight)}"
              if control.essential_eight else "")
        return 0

    if args.search:
        hits = catalogue.search(args.search)[: args.limit]
        for control in hits:
            print(f"{control.id}  {control.title}")
        if not hits:
            print(f"nothing in ISM {catalogue.version} mentions {args.search!r}")
        return 0

    if args.profile:
        selected = catalogue.profile(args.profile)
        print(_CONTROL_LIST_HEADER.format(
            count=len(selected), profile=args.profile, version=catalogue.version
        ))
        for control in selected[: args.limit]:
            print(f"{control.id}  {control.title}")
        if len(selected) > args.limit:
            print(f"... and {len(selected) - args.limit} more")
        return 0

    print(f"ISM {catalogue.version}, {len(catalogue.controls)} controls, from "
          f"{catalogue.source} (retrieved {catalogue.retrieved})")
    return 0


def _phase(args: argparse.Namespace) -> int:
    root = find_root_from(args.root)
    if root is None:
        print(f"{args.root} is not inside an assessment", file=sys.stderr)
        return 2
    try:
        moved_from, moved_to = (
            next_phase(root) if args.to == "next" else set_phase(root, args.to)
        )
    except TrackingError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"phase: {moved_from} -> {moved_to}")
    return 0


def _rfi(args: argparse.Namespace) -> int:
    root = find_root_from(args.root)
    if root is None:
        print(f"{args.root} is not inside an assessment", file=sys.stderr)
        return 2

    if args.action == "new":
        if not args.question or not args.asked_of:
            print("--question and --asked-of are both required", file=sys.stderr)
            return 2
        identifier = open_rfi(root, args.question, args.asked_of, resolves=args.reason)
        print(f"{identifier} opened, asked of {args.asked_of}")
        return 0

    if args.action == "close":
        if not args.identifier or not args.source:
            print("closing an RFI needs its id and --source: the answer must be on file "
                  "in sources/, not only in a conversation", file=sys.stderr)
            return 2
        try:
            path = close_rfi(root, args.identifier, args.source)
        except TrackingError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"{args.identifier} closed by {args.source} ({path.name})")
        return 0

    if args.action == "export":
        print(export_rfis(root), end="")
        return 0

    entries = open_rfis(root)
    for data in entries:
        print(f"{data['id']}  {data.get('asked_of', '')}  {data.get('question', '')}")
    if not entries:
        print("No requests for information are open.")
    return 0


def _commit(args: argparse.Namespace) -> int:
    root = find_root_from(args.root)
    if root is None:
        print(f"{args.root} is not inside an assessment", file=sys.stderr)
        return 2
    try:
        made = git_commit(root, args.kind, args.summary, args.detail)
    except GitError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"{args.kind}: {args.summary}" if made else "nothing to commit")
    return 0


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
