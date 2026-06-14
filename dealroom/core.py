"""dealroom core — M&A / VC due-diligence assistant engine.

Fully local, standard-library only. No network access required.

The engine has three responsibilities:

1. **Checklists** — produce a structured diligence checklist keyed by *deal
   type* (``saas`` / ``services`` / ``hardware``). Each checklist item declares
   a category, a human label, whether it is *required*, and a set of filename
   keyword hints used to map dataroom files onto it.

2. **Scan** — walk a local dataroom directory, inventory the files, map each
   file to the checklist item(s) it most plausibly satisfies, flag checklist
   items that are *missing* (required but unmatched), and read text-like
   documents for risky language (auto-renew clauses, change-of-control,
   unlimited liability, missing IP assignment, expiring contracts, ...).

3. **Report / serialize** — roll the scan up into a status + risk summary and
   render it as a table, JSON, or a self-contained HTML report.

Everything here is deterministic and side-effect free except the explicit
filesystem reads in :func:`scan_dataroom`.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

TOOL_NAME = "dealroom"
TOOL_VERSION = "0.1.0"

# Severity ordering shared with the CLI gate. Lower index == more severe.
SEVERITY_ORDER: Dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}

DEAL_TYPES: Tuple[str, ...] = ("saas", "services", "hardware")

# Text-like extensions we will open and scan for risky language. Binary office
# formats (.docx/.pdf/.xlsx) are inventoried and mapped, but their bytes are not
# parsed — we keep to the standard library and to a no-surprises contract.
_TEXT_EXTS = {".txt", ".md", ".markdown", ".rst", ".csv", ".json", ".html",
              ".htm", ".text", ".log", ".cfg", ".ini", ".yaml", ".yml"}

# Cap how much of any single file we read, so a giant log can't blow up memory.
_MAX_READ_BYTES = 2_000_000


class DataroomError(Exception):
    """Raised for unusable inputs (missing directory, bad deal type, ...)."""


# --------------------------------------------------------------------------- #
# Checklist model
# --------------------------------------------------------------------------- #
@dataclass
class ChecklistItem:
    """A single diligence request."""

    id: str
    category: str
    label: str
    required: bool
    # Filename keyword hints (lowercase substrings) used to map files.
    hints: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "category": self.category,
            "label": self.label,
            "required": self.required,
            "hints": list(self.hints),
        }


# Items common to every deal type. (id, category, label, required, hints)
_COMMON_ITEMS: Tuple[Tuple[str, str, str, bool, Tuple[str, ...]], ...] = (
    ("corp.formation", "Corporate", "Certificate of incorporation / formation", True,
     ("incorporation", "formation", "articles", "charter", "certificate")),
    ("corp.bylaws", "Corporate", "Bylaws / operating agreement", True,
     ("bylaws", "operating-agreement", "operating_agreement", "llc-agreement")),
    ("corp.captable", "Corporate", "Capitalization table", True,
     ("cap-table", "cap_table", "captable", "capitalization", "shareholder")),
    ("corp.board", "Corporate", "Board minutes & consents", False,
     ("board", "minutes", "consent", "resolution")),
    ("fin.statements", "Financial", "Financial statements (P&L, balance sheet)", True,
     ("financial", "p&l", "pnl", "income-statement", "balance-sheet", "statements")),
    ("fin.tax", "Financial", "Tax returns / filings", True,
     ("tax", "return", "1120", "irs", "k-1")),
    ("fin.debt", "Financial", "Debt & financing agreements", False,
     ("loan", "debt", "credit-agreement", "promissory", "promissory-note", "financing")),
    ("legal.litigation", "Legal", "Litigation & disputes summary", True,
     ("litigation", "dispute", "lawsuit", "claim", "settlement")),
    ("legal.contracts", "Legal", "Material customer & vendor contracts", True,
     ("contract", "agreement", "msa", "sow", "vendor", "supplier", "customer")),
    ("legal.insurance", "Legal", "Insurance policies", False,
     ("insurance", "policy", "coverage", "liability-policy")),
    ("hr.employees", "HR", "Employee census & agreements", True,
     ("employee", "census", "offer-letter", "employment", "payroll")),
    ("hr.benefits", "HR", "Benefit plans", False,
     ("benefit", "401k", "pto", "stock-option", "esop")),
    ("ip.assignments", "IP", "IP assignment agreements", True,
     ("ip-assignment", "ip_assignment", "assignment", "invention", "piiaa", "ciiaa")),
    ("ip.registrations", "IP", "Patents / trademarks / copyrights", False,
     ("patent", "trademark", "copyright", "uspto", "registration")),
)

# Deal-type-specific items.
_SAAS_ITEMS: Tuple[Tuple[str, str, str, bool, Tuple[str, ...]], ...] = (
    ("saas.metrics", "SaaS Metrics", "ARR / MRR / churn cohort analysis", True,
     ("arr", "mrr", "churn", "cohort", "retention", "metrics")),
    ("saas.subscriptions", "Commercial", "Subscription / customer agreements (ToS, SLA)", True,
     ("subscription", "tos", "terms-of-service", "sla", "eula", "saas-agreement")),
    ("saas.security", "Tech", "Security & compliance (SOC 2, pen tests)", True,
     ("soc2", "soc-2", "pentest", "pen-test", "iso27001", "security", "compliance")),
    ("saas.privacy", "Tech", "Data privacy (GDPR/CCPA, DPA, privacy policy)", True,
     ("privacy", "gdpr", "ccpa", "dpa", "data-processing")),
    ("saas.architecture", "Tech", "Architecture & hosting / DR plan", False,
     ("architecture", "infrastructure", "hosting", "disaster-recovery", "dr-plan")),
    ("saas.oss", "Tech", "Open-source / third-party license inventory", False,
     ("oss", "open-source", "license-inventory", "sbom", "bill-of-materials")),
)

_SERVICES_ITEMS: Tuple[Tuple[str, str, str, bool, Tuple[str, ...]], ...] = (
    ("svc.sow", "Commercial", "Statements of work & master service agreements", True,
     ("sow", "statement-of-work", "msa", "master-service", "engagement")),
    ("svc.backlog", "Financial", "Backlog / pipeline & utilization", True,
     ("backlog", "pipeline", "utilization", "bookings", "revenue-by-client")),
    ("svc.contractors", "HR", "Independent contractor / 1099 agreements", True,
     ("contractor", "1099", "freelance", "subcontractor", "consultant")),
    ("svc.clientconc", "Commercial", "Client concentration analysis", False,
     ("concentration", "top-clients", "client-revenue", "key-account")),
    ("svc.deliverables", "Legal", "Deliverable acceptance & warranty terms", False,
     ("deliverable", "acceptance", "warranty", "milestone")),
)

_HARDWARE_ITEMS: Tuple[Tuple[str, str, str, bool, Tuple[str, ...]], ...] = (
    ("hw.bom", "Operations", "Bill of materials & component sourcing", True,
     ("bom", "bill-of-materials", "components", "sourcing")),
    ("hw.suppliers", "Operations", "Supplier / manufacturing agreements", True,
     ("supplier", "manufacturing", "manufacturer", "oem", "contract-manufacturer", "cm-agreement")),
    ("hw.inventory", "Operations", "Inventory & WIP valuation", True,
     ("inventory", "wip", "work-in-progress", "stock-valuation")),
    ("hw.warranty", "Legal", "Product warranty & recall history", True,
     ("warranty", "recall", "defect", "rma", "return-merchandise")),
    ("hw.regulatory", "Compliance", "Regulatory certifications (FCC, CE, UL, RoHS)", True,
     ("fcc", "ce-mark", "ul-listing", "rohs", "reach", "certification", "regulatory")),
    ("hw.facilities", "Operations", "Facilities, leases & equipment", False,
     ("lease", "facility", "equipment", "real-estate", "premises")),
)

_DEAL_ITEMS: Dict[str, Tuple] = {
    "saas": _SAAS_ITEMS,
    "services": _SERVICES_ITEMS,
    "hardware": _HARDWARE_ITEMS,
}


def build_checklist(deal_type: str) -> List[ChecklistItem]:
    """Return the ordered checklist for ``deal_type``.

    Raises :class:`DataroomError` for an unknown deal type.
    """
    dt = (deal_type or "").strip().lower()
    if dt not in _DEAL_ITEMS:
        raise DataroomError(
            f"unknown deal type {deal_type!r}; choose one of {', '.join(DEAL_TYPES)}")
    rows = list(_COMMON_ITEMS) + list(_DEAL_ITEMS[dt])
    return [ChecklistItem(item_id, cat, label, req, hints)
            for (item_id, cat, label, req, hints) in rows]


def checklist_to_dict(deal_type: str) -> Dict[str, object]:
    items = build_checklist(deal_type)
    return {
        "tool": TOOL_NAME,
        "version": TOOL_VERSION,
        "deal_type": deal_type.strip().lower(),
        "generated": _dt.date.today().isoformat(),
        "item_count": len(items),
        "required_count": sum(1 for i in items if i.required),
        "items": [i.to_dict() for i in items],
    }


# --------------------------------------------------------------------------- #
# Risk detection
# --------------------------------------------------------------------------- #
@dataclass
class Risk:
    """A risky pattern found in (or inferred about) a dataroom."""

    rule: str
    severity: str
    message: str
    location: str = ""          # file path (relative) + optional line
    snippet: str = ""           # the matched text, trimmed

    def to_dict(self) -> Dict[str, object]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
            "snippet": self.snippet,
        }


# (rule, severity, message, compiled-regex). Order is informational only.
_RISK_PATTERNS: Tuple[Tuple[str, str, str, "re.Pattern[str]"], ...] = (
    ("contract.auto_renew", "medium",
     "Auto-renewal / evergreen clause — renews unless notice is given.",
     re.compile(r"\b(auto(?:matic(?:ally)?)?[\s-]*renew\w*|evergreen|"
                r"renew\w*\s+for\s+(?:successive|additional)\b|"
                r"unless\s+(?:either\s+)?(?:party|notice)\b.{0,40}\bterminat)",
                re.I)),
    ("contract.change_of_control", "high",
     "Change-of-control provision — may be triggered or assignable on acquisition.",
     re.compile(r"\bchange[\s-]+(?:of|in)[\s-]+control\b|\bupon\s+a\s+sale\s+of\b|"
                r"\bassign\w*\b.{0,30}\bconsent\b", re.I)),
    ("contract.unlimited_liability", "high",
     "Unlimited / uncapped liability or indemnity exposure.",
     re.compile(r"\bunlimited\s+liab\w*|"
                r"liab\w*\b[\s\S]{0,90}?\b(?:shall|will|is|be)\s+unlimited|"
                r"liab\w*\s+(?:shall|will)?\s*(?:not\s+be|is\s+not)\s+"
                r"(?:capped|limited)|without\s+limit\w*\s+of\s+liab\w*|"
                r"no\s+(?:cap|limit\w*)\s+on\s+(?:liab\w*|damages)", re.I)),
    ("ip.no_assignment", "high",
     "IP / invention language that may NOT assign rights to the company.",
     re.compile(r"\bretain\w*\s+(?:all\s+)?(?:right\w*|ownership|title)\b.{0,40}"
                r"\b(?:invention|intellectual\s+property|work\s+product)\b|"
                r"\b(?:employee|contractor|consultant)\s+(?:shall\s+)?(?:retain|own)s?\b",
                re.I)),
    ("contract.exclusivity", "medium",
     "Exclusivity / non-compete / most-favored-nation lock-in.",
     re.compile(r"(?<!non-)(?<!non )\bexclusiv\w*|\bnon[\s-]*compete\b|"
                r"\bmost[\s-]+favored[\s-]+nation\b|\bMFN\b", re.I)),
    ("contract.termination_convenience", "low",
     "Termination-for-convenience right (counterparty can exit at will).",
     re.compile(r"\bterminat\w*\s+(?:this\s+agreement\s+)?for\s+(?:any\s+reason|convenience)\b",
                re.I)),
    ("secret.embedded", "critical",
     "Possible embedded credential / secret in a dataroom document.",
     re.compile(r"(?i)\b(?:api[_\- ]?key|secret[_\- ]?key|password|passwd|access[_\- ]?token|"
                r"private[_\- ]?key)\b\s*[:=]\s*[\"']?[A-Za-z0-9/+_\-]{16,}")),
)

# Date detection for expiring/expired contracts. We support ISO (2026-01-31) and
# common US formats (01/31/2026, January 31, 2026), near an expiry keyword.
_EXPIRY_KEYWORD = re.compile(
    r"\b(expir\w*|terminat\w*|end\s+date|valid\s+(?:until|through)|"
    r"renewal\s+date|effective\s+(?:until|through))\b", re.I)

_DATE_PATTERNS: Tuple["re.Pattern[str]", ...] = (
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),                       # 2026-01-31
    re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"),                   # 01/31/2026
    re.compile(r"\b(January|February|March|April|May|June|July|August|"
               r"September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b", re.I),
)

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}

# Soon-to-expire window (days). Contracts expiring within this window are flagged.
EXPIRY_SOON_DAYS = 90


def _parse_dates(text: str) -> List[_dt.date]:
    out: List[_dt.date] = []
    for m in _DATE_PATTERNS[0].finditer(text):
        try:
            out.append(_dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            pass
    for m in _DATE_PATTERNS[1].finditer(text):
        try:
            out.append(_dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2))))
        except ValueError:
            pass
    for m in _DATE_PATTERNS[2].finditer(text):
        mon = _MONTHS.get(m.group(1).lower())
        if mon:
            try:
                out.append(_dt.date(int(m.group(3)), mon, int(m.group(2))))
            except ValueError:
                pass
    return out


def _scan_text_for_risks(rel_path: str, text: str,
                         today: _dt.date) -> List[Risk]:
    """Return risks found inside a single document's text."""
    risks: List[Risk] = []
    lines = text.splitlines()

    for rule, sev, msg, rx in _RISK_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        # Find a 1-based line number for the match start.
        upto = text[: m.start()]
        line_no = upto.count("\n") + 1
        snippet = m.group(0).strip()
        if len(snippet) > 120:
            snippet = snippet[:117] + "..."
        # Never echo a captured secret value back out.
        if rule == "secret.embedded":
            snippet = re.sub(r"([:=]\s*[\"']?).*$", r"\1***REDACTED***", snippet)
        risks.append(Risk(rule, sev, msg,
                          location=f"{rel_path}:{line_no}", snippet=snippet))

    # Expiry: look at lines that mention an expiry keyword and carry a date.
    for idx, line in enumerate(lines, start=1):
        if not _EXPIRY_KEYWORD.search(line):
            continue
        for d in _parse_dates(line):
            delta = (d - today).days
            if delta < 0:
                risks.append(Risk(
                    "contract.expired", "high",
                    f"Contract appears EXPIRED ({d.isoformat()}, {abs(delta)} days ago).",
                    location=f"{rel_path}:{idx}", snippet=line.strip()[:120]))
            elif delta <= EXPIRY_SOON_DAYS:
                risks.append(Risk(
                    "contract.expiring_soon", "medium",
                    f"Contract expiring soon ({d.isoformat()}, in {delta} days).",
                    location=f"{rel_path}:{idx}", snippet=line.strip()[:120]))
            break  # one date per expiry line is enough
    return risks


