# dealroom — Roadmap

> M&A / VC due-diligence assistant — dataroom checklist, item tracking, document risk flagging

## Now (v0.1.x)
- Stable CLI: `init`, `scan`, `report` with table / JSON / HTML output.
- Deal-type checklists: SaaS / services / hardware.
- Local document risk detection (auto-renew, change-of-control, unlimited
  liability, missing IP assignment, expiring/expired contracts, embedded secrets).
- Bundled sample dataroom + smoke and deep tests.
- MCP server for Cognis.Studio integration.

## Next (v0.2)
- Binary document extraction (`.pdf` / `.docx` / `.xlsx`) behind optional deps.
- Configurable checklist + risk rules via a local YAML/JSON profile.
- Side-by-side scan diffing to track diligence progress over time.

## Later (v1.0)
- Per-jurisdiction risk libraries and a stable rule/plugin API.
- Packaging to PyPI.
- Pro tier + commercial support (see `licensing@cognis.digital`).

Want something prioritized? Open an issue or a PR — see [CONTRIBUTING.md](CONTRIBUTING.md).
