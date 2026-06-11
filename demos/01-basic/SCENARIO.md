# Demo 01 — Diligence on a SaaS dataroom

This scenario runs `dealroom` against `sample-dataroom/`, a realistic but
deliberately incomplete SaaS data room for a fictional company, **Acme Cloud, Inc.**

## Run it

```bash
# 1. Generate the SaaS diligence checklist
python -m dealroom init --deal-type saas

# 2. Scan the sample dataroom (full checklist + risk detail)
python -m dealroom scan demos/01-basic/sample-dataroom --deal-type saas

# 3. Condensed status + risk summary
python -m dealroom report demos/01-basic/sample-dataroom --deal-type saas

# 4. Machine-readable / shareable formats
python -m dealroom scan demos/01-basic/sample-dataroom --deal-type saas --format json
python -m dealroom report demos/01-basic/sample-dataroom --deal-type saas --format html --out report.html
```

## What it should catch

**Missing required checklist items** (present in the SaaS checklist, but no
matching file in the dataroom):

| Item                    | Why it matters                              |
|-------------------------|---------------------------------------------|
| Tax returns / filings   | Hidden tax exposure                         |
| Litigation summary      | Undisclosed disputes                        |
| Security & compliance   | No SOC 2 / pen-test evidence                |
| Data privacy            | No GDPR/CCPA / DPA / privacy policy         |

**Risky patterns** found in the documents that *are* present:

| Rule                          | Severity | Source file                        |
|-------------------------------|----------|------------------------------------|
| `contract.unlimited_liability`| high     | `Legal/msa-bigco-customer.txt`     |
| `contract.change_of_control`  | high     | `Legal/msa-bigco-customer.txt`     |
| `ip.no_assignment`            | high     | `IP/contractor-invention-agreement.txt` |
| `contract.expired`            | high     | `Legal/vendor-agreement-datacenter.txt` |
| `secret.embedded`             | critical | `Commercial/subscription-terms-of-service.txt` (placeholder, redacted) |
| `contract.auto_renew`         | medium   | `Legal/msa-bigco-customer.txt`     |
| `contract.expiring_soon`      | medium   | `Legal/msa-bigco-customer.txt`     |
| `contract.exclusivity`        | medium   | `Commercial/subscription-terms-of-service.txt` |
| `contract.termination_convenience` | low | `Legal/vendor-agreement-datacenter.txt` |

Because required items are missing and critical/high risks are present, the
process exits non-zero — failing any CI gate that wraps it.

> The embedded "secret" is the obvious non-secret placeholder
> `EXAMPLE_NOT_A_REAL_TOKEN`; `dealroom` still flags the *pattern* and redacts
> the value in its output, demonstrating the secret-hygiene check.