# --------------------------------------------------------------------------- #
# File -> checklist mapping
# --------------------------------------------------------------------------- #
def _match_items(rel_path: str,
                 items: Sequence[ChecklistItem]) -> List[str]:
    """Return checklist item ids whose hints appear in the file path."""
    hay = rel_path.lower().replace("\\", "/")
    base = hay.rsplit("/", 1)[-1]
    matched: List[str] = []
    for it in items:
        for hint in it.hints:
            if hint in hay or hint in base:
                matched.append(it.id)
                break
    return matched


# --------------------------------------------------------------------------- #
# Scan
# --------------------------------------------------------------------------- #
@dataclass
class FileEntry:
    path: str                  # relative to the dataroom root
    size: int
    ext: str
    matched_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "size": self.size,
            "ext": self.ext,
            "matched_items": list(self.matched_items),
        }


@dataclass
class ScanResult:
    deal_type: str
    root: str
    items: List[ChecklistItem]
    files: List[FileEntry]
    risks: List[Risk]
    # item_id -> list of file paths satisfying it
    coverage: Dict[str, List[str]]
    generated: str = field(default_factory=lambda: _dt.date.today().isoformat())

    # ---- derived views -------------------------------------------------- #
    @property
    def present_items(self) -> List[ChecklistItem]:
        return [i for i in self.items if self.coverage.get(i.id)]

    @property
    def missing_items(self) -> List[ChecklistItem]:
        return [i for i in self.items if not self.coverage.get(i.id)]

    @property
    def missing_required(self) -> List[ChecklistItem]:
        return [i for i in self.missing_items if i.required]

    @property
    def risk_counts(self) -> Dict[str, int]:
        counts = {s: 0 for s in SEVERITY_ORDER}
        for r in self.risks:
            counts[r.severity] = counts.get(r.severity, 0) + 1
        return counts

    @property
    def completion_pct(self) -> int:
        if not self.items:
            return 100
        return round(100 * len(self.present_items) / len(self.items))

    @property
    def failed(self) -> bool:
        """A diligence pass *fails* if a required item is missing or a
        critical/high risk is present."""
        if self.missing_required:
            return True
        return any(r.severity in ("critical", "high") for r in self.risks)

    def to_dict(self) -> Dict[str, object]:
        rc = self.risk_counts
        return {
            "tool": TOOL_NAME,
            "version": TOOL_VERSION,
            "deal_type": self.deal_type,
            "root": self.root,
            "generated": self.generated,
            "summary": {
                "checklist_items": len(self.items),
                "items_present": len(self.present_items),
                "items_missing": len(self.missing_items),
                "missing_required": len(self.missing_required),
                "completion_pct": self.completion_pct,
                "files_inventoried": len(self.files),
                "total_risks": len(self.risks),
                "risk_counts": rc,
                "failed": self.failed,
            },
            "items": [
                {**i.to_dict(),
                 "present": bool(self.coverage.get(i.id)),
                 "files": list(self.coverage.get(i.id, []))}
                for i in self.items
            ],
            "missing_required": [i.id for i in self.missing_required],
            "files": [f.to_dict() for f in self.files],
            "risks": [r.to_dict() for r in self.risks],
        }


