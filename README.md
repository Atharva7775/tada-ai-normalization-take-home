# Tada AI · Data Normalization

A local platform that pulls employee, direct-deposit, deduction, and payroll
data from three payroll providers — **PrismHR, isolved, and UKG Ready** —
and normalizes all of it into one shared canonical schema, regardless of
which provider it came from. Built for the Tada AI data-normalization
take-home; the original assignment brief is preserved verbatim at
[ASSIGNMENT.md](ASSIGNMENT.md).

- **Full setup and run commands:** [RUNNING.md](RUNNING.md)
- **Assumptions, decisions, known gaps, and real bugs found and fixed:**
  [ASSUMPTIONS_AND_DECISIONS.md](ASSUMPTIONS_AND_DECISIONS.md)
- **Canonical schema design rationale:** [docs/CANONICAL_SCHEMA.md](docs/CANONICAL_SCHEMA.md)
  (technical) and [docs/layman.md](docs/layman.md) (plain-English walkthrough)

## What's in this repo

```
contracts/                  Organizer-supplied API specs and lookup references (read-only)
src/normalization/
  canonical/                 The shared schema every provider maps into (models.py, enums.py)
  adapters/                  One file per provider - raw API shape -> canonical schema
  __main__.py                CLI entry point (organizer-provided scaffold)
scripts/generate_fixtures.py Deterministic synthetic data generator, no credentials needed
app/                         Streamlit wizard app + the Python modules it's built from
tests/                       pytest suite against the synthetic fixtures (23 tests)
docs/                        Design-rationale documents
postman/                     Importable Postman collection covering all three provider APIs
```

## Approach

**Three adapters, one schema.** Each provider (`src/normalization/adapters/`)
gets its own adapter whose only job is translating that provider's raw API
shape into one shared canonical schema (`src/normalization/canonical/`) -
`Company`, `Employee` (with `direct_deposits`/`deductions` nested inside, per
the assignment's four data types), and `Paycheck`. Every adapter exposes the
same `normalize(entity, response, reference)` entry point, so nothing
downstream (the CLI, the test suite, the Streamlit app) needs to know which
provider it's looking at.

**Cross-provider identity without a mapping table.** Canonical ids are
provider-prefixed composite strings (`canonical_id(provider, kind, raw_id)`
→ `"prismhr:employee:A00576"`), so an `Employee.company_id` can point
straight at a `Company.id` with no separate id-mapping table to keep in
sync, and ids from all three providers can coexist in one shared SQLite
database without colliding.

**Every enum keeps its raw code.** The organizer's own lookup-reference
files say outright that they're partial - undocumented and
tenant-configured values aren't supplied. So every enum field (employment
status, deduction category, etc.) ships with a sibling `raw_*` string: the
adapter's best-guess canonical value, plus the original code, always both,
never just one. An unrecognized code falls back to `OTHER`/`UNKNOWN`
instead of raising.

**Deterministic synthetic data, no credentials required.**
`scripts/generate_fixtures.py` fabricates six scripted scenarios per
provider (happy path, terminated, on-leave, no-deposits/no-deductions,
multiple-deposits, and a deliberately-unrecognized status code) in each
provider's real raw API shape - committed under `tests/fixtures/` and
exercised by the test suite, so grading never depends on live credentials.

**A Streamlit app ties the whole pipeline together end to end.** Sign in to
the organizer's live demo APIs (optional) or generate synthetic data, run
either through the real adapters, and save the result into one shared
SQLite database (`canonical.db`) - with a built-in table browser and a
per-session SQL export, so the normalized output is actually inspectable,
not just a JSON blob in a terminal. See [RUNNING.md](RUNNING.md) for the
full step-by-step wizard walkthrough.

## How I built it

1. Read the organizer's reference specs for all three providers and the
   `contracts/*/lookup-reference.json` files to see what was actually
   documented versus what wasn't.
2. Designed the canonical schema first (`docs/CANONICAL_SCHEMA.md` /
   `docs/layman.md`), before writing a single adapter - what fields every
   provider needed to fit into, and the house rules that apply everywhere
   (exact-precision money, raw-code preservation, PII minimization,
   `extra="forbid"` validation).
3. Built the PrismHR adapter first (the most completely documented
   provider), verified it against real pulled data, then isolved and UKG
   Ready, each of which surfaced new gaps that fed back into the schema.
4. Built `scripts/generate_fixtures.py` so the test suite and submission
   never depend on live credentials, and wrote `tests/test_*_adapter.py`
   against those fixtures.
5. Built the Streamlit app (`app/`) as a thin UI layer over the same
   adapters and schema - every module under `app/` is deliberately
   Streamlit-free at its core (`data_client.py`, `canonicalize_client.py`,
   `db_client.py`, etc.) so the actual pull/normalize/save logic is
   reusable outside the UI, and `streamlit_app.py` just wires it together.
6. Iterated on the app based on actual use: pulling live data surfaced real
   bugs the fixtures hadn't (a PrismHR date field that's genuinely
   `"0000-01-01"` for some employees; two providers' direct-deposit ids
   that collide across different employees) - both found and fixed, with
   the reasoning documented in
   [ASSUMPTIONS_AND_DECISIONS.md](ASSUMPTIONS_AND_DECISIONS.md).

**Optional write-path extension:** not attempted. This submission is
read/normalize-only (provider → canonical), as the assignment explicitly
scopes that extension as optional.

## Quickstart

```sh
git clone <this-repo-url>
cd tada-ai-normalization-take-home
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python3 -m pytest tests/ -q      # 23 tests, synthetic fixtures, no credentials needed
streamlit run app/streamlit_app.py              # the full wizard app
```

Full commands (CLI usage, regenerating fixtures, live-demo credentials, a
step-by-step tour of the Streamlit wizard) are in
[RUNNING.md](RUNNING.md).

## Testing

`PYTHONPATH=src python3 -m pytest tests/ -q` runs 23 tests: one suite per
provider adapter (company/employee/payroll conversion against the
deterministic synthetic fixtures, including the six scripted scenarios
above and both real bugs listed in the assumptions file), plus the
organizer's own starter and reference-integrity checks. All synthetic,
deterministic, and credential-free.

## Known limitations

Every provider has real, confirmed gaps - fields that live behind an
endpoint this project never crawled (UKG's `/demographics`, `/pay-info`),
fields no provider in this project's discovery ever documented an enum for
(isolved's employment-status strings), and fields genuinely absent from
the data (`Paycheck.benefit_contributions` for all three). None of these
are silently guessed at - each is either mapped from directly-observed
values or left `None` with the reason recorded inline. Full list, with
reasoning, in [ASSUMPTIONS_AND_DECISIONS.md](ASSUMPTIONS_AND_DECISIONS.md).
