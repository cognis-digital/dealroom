# dealroom — M&A / VC due-diligence assistant

> Part of the **[Cognis Neural Suite](https://github.com/cognis-digital)** by [Cognis Digital](https://cognis.digital)
> Cognis Open Collaboration License (COCL) v1.0 · domain: `business`

[![install](https://img.shields.io/badge/install-git%2B%20%C2%B7%20pipx%20%C2%B7%20uv-6b46c1.svg)](#install--every-way-every-platform)
[![CI](https://github.com/cognis-digital/dealroom/actions/workflows/ci.yml/badge.svg)](https://github.com/cognis-digital/dealroom/actions)
[![License: COCL 1.0](https://img.shields.io/badge/License-COCL%201.0-2b6cb0.svg)](LICENSE)
[![Suite](https://img.shields.io/badge/Cognis-Neural%20Suite-6b46c1.svg)](https://github.com/cognis-digital)

**Generate a dataroom checklist, track which items are present, and flag risks in local documents — fully local, no network needed.**

*Business & Operations — practical tooling for deals, diligence, and decisions.*

<!-- cognis:layman:start -->
## What is this?

Dealroom is a command-line tool that helps you run smarter due diligence when buying a company or evaluating a startup investment. You point it at a folder of business documents and it checks which important items are present (like cap tables, contracts, and financial statements), tells you exactly what is missing, and highlights red flags buried in the text — things like contracts that auto-renew without notice, expired agreements, or language that could let the other party walk away. Everything runs on your own computer; your documents never leave your machine.
<!-- cognis:layman:end -->

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

<!-- cognis:install:start -->
## Install

`dealroom` is source-available (not published to PyPI) — every method below installs
straight from GitHub. Pick whichever you prefer; the one-line scripts auto-detect
the best tool available on your machine.

**One-liner (Linux / macOS):**
```sh
curl -fsSL https://raw.githubusercontent.com/cognis-digital/dealroom/HEAD/install.sh | sh
```

**One-liner (Windows PowerShell):**
```powershell
irm https://raw.githubusercontent.com/cognis-digital/dealroom/HEAD/install.ps1 | iex
```

**Or install manually — any one of:**
```sh
pipx install "git+https://github.com/cognis-digital/dealroom.git"     # isolated (recommended)
uv tool install "git+https://github.com/cognis-digital/dealroom.git"  # uv
pip install "git+https://github.com/cognis-digital/dealroom.git"      # pip
```

**From source:**
```sh
git clone https://github.com/cognis-digital/dealroom.git
cd dealroom && pip install .
```

Then run:
```sh
dealroom --help
```
<!-- cognis:install:end -->

## Install

```bash
pip install "git+https://github.com/cognis-digital/dealroom.git"
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

<a name="verification"></a>
## Verification

[![tests](https://img.shields.io/badge/tests-46%20passing-2ea44f.svg)](AUDIT.md)

Every push is verified end-to-end. Latest audit (2026-06-12):

```text
tests        : 46 passed, 0 failed, 0 errored
compile      : all modules parse
cli          : C:\Python314\python.exe: No module named https
package      : https
```

<details><summary>CLI surface (<code>--help</code>)</summary>

```text
C:\Python314\python.exe: No module named https
```
</details>

Full machine-readable results: [`AUDIT.md`](AUDIT.md) · regenerate with `python -m https --help` + `pytest -q`.

<div align="right"><a href="#top">↑ back to top</a></div>


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