def scan_dataroom(directory: str, deal_type: str) -> ScanResult:
    """Inventory ``directory``, map files to the checklist, flag risks."""
    if not directory or not directory.strip():
        raise DataroomError("directory path must not be empty")
    if not os.path.isdir(directory):
        raise DataroomError(f"not a directory: {directory}")
    items = build_checklist(deal_type)
    today = _dt.date.today()

    files: List[FileEntry] = []
    risks: List[Risk] = []
    coverage: Dict[str, List[str]] = {it.id: [] for it in items}

    for dirpath, dirnames, filenames in os.walk(directory):
        # Skip dotfolders (e.g. .git) deterministically.
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, directory).replace("\\", "/")
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            ext = os.path.splitext(name)[1].lower()

            matched = _match_items(rel, items)
            for item_id in matched:
                coverage[item_id].append(rel)
            files.append(FileEntry(rel, size, ext, matched))

            # Read + risk-scan text-like documents only.
            if ext in _TEXT_EXTS:
                try:
                    with open(full, "r", encoding="utf-8", errors="replace") as fh:
                        text = fh.read(_MAX_READ_BYTES)
                except OSError:
                    continue
                risks.extend(_scan_text_for_risks(rel, text, today))

    # Stable ordering: risks by severity then location.
    risks.sort(key=lambda r: (SEVERITY_ORDER.get(r.severity, 99), r.location))
    files.sort(key=lambda f: f.path)
    return ScanResult(
        deal_type=deal_type.strip().lower(),
        root=os.path.abspath(directory),
        items=items, files=files, risks=risks, coverage=coverage)


