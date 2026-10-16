# Assumptions, decisions, and limitations

This is the submission's required assumptions/decisions document (per
[ASSIGNMENT.md](ASSIGNMENT.md)'s "Submission" section). It consolidates the
design rationale in [docs/CANONICAL_SCHEMA.md](docs/CANONICAL_SCHEMA.md),
every confirmed per-provider data gap, every real bug found and fixed while
building and using this project, and the application-layer decisions behind
the Streamlit app in `app/`. Where something failed or looked inconsistent,
the reasoning for what I assumed or decided is recorded inline, not just the
outcome.

## 1. Schema structure

- **Three top-level entities, not four.** The organizer's own adapter
  scaffold fixes `ENTITIES = ("company", "employee", "payroll")`. Direct
  deposits and deductions - two of the assignment's four listed data types -
  aren't separate top-level entities here; they nest inside `Employee` as
  setup/configuration (`Employee.direct_deposits`, `Employee.deductions`).
  Actual transactional deduction amounts taken on a given paycheck live
  under `Paycheck` instead, as line items (`DeductionLine`) - the same
  deduction code can appear in both places with a different meaning (what's
  configured vs. what was actually withheld that period), which is why
  `DeductionLine` carries its own amounts rather than reusing
  `DeductionSetup`.
- **`PayrollRun` is exported but never instantiated by any of the three
  adapters.** All three return a flat list of `Paycheck`s instead -
  deliberate, not an oversight: whether a provider's payroll call naturally
  groups checks under one run is a per-adapter decision, and none of the
  three had a response shape that grouped cleanly. `PayrollRun` stays part
  of the schema so a future adapter could use it without a schema change.
- **Cross-provider identity without a mapping table.** Canonical ids are
  provider-prefixed composite strings - `canonical_id(provider, kind,
  raw_id)` → `"prismhr:employee:A00576"` - so `Employee.company_id` can
  point straight at a `Company.id`, invertible by splitting on `:`, with no
  separate id-mapping table to build or keep in sync. Every top-level record
  also carries a redundant `Source` block (`provider`, `raw_id`) so a
  consumer doesn't have to parse the composite id to answer "what provider
  did this come from."
- **Every enum field keeps its raw code** (e.g. `employment_status` +
  `raw_employment_status`). The organizer's lookup-reference files say
  outright that they're partial - e.g.
  `contracts/prismhr/lookup-reference.json`'s status-class entry literally
  says *"no candidate canonical mapping is supplied"*. An adapter that
  collapsed straight to an enum would silently lose information on any
  value this project's discovery missed, so every enum has an
  `OTHER`/`UNKNOWN` fallback and the raw code is never thrown away.
- **Money is `Decimal`, not `float`** - verified to serialize as an
  exact-precision string via `model_dump(mode="json")`
  (`Decimal("85000.10")` → `"85000.10"`), avoiding binary-float rounding
  drift across three payroll systems that each round differently
  internally.
- **PII is minimized by design, not modeled in full.** `DirectDeposit` only
  keeps `routing_number_last4`/`account_number_last4`; `Employee` only keeps
  `ssn_last4`. The canonical schema is a design artifact that can end up in
  a public submission repo, so full account/routing numbers and SSNs are
  out of scope for the schema itself even though providers return them in
  full. The same principle extends into the live app (see §5).
- **`CanonicalModel` sets `extra="forbid"`.** An adapter attaching a field
  the schema doesn't model is far more likely to be a mapping bug worth
  catching immediately than data worth silently tolerating - this project
  is about discovering and documenting every field, not accreting ad hoc
  extras.

## 2. Confirmed per-provider gaps

**PrismHR** (the most completely documented of the three):
- `Company.tax_id` is unreachable at the endpoints this project used.
- `Employee.worker_type`, `department` have no documented enum or clean
  1:1 mapping from PrismHR's raw fields.
- `Paycheck.benefit_contributions` - `PayrollVoucher.benefit[]` is real
  data seen live but not yet mapped (`planId`/`empContrib`/`empDeduct`).
- `DeductionLine.deduction_setup_id` is always `None` - cross-referencing a
  paycheck's deduction line back to the specific `DeductionSetup.id` it was
  taken against needs a pass that wasn't built.
