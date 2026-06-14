"""Command-line interface for dealroom."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import (
    DEAL_TYPES,
    DataroomError,
    ScanResult,
    SEVERITY_ORDER,
    build_checklist,
    checklist_to_dict,
    scan_dataroom,
    to_html,
)

_SEV_LABEL = {
    "critical": "CRIT",
    "high": "HIGH",
    "medium": "MED ",
    "low": "LOW ",
    "info": "INFO",
}


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _render_checklist_table(deal_type: str) -> str:
    items = build_checklist(deal_type)
    lines: List[str] = []
    lines.append(f"dealroom checklist — deal type: {deal_type.lower()}")
    lines.append("=" * 68)
    last_cat = None
    for it in items:
        if it.category != last_cat:
            lines.append(f"\n[{it.category}]")
            last_cat = it.category
        req = "REQUIRED" if it.required else "optional"
        lines.append(f"  - {it.label}  ({req})")
        lines.append(f"      id={it.id}  hints: {', '.join(it.hints)}")
    req_n = sum(1 for i in items if i.required)
    lines.append("-" * 68)
    lines.append(f"{len(items)} items ({req_n} required). "
                 f"Lay your dataroom out using the hints, then run "
                 f"`{TOOL_NAME} scan <dir> --deal-type {deal_type.lower()}`.")
    return "\n".join(lines)


def _render_scan_table(result: ScanResult) -> str:
    lines: List[str] = []
    lines.append(f"dealroom scan — {result.deal_type} — {result.root}")
    lines.append("=" * 68)

    lines.append("CHECKLIST STATUS")
    for it in result.items:
        present = bool(result.coverage.get(it.id))
        if present:
            mark = "[x]"
        elif it.required:
            mark = "[!]"
        else:
            mark = "[ ]"
        req = "req" if it.required else "opt"
        lines.append(f"  {mark} ({req}) {it.label}")
        if present:
            lines.append(f"        -> {', '.join(result.coverage[it.id])}")

    lines.append("")
    lines.append("RISKS")
    if not result.risks:
        lines.append("  none detected")
    else:
        for r in result.risks:
            label = _SEV_LABEL.get(r.severity, r.severity.upper())
            lines.append(f"  [{label}] {r.rule} — {r.message}")
            if r.location:
                lines.append(f"          at: {r.location}")
            if r.snippet:
                lines.append(f"          > {r.snippet}")

    rc = result.risk_counts
    lines.append("-" * 68)
    lines.append(
        f"completion={result.completion_pct}%  "
        f"present={len(result.present_items)}/{len(result.items)}  "
        f"missing_required={len(result.missing_required)}  "
        f"files={len(result.files)}")
    lines.append(
        f"risks: critical={rc['critical']} high={rc['high']} "
        f"medium={rc['medium']} low={rc['low']}")
    if result.missing_required:
        lines.append("MISSING REQUIRED: "
                     + ", ".join(i.id for i in result.missing_required))
    lines.append("RESULT: " + ("FAIL" if result.failed else "PASS"))
    return "\n".join(lines)


def _render_report_table(result: ScanResult) -> str:
    """A condensed status + risk summary (the `report` view)."""
    rc = result.risk_counts
    lines: List[str] = []
    lines.append(f"dealroom report — {result.deal_type}")
    lines.append("=" * 68)
    lines.append(f"Completion : {result.completion_pct}% "
                 f"({len(result.present_items)}/{len(result.items)} items)")
    lines.append(f"Files      : {len(result.files)} inventoried")
    lines.append(f"Risks      : {len(result.risks)} "
                 f"(crit={rc['critical']} high={rc['high']} "
                 f"med={rc['medium']} low={rc['low']})")
    lines.append("")
    if result.missing_required:
        lines.append("MISSING REQUIRED ITEMS:")
        for it in result.missing_required:
            lines.append(f"  [!] {it.category}: {it.label} (id={it.id})")
    else:
        lines.append("All required checklist items are present.")
    lines.append("")
    top = [r for r in result.risks if r.severity in ("critical", "high")]
    if top:
        lines.append("TOP RISKS (critical / high):")
        for r in top:
            label = _SEV_LABEL.get(r.severity, r.severity.upper())
            lines.append(f"  [{label}] {r.rule} @ {r.location}")
            lines.append(f"          {r.message}")
    else:
        lines.append("No critical or high risks detected.")
    lines.append("-" * 68)
    lines.append("RESULT: " + ("FAIL" if result.failed else "PASS"))
    return "\n".join(lines)


def _emit(text: str, out: Optional[str]) -> None:
    if out:
        try:
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(text if text.endswith("\n") else text + "\n")
        except OSError as exc:
            raise DataroomError(f"cannot write output file {out!r}: {exc}") from exc
        print(f"wrote {out}", file=sys.stderr)
    else:
        print(text)


# --------------------------------------------------------------------------- #
# Argument parser
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="M&A / VC due-diligence assistant — generate a dataroom "
                    "checklist, track items, and flag risks in local documents.")
    p.add_argument("--version", action="version",
                   version=f"{TOOL_NAME} {TOOL_VERSION}")
    sub = p.add_subparsers(dest="command")

    # init: scaffold a checklist by deal type.
    init = sub.add_parser(
        "init", help="Scaffold a structured diligence checklist by deal type.")
    init.add_argument("--deal-type", choices=DEAL_TYPES, default="saas",
                      help="Deal type to scaffold (default: saas).")
    init.add_argument("--format", choices=("table", "json"), default="table",
                      help="Output format (default: table).")
    init.add_argument("--out", help="Write output to this file instead of stdout.")

    # scan: inventory a dataroom directory.
    sc = sub.add_parser(
        "scan", help="Scan a local dataroom folder; map files + flag risks.")
    sc.add_argument("directory", help="Path to the dataroom directory.")
    sc.add_argument("--deal-type", choices=DEAL_TYPES, default="saas",
                    help="Deal type checklist to apply (default: saas).")
    sc.add_argument("--format", choices=("table", "json", "html"),
                    default="table", help="Output format (default: table).")
    sc.add_argument("--out", help="Write output to this file instead of stdout.")
    sc.add_argument("--fail-on", choices=tuple(SEVERITY_ORDER), default=None,
                    help="Exit non-zero if a risk at/above this severity exists.")

    # report: status + risk summary (condensed scan view).
    rep = sub.add_parser(
        "report", help="Scan then print a condensed status + risk summary.")
    rep.add_argument("directory", help="Path to the dataroom directory.")
    rep.add_argument("--deal-type", choices=DEAL_TYPES, default="saas",
                     help="Deal type checklist to apply (default: saas).")
    rep.add_argument("--format", choices=("table", "json", "html"),
                     default="table", help="Output format (default: table).")
    rep.add_argument("--out", help="Write output to this file instead of stdout.")
    rep.add_argument("--fail-on", choices=tuple(SEVERITY_ORDER), default=None,
                     help="Exit non-zero if a risk at/above this severity exists.")

    # mcp: expose over stdio.
    mcp = sub.add_parser("mcp", help="Run as an MCP server (stdio JSON-RPC).")
    mcp.add_argument("--host", default=None, help="Reserved; stdio transport only.")
    return p


def _gate(result: ScanResult, fail_on: Optional[str]) -> bool:
    """Whether to exit non-zero."""
    if fail_on:
        threshold = SEVERITY_ORDER[fail_on]
        return any(SEVERITY_ORDER.get(r.severity, 99) <= threshold
                   for r in result.risks)
    return result.failed


# --------------------------------------------------------------------------- #
# Subcommand runners
# --------------------------------------------------------------------------- #
def _run_init(args: argparse.Namespace) -> int:
    try:
        if args.format == "json":
            text = json.dumps(checklist_to_dict(args.deal_type), indent=2)
        else:
            text = _render_checklist_table(args.deal_type)
        _emit(text, args.out)
    except DataroomError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def _run_scan(args: argparse.Namespace, condensed: bool) -> int:
    try:
        result = scan_dataroom(args.directory, args.deal_type)
    except DataroomError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        fmt = args.format
        if fmt == "json":
            _emit(json.dumps(result.to_dict(), indent=2), args.out)
        elif fmt == "html":
            _emit(to_html(result), args.out)
        elif condensed:
            _emit(_render_report_table(result), args.out)
        else:
            _emit(_render_scan_table(result), args.out)
    except DataroomError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return 1 if _gate(result, args.fail_on) else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return _run_init(args)
        if args.command == "scan":
            return _run_scan(args, condensed=False)
        if args.command == "report":
            return _run_scan(args, condensed=True)
        if args.command == "mcp":
            from .mcp_server import run_mcp_server
            run_mcp_server()
            return 0
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive last resort
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 2
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
