# dealroom — Architecture

`dealroom` is a single Python package, standard-library only, with a clean
split between engine and interfaces.

```
dealroom/
  __init__.py     exports TOOL_NAME / TOOL_VERSION + the public API
  __main__.py     `python -m dealroom`
  core.py         the engine (checklists, risk detection, scan, serializers)
  cli.py          argparse front-end (init / scan / report / mcp)
  mcp_server.py   stdio JSON-RPC MCP server (checklist / scan_dataroom tools)
```

## Engine (`core.py`)

Three responsibilities, all deterministic and side-effect free except the
explicit filesystem reads in `scan_dataroom`:

1. **Checklists** — `build_checklist(deal_type)` composes a set of common
   corporate/financial/legal/HR/IP items with deal-type-specific items
   (`saas` / `services` / `hardware`). Each `ChecklistItem` carries filename
   keyword *hints* used to map dataroom files onto it.

2. **Risk detection** — a table of compiled regexes (`_RISK_PATTERNS`) flags
   risky contract language; a separate expiry pass parses ISO / US / long-form
   dates near expiry keywords and classifies contracts as expired or
   expiring-soon. Detected secrets are pattern-flagged but their values are
   **redacted** before they ever leave the process.

3. **Scan + serialize** — `scan_dataroom(dir, deal_type)` walks the tree,
   inventories files, maps them to checklist items, runs risk detection on
   text-like documents, and returns a `ScanResult`. `ScanResult.to_dict()` and
   `to_html()` render JSON and a self-contained, fully-escaped HTML report.

## Failure semantics

A diligence pass *fails* (non-zero exit) when a **required** checklist item is
missing **or** any **critical/high** risk is present. `--fail-on <severity>`
overrides this with an explicit severity gate, making the tool CI-friendly.

## Privacy

Fully local. No network calls. Only text-like files are opened; binary office
formats are inventoried and mapped by filename but not parsed. Reads are capped
at 2 MB per file.