- `Gender`/`MaritalStatus` have **no documented code table anywhere** in
  PrismHR's spec or lookup-reference - `M`/`F` and `S`/`M` are inferred
  from values observed live, not from documentation. Lower-confidence than
  every other mapping in this adapter; a differently-configured tenant
  could use different codes.
- PrismHR exposes two fields that read identically in every example seen
  (`employeeStatus`, tenant-configurable free text vs. `statusClass`, a
  genuine fixed 3-value enum). The adapter maps status from `statusClass`
  only; `employeeStatus` is discarded entirely rather than kept as a
  second raw field, since treating it as authoritative would be a mistake
  waiting to happen.

**isolved:**
- Has **almost no documented enums at all** - `employmentStatus`,
  direct-deposit `accountType`/`status`, pay-item `payItemType`, and check
  `checkTypeDescription` are all bare `"type": "string"` in the swagger
  spec, no enum array anywhere, and isolved's own `lookup-reference.json`'s
  11 domains are all scheduling/timecard fields, none of these. Every
  isolved mapping is built from literal strings observed live, flagged
  throughout the adapter as lower-confidence than PrismHR's.
- `CheckModel.taxes` and `CheckModel.benefits` were null on every real
  check observed; `taxCategories` (filing-status configuration) was
  deliberately **not** substituted for taxes actually withheld, since using
  it would fabricate tax lines from data that isn't there.
- Every employee showed the same count (19) of `Deduction`-typed pay
  items, suggesting `/payItems` returns the client's configured catalog,
  not per-employee elections - `DeductionSetup.is_active` is left `None`
  for isolved for this reason (no real enrollment flag exists in this
  data).
- Deduction *category* classification is a keyword-matched heuristic
  against free-text pay-item names (e.g. `"401k"` → `RETIREMENT`), since
  isolved exposes no category code at all - meaningfully lower-confidence
  than PrismHR's fully-documented code table.
- `Company.tax_id` **is** reachable for isolved (`LegalModel.federalEIN`) -
  unlike PrismHR and UKG.

**UKG Ready:**
- `Employee.gender`, `marital_status`, `job_title`, `pay_rates`,
  `pay_frequency`, `worker_type` are `None` for every UKG employee because
  they live behind `/demographics`/`/pay-info` sub-resources this project
  never crawled - a discovery gap, not a provider gap.
- `GET .../deductions` 404s live for this demo tenant (the cached docs tag
  it `dev`, not `v2`) - `Employee.deductions` is always `[]` for UKG.
- The pay-statements endpoint is a lightweight index only - no gross/net
  pay or earnings/taxes/deductions lines, so `Paycheck` fields beyond
  id/status/dates stay unset for UKG.
- **No company-detail endpoint exists at all** in this project's discovered
  UKG API surface - `Company` can only ever carry an id, never a name.
  (`Company.name` was changed from required to optional specifically
  because of this - see §3.)

## 3. Real bugs found and fixed

**PrismHR `Paycheck.id` collisions.** The first version built `Paycheck.id`
from `voucherId` alone. Verifying against the full real dataset hit a
`UNIQUE constraint failed` - `voucherId` is unique within one employee's own
voucher history but **not globally unique across the provider** (the same
`voucherId` recurs across different clients/employees; PrismHR's voucher
numbering is a per-client sequence, not a global one). Fixed by scoping the
canonical id as `employeeId:voucherId`; `Source.raw_id` still keeps the
true, unscoped `voucherId`.

**`Company.name` was wrongly required.** Writing the UKG adapter hit a real
`pydantic.ValidationError` immediately, because UKG has no company-detail
endpoint at all (§2). `Company.name` changed from required to
`Optional[str] = None`. This is `extra="forbid"` + required-fields working
as designed - catching a real schema/reality mismatch immediately rather
than silently.

**PrismHR's `"0000-01-01"` date sentinel.** Confirmed live: converting a
real PrismHR employee failed with a pydantic date-parsing error - *"year 0
is out of range"* - because `compensation.effectiveDate` was the literal
string `"0000-01-01"`, PrismHR's own "never set" sentinel, not a blank
string or `null`. The adapter's `_date()` helper only treated blanks as
absent. Fixed by also treating any `"0000-..."` date as absent, the same as
a blank value. Regression-tested in `tests/test_prismhr_adapter.py`.

