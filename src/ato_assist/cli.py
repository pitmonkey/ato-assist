"""The `ato` command line.

Skills call this rather than reimplementing anything in prose: a skill that computes a
count in its head is a skill that will disagree with the file on disk.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from . import frontmatter
from .export import ExportError, register_csv, register_xlsx
from .export import report as build_report
from .gitops import GitError
from .gitops import commit as git_commit
from .ingest import ConverterMissing, IngestError
from .ingest import run as ingest_run
from .oscal import PROFILES, CatalogueError, normalise_profile
from .oscal import load as load_catalogue
from .repo import find_root_from
from .risk import MatrixError, rate_all
from .risk import load as load_matrix
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
from .validate import validate_repo

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
        "risk": _risk,
        "export": _export,
        "evidence": _evidence,
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
    take.add_argument("--force", action="store_true",
                      help="accept a conversion that will lose document structure")
    take.add_argument("--reingest", metavar="SRC-NNNN",
                      help="discard a source and read its original again")

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

    rk = sub.add_parser("risk", help="the risk matrix, and risks rated against it")
    rk.add_argument("action", choices=("scales", "list"))
    rk.add_argument("--root", default=".")

    out = sub.add_parser("export", help="regenerate the risk register and report")
    out.add_argument("what", nargs="?", default="all", choices=("all", "register", "report"))
    out.add_argument("--root", default=".")

    evi = sub.add_parser("evidence", help="record an artefact as evidence")
    evi.add_argument("action", choices=("add",))
    evi.add_argument("--file", required=True, help="the artefact itself")
    evi.add_argument("--describe", required=True, help="one line: what it is")
    evi.add_argument("--bears-on", action="append", required=True,
                     help="a claim ID this bears on; repeatable")
    evi.add_argument("--direction", default="supports",
                     choices=("supports", "refutes", "mixed"))
    evi.add_argument("--collected-by", default="assessor")
    evi.add_argument("--root", default=".")

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
    profile = normalise_profile(args.profile)
    if profile is None:
        print(
            f"--profile {args.profile!r} is not a framework profile. Use one of: "
            + ", ".join(PROFILES),
            file=sys.stderr,
        )
        return 2
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
        profile=profile,
        retain=args.retain,
    )
    try:
        create(root, spec)
    except ScaffoldError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    _report_init(root, spec)
    return 0


def _report_init(root: Path, spec: Spec) -> None:
    """Read the settings back. A setting nothing echoes is a setting nobody checks."""
    print(f"Assessment scaffolded at {root}\n")
    for label, value in (
        ("system", f"{spec.name} ({spec.short_name})"),
        ("owner", spec.owner),
        ("assessor", spec.assessor),
        ("data", spec.data),
        ("environment", spec.environment),
        ("marking", spec.marking),
        ("framework", f"{spec.framework} {spec.profile}"),
        ("inbox", f"{spec.retain} ({spec.retention_days} days)"),
    ):
        print(f"  {label:<12} {value}")

    try:
        catalogue = load_catalogue()
        selected = len(catalogue.profile(spec.profile))
        print(f"\n{selected} {spec.framework.upper()} controls apply at {spec.profile} "
              f"({spec.framework.upper()} {catalogue.version}).")
    except CatalogueError as exc:
        print(f"\n! No control catalogue: {exc}")

    print(
        "\n! process.yaml, risk-matrix.yaml and register-columns.yaml are authored "
        "placeholders,\n"
        "  not your organisation's. Validate them with your assessment team before a "
        "register\n"
        "  or report goes anywhere. `ato status` will keep saying so until you do.\n"
        "\nNext: /ato-interview, before ingesting any document."
    )


def _validate(args: argparse.Namespace) -> int:
    root = find_root_from(args.root)
    if root is None:
        print(f"{args.root} is not inside an assessment (no assessment.yaml)", file=sys.stderr)
        return 2

    findings = validate_repo(root)
    if args.as_json:
        print(json.dumps({"findings": [f._asdict() for f in findings]}, indent=2))
    else:
        for finding in findings:
            where = f" ({finding.field})" if finding.field else ""
            mark = "!" if finding.level == "error" else "-"
            print(f"{mark} {finding.code} {finding.path}{where}: {finding.message}")
        errors = sum(1 for finding in findings if finding.level == "error")
        print(f"{len(findings)} problems ({errors} blocking)")
    return 1 if any(f.level == "error" for f in findings) else 0


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
        report = ingest_run(root, force=args.force, reingest=args.reingest)
    except ConverterMissing as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except IngestError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not report.ingested and not report.skipped:
        print("Nothing in inbox/ to ingest.")
        return 0
    for source_id in report.ingested:
        sections = report.sections.get(source_id, 0)
        change = report.changes.get(source_id)
        detail = (
            f", revision: {change['added']} added, {change['changed']} changed, "
            f"{change['removed']} removed"
            if change
            else ""
        )
        print(f"ingested {source_id} — {sections} sections{detail}")
        if source_id in report.unusable:
            print(f"  !! {report.unusable[source_id]}")
            print("     re-ingest with a converter installed: "
                  f"ato ingest --reingest {source_id}")
        for framework in report.frameworks_seen.get(source_id, []):
            print(f"  !  names {framework}, which this assessment is not configured for")
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
        profile = normalise_profile(args.profile)
        if profile is None:
            print(
                f"{args.profile!r} is not a profile in the {catalogue.framework.upper()} "
                f"catalogue. Use one of: " + ", ".join(catalogue.profiles),
                file=sys.stderr,
            )
            return 1
        args.profile = profile
        selected = catalogue.profile(profile)
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


def _risk(args: argparse.Namespace) -> int:
    root = find_root_from(args.root)
    if root is None:
        print(f"{args.root} is not inside an assessment", file=sys.stderr)
        return 2
    try:
        matrix = load_matrix(root)
    except MatrixError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.action == "scales":
        print("likelihood: " + ", ".join(matrix.likelihood))
        print("impact:     " + ", ".join(matrix.impact))
        print("ratings:    " + ", ".join(matrix.severities))
        if matrix.review_required:
            print("\n!  This matrix is the shipped placeholder. It must be replaced with "
                  "the organisation's own scales before a register goes to a board.")
        return 0

    rated = rate_all(root)
    for entry in rated:
        severity = entry.severity or f"unrated — {entry.problem}"
        print(f"{entry.id}  {severity:<10}  {entry.title}")
    if not rated:
        print("No risks have been raised.")
    return 0


def _export(args: argparse.Namespace) -> int:
    root = find_root_from(args.root)
    if root is None:
        print(f"{args.root} is not inside an assessment", file=sys.stderr)
        return 2
    try:
        written = []
        if args.what in ("all", "register"):
            written.append(register_csv(root))
            written.append(register_xlsx(root))
        if args.what in ("all", "report"):
            written.append(build_report(root))
    except ExportError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for path in written:
        print(f"wrote {path.relative_to(root)}")
    return 0


def _evidence(args: argparse.Namespace) -> int:
    """The mechanical half of recording evidence, so an adapter is a one-line call.

    Deliberately labelled `method: ad-hoc`: an artefact recorded by hand, with no adapter
    that understands its format, is exactly what ad-hoc means, and that caps its
    confidence downstream.
    """
    root = find_root_from(args.root)
    if root is None:
        print(f"{args.root} is not inside an assessment", file=sys.stderr)
        return 2
    artifact = Path(args.file)
    if not artifact.is_file():
        print(f"{artifact} is not a readable file", file=sys.stderr)
        return 2

    identifier = _allocate(root, "evidence", "EVD")
    stored = root / "evidence" / "artifacts" / f"{identifier}-{artifact.name}"
    stored.parent.mkdir(parents=True, exist_ok=True)
    if artifact.resolve() != stored.resolve():
        shutil.copy2(artifact, stored)

    today = datetime.date.today()
    data = {
        "id": identifier,
        "title": args.describe,
        "bears_on": list(args.bears_on),
        "direction": args.direction,
        "artifact": [stored.relative_to(root).as_posix()],
        "method": "ad-hoc",
        "collected": today,
        "collected_by": args.collected_by,
        "integrity": f"sha256:{hashlib.sha256(artifact.read_bytes()).hexdigest()}",
        "state": "draft",
        "updated": today,
    }
    body = (
        f"Recorded by hand from `{artifact.name}`.\n\n"
        "No adapter understands this format, so nothing has been read out of it: what it "
        "shows is the assessor's reading, recorded below.\n\n"
        "## Assessor note\n\n"
        "State what this artefact actually demonstrates, and for what scope.\n"
    )
    slug = re.sub(r"[^a-z0-9]+", "-", args.describe.lower()).strip("-")[:40] or "artifact"
    path = root / "evidence" / f"{identifier}-{slug}.md"
    path.write_text(frontmatter.render(data, body), encoding="utf-8")
    print(f"{identifier} recorded from {artifact.name}; say what it shows in {path.name}")
    return 0


def _allocate(root: Path, directory: str, prefix: str) -> str:
    pattern = re.compile(rf"^{prefix}-(\d{{4}})")
    highest = max(
        (int(match.group(1))
         for entry in (root / directory).glob(f"{prefix}-*")
         if (match := pattern.match(entry.name))),
        default=0,
    )
    return f"{prefix}-{highest + 1:04d}"


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