# --------------------------------------------------------------------------- #
# Serializers
# --------------------------------------------------------------------------- #
def to_html(result: ScanResult) -> str:
    """Render a self-contained HTML diligence report (all content escaped)."""
    e = _html.escape
    s = result.to_dict()["summary"]
    rc = result.risk_counts
    parts: List[str] = []
    parts.append("<!doctype html>")
    parts.append("<html lang='en'><head><meta charset='utf-8'>")
    parts.append(f"<title>dealroom report — {e(result.deal_type)}</title>")
    parts.append(
        "<style>body{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:2rem;"
        "color:#1a202c}h1{color:#2b6cb0}table{border-collapse:collapse;width:100%;"
        "margin:1rem 0}th,td{border:1px solid #cbd5e0;padding:.4rem .6rem;"
        "text-align:left;font-size:14px}th{background:#edf2f7}"
        ".crit{color:#c53030;font-weight:700}.high{color:#dd6b20;font-weight:700}"
        ".medium{color:#b7791f}.low{color:#718096}.ok{color:#2f855a}"
        ".miss{color:#c53030}.badge{display:inline-block;padding:.1rem .5rem;"
        "border-radius:.5rem;background:#edf2f7;margin-right:.4rem}</style></head><body>")
    parts.append(f"<h1>dealroom — {e(result.deal_type)} diligence report</h1>")
    parts.append(f"<p>root: <code>{e(result.root)}</code> · generated {e(result.generated)}</p>")
    parts.append("<p>"
                 f"<span class='badge'>completion {s['completion_pct']}%</span>"
                 f"<span class='badge'>items {s['items_present']}/{s['checklist_items']}</span>"
                 f"<span class='badge'>missing required {s['missing_required']}</span>"
                 f"<span class='badge'>files {s['files_inventoried']}</span>"
                 f"<span class='badge'>risks {s['total_risks']}</span>"
                 "</p>")

    # Checklist table.
    parts.append("<h2>Checklist</h2><table>")
    parts.append("<tr><th>Status</th><th>Category</th><th>Item</th>"
                 "<th>Req</th><th>Files</th></tr>")
    for it in result.items:
        present = bool(result.coverage.get(it.id))
        status = "<span class='ok'>PRESENT</span>" if present else \
                 ("<span class='miss'>MISSING</span>" if it.required
                  else "<span class='low'>missing</span>")
        files = e(", ".join(result.coverage.get(it.id, []))) or "&mdash;"
        parts.append(f"<tr><td>{status}</td><td>{e(it.category)}</td>"
                     f"<td>{e(it.label)}</td><td>{'yes' if it.required else 'no'}</td>"
                     f"<td>{files}</td></tr>")
    parts.append("</table>")

    # Risk table.
    parts.append("<h2>Risks</h2>")
    if not result.risks:
        parts.append("<p class='ok'>No risky patterns detected.</p>")
    else:
        parts.append("<table><tr><th>Severity</th><th>Rule</th><th>Finding</th>"
                     "<th>Where</th><th>Snippet</th></tr>")
        for r in result.risks:
            cls = {"critical": "crit", "high": "high", "medium": "medium",
                   "low": "low", "info": "low"}.get(r.severity, "low")
            parts.append(
                f"<tr><td class='{cls}'>{e(r.severity.upper())}</td>"
                f"<td>{e(r.rule)}</td><td>{e(r.message)}</td>"
                f"<td><code>{e(r.location)}</code></td>"
                f"<td><code>{e(r.snippet)}</code></td></tr>")
        parts.append("</table>")

    parts.append(f"<p>RESULT: <b>{'FAIL' if result.failed else 'PASS'}</b> "
                 f"(critical={rc['critical']} high={rc['high']} "
                 f"medium={rc['medium']} low={rc['low']})</p>")
    parts.append("<hr><p style='color:#718096;font-size:12px'>"
                 "Generated by dealroom — Cognis Neural Suite. Informational only; "
                 "not legal advice.</p>")
    parts.append("</body></html>")
    return "\n".join(parts)