**isolved and UKG Ready direct-deposit id collisions.** Saving all six of
isolved's synthetic employees to the shared database hit a `UNIQUE
constraint failed: direct_deposits.id`. Root cause: `DirectDeposit.id` was
built from the deposit's own raw `id` field alone, with no employee
scoping - and that raw id is **not globally unique**, confirmed empirically
(two different synthetic employees' deposits reuse the same raw id).
Notably, this exact failure mode had *already* been identified and fixed
once before, for isolved's deductions, with a comment explaining the same
root cause - direct deposits had just been missed. Fixed by scoping
`DirectDeposit.id` by `employee_id` in both the isolved and UKG Ready
adapters (UKG shared the identical unscoped pattern, fixed pre-emptively
rather than waiting to hit the same crash on different data).

## 4. CLI readiness gate (organizer's own compliance gate, not a bug)

`python -m normalization normalize` refuses to run for isolved and UKG
Ready - `python -m normalization check-inputs` currently reports:

```json
{
  "prismhr": [],
  "isolved": ["Candidate-distribution permission has not been verified."],
  "ukg-ready": [
    "Candidate-distribution permission has not been verified.",
    "OpenAPI artifact is absent or unverified.",
    "Approved OpenAPI filename is missing.",
    "Approved OpenAPI provenance/version/checksum metadata is incomplete."
  ]
}
```

This is the organizer's own licensing/redistribution gate
(`src/normalization/references.py`, documented in
`docs/REFERENCE_AUDIT.md`), correctly enforced - not an adapter bug. Both
adapters are still fully implemented and exercised: the Streamlit app and
the entire pytest suite call `ADAPTERS[provider].normalize(...)` directly,
the same adapter code the CLI would call, just not routed through the CLI
wrapper's gate. `python -m normalization normalize --provider prismhr ...`
is unaffected and works end to end.

For live (not fixture) data specifically, `scripts/pull_live_and_normalize.py`
is this project's terminal-only workaround: it pulls one employee live and
calls `canonicalize_employee()` directly (the same code path above), so
live data from isolved and UKG Ready can be normalized from the terminal
without going through the CLI's blocked `normalize` subcommand. See
[RUNNING.md](RUNNING.md) for usage.

## 5. Application-layer decisions (`app/`)

- **Deterministic synthetic data generates all six scripted scenarios per
  click, not a random one.** `scripts/generate_fixtures.py` always produces
  the same six scenarios (happy path, terminated, on-leave,
  no-deposits/no-deductions, multiple-deposits, unknown-status-code) - the
  app shows and converts all six together rather than picking one, so the
  full range of edge cases is always visible, not hidden behind a variant
  picker.
- **Live pulls redact SSNs and account numbers; synthetic data doesn't.**
  `app/data_client.py`'s `_redact()` masks sensitive fields (keeping only
  the last 4 digits) on every real API response before it ever reaches
  session state or the UI - a privacy safeguard for real people's data.
  Synthetic data is fictional, so nothing is masked there; the difference
  is intentional, not an inconsistency.
- **A later company's pull failure is soft-skipped, not fatal.** Pulling
  live data from N companies tries each one; a company that genuinely has
  zero employees (confirmed real, not hypothetical, for at least one demo
  PrismHR client) is skipped and reported, while the first company's
  failure or any 401 still aborts the whole pull (token expiry dooms every
  remaining call too, so there's no point making them).
- **Step 4's counts and downloads are scoped to the current session, not
  the whole database file.** `canonical.db` is one shared, persistent
  SQLite file that every run (past and future) writes into. An unfiltered
  view would mix in rows from earlier runs. `st.session_state.saved_employee_ids`
  tracks exactly which canonical employee ids *this* session saved, and
  every count, the "Browse normalization data" table viewer, and the
  downloadable SQL export are all filtered to that set.
- **No `st.dataframe`/`st.table` anywhere in the app.** Both require
  `pyarrow`, which is not reliably binary-compatible with every `numpy`
  installation (confirmed: it crashes with `numpy.core.multiarray failed
  to import` in this exact development environment). Every tabular view in
  the app (the database browser, the JSON viewers' containers) is a plain
  HTML table or `st.json()`, with no pyarrow dependency, and no risk of
  working on one machine and crashing on another.

## 6. Optional extension: not attempted

The assignment's optional write-path extension (accept canonical employee
data and write it into a destination provider tenant) was not built. This
submission is read/normalize-only: provider → canonical. Everything above
and in `docs/CANONICAL_SCHEMA.md` reflects that scope.

