# dealroom — M&A / VC due-diligence assistant

> Part of the **[Cognis Neural Suite](https://github.com/cognis-digital)** by [Cognis Digital](https://cognis.digital)
> Cognis Open Collaboration License (COCL) v1.0 · domain: `business`

[![PyPI](https://img.shields.io/pypi/v/cognis-dealroom.svg)](https://pypi.org/project/cognis-dealroom/)
[![CI](https://github.com/cognis-digital/dealroom/actions/workflows/ci.yml/badge.svg)](https://github.com/cognis-digital/dealroom/actions)
[![License: COCL 1.0](https://img.shields.io/badge/License-COCL%201.0-2b6cb0.svg)](LICENSE)
[![Suite](https://img.shields.io/badge/Cognis-Neural%20Suite-6b46c1.svg)](https://github.com/cognis-digital)

**Generate a dataroom checklist, track which items are present, and flag risks in local documents — fully local, no network needed.**

*Business & Operations — practical tooling for deals, diligence, and decisions.*

## Usage — step by step

`dealroom` is an M&A / VC due-diligence assistant: it scaffolds a dataroom checklist and scans a real dataroom directory for gaps, scoring readiness by deal type.

1. **Install:**

   ```bash
   pip install cognis-dealroom      # or: pip install -e .
   dealroom --version
   ```

2. **Initialize a checklist** for your deal type (`saas` is the default; `--format` is `table` or `json`):

   ```bash
   dealroom init --deal-type saas --format table
   ```

3. **Scan a dataroom directory** for missing/weak documents (formats: `table`, `json`, `html`):

   ```bash
   dealroom scan ./dataroom --deal-type saas --format json --out dd-findings.json
   ```

4. **Read the result / generate a report** — produce a shareable HTML diligence report:

   ```bash
   dealroom report ./dataroom --deal-type saas --format html --out dd-report.html
   jq '.findings[] | {id, severity, message}' dd-findings.json
   ```

5. **Gate it in CI** — fail when material gaps remain, and/or expose it to an agent over MCP (stdio JSON-RPC):

   ```bash
   dealroom scan ./dataroom --fail-on high          # non-zero exit blocks the merge
   dealroom mcp                                      # run as an MCP server
   ```

## Why

M&A and VC diligence starts the same way every time: a structured request list,
a folder full of documents, and the slow human job of cross-referencing the two
while hunting for landmines buried in contract language. `dealroom` automates the
mechanical parts. Point it at a local dataroom folder and it inventories the
files, maps them onto a deal-type-aware checklist, tells you exactly which
**required** items are missing, and flags **risky patterns** in the documents
that *are* there — auto-renewal clauses, change-of-control provisions, uncapped
liability, IP that may not be assigned, and contracts that are expired or about
to be. Everything runs locally; your data room never leaves the machine.

## Install

```bash
pip install cognis-dealroom
# or, from this repo:
pip install -e ".[dev]"
```

Standard library only — no third-party runtime dependencies.

## Quick start

```bash
dealroom --version

# 1. Scaffold a diligence checklist for a deal type (saas / services / hardware)
dealroom init --deal-type saas

# 2. Scan a local dataroom: map files to the checklist + flag document risks
dealroom scan demos/01-basic/sample-dataroom --deal-type saas

# 3. Condensed status + risk summary
dealroom report demos/01-basic/sample-dataroom --deal-type saas

# 4. Machine-readable / shareable formats
dealroom scan demos/01-basic/sample-dataroom --deal-type saas --format json
dealroom report demos/01-basic/sample-dataroom --deal-type saas --format html --out report.html

# 5. Gate a pipeline on high+ risks only
dealroom scan demos/01-basic/sample-dataroom --deal-type saas --fail-on high

# Run as an MCP server (Cognis.Studio / Claude Desktop / Cursor)
dealroom mcp
```

## Subcommands

| Command  | What it does                                                                 |
|----------|------------------------------------------------------------------------------|
| `init`   | Print a structured diligence checklist for a deal type.                      |
| `scan`   | Inventory a dataroom dir, map files to checklist items, flag risks (full).   |
| `report` | Scan, then print a condensed status + top-risk summary.                      |
| `mcp`    | Expose `checklist` and `scan_dataroom` as MCP tools over stdio.              |

## Deal types

- **`saas`** — adds ARR/MRR cohort metrics, subscription/ToS/SLA, SOC 2 / pen-test
  security, data privacy (GDPR/CCPA/DPA), architecture/DR, OSS inventory.
- **`services`** — adds SOW/MSA, backlog & utilization, 1099/contractor agreements,
  client concentration, deliverable acceptance & warranty.
- **`hardware`** — adds bill of materials & sourcing, supplier/manufacturing,
  inventory & WIP, warranty & recall, regulatory certs (FCC/CE/UL/RoHS), facilities.

All deal types share a common corporate / financial / legal / HR / IP core.

## Risk detections

| Rule                            | Severity | Flags                                            |
|---------------------------------|----------|--------------------------------------------------|
| `secret.embedded`               | critical | A credential/token pattern in a document (value redacted). |
| `contract.change_of_control`    | high     | Change-of-control / assignment-on-acquisition.   |
| `contract.unlimited_liability`  | high     | Uncapped liability or indemnity exposure.        |
| `ip.no_assignment`              | high     | IP language that may not assign rights to the company. |
| `contract.expired`              | high     | A contract whose end date is in the past.        |
| `contract.auto_renew`           | medium   | Auto-renewal / evergreen clauses.                |
| `contract.exclusivity`          | medium   | Exclusivity / non-compete / MFN lock-in.         |
| `contract.expiring_soon`        | medium   | A contract expiring within 90 days.              |
| `contract.termination_convenience` | low  | Counterparty can terminate at will.              |

## Output formats

- **Table** (default) — human-readable terminal summary
- **JSON** — machine-readable checklist + findings for pipelines
- **HTML** — shareable, self-contained report with status + risk rollups

## Built-in demo

[`demos/01-basic/`](demos/01-basic/SCENARIO.md) ships a realistic but
deliberately incomplete SaaS data room (Acme Cloud, Inc.) that exercises every
detection and several missing-required-item paths.

## How it fits the Cognis Neural Suite

`dealroom` is one tool in the [Cognis Neural Suite](https://github.com/cognis-digital).
Every tool ships an MCP server, so [Cognis.Studio](https://cognis.studio) agents
can call them as scoped capabilities.

## Architecture & roadmap

- Design notes: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Planned work: [`ROADMAP.md`](ROADMAP.md)

## Contributing

PRs, new checklist items, deal types, and risk detections are welcome under the
collaboration-pull model. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## Interoperability

`dealroom` composes with the 300+ tool Cognis suite — JSON in/out and a shared
OpenAI-compatible `/v1` backbone. See **[INTEROP.md](INTEROP.md)** for the
suite map, composition patterns, and reference stacks.

## Integrations

Forward `dealroom`'s findings to STIX/MISP/Sigma/Splunk/Elastic/Slack/webhooks via
[`cognis-connect`](https://github.com/cognis-digital/cognis-connect). See **[INTEGRATIONS.md](INTEGRATIONS.md)**.

## License

Source-available under the **Cognis Open Collaboration License (COCL) v1.0** —
free for personal, internal-evaluation, research, and educational use;
**commercial / production use requires a license** (licensing@cognis.digital).
See [LICENSE](LICENSE).

## Disclaimer

`dealroom` is an aid for diligence workflows, **not legal, tax, or financial
advice**. Its risk flags are heuristic and may produce false positives or miss
issues. Always have qualified counsel review material agreements.

## About

**[Cognis Digital](https://cognis.digital)** — Wyoming, USA · *Making Tomorrow Better Today: Advanced Cybersecurity, AI Innovation, and Blockchain Expertise.*
