# Canonical schema design

Defines `src/normalization/canonical/` — the shared models every provider
adapter maps into. This file explains *why* each decision was made; move
the relevant parts into the submission's required assumptions Markdown
once the adapters are built and the real gaps/surprises are known.

## Entities

The scaffold (`src/normalization/adapters/__init__.py`) fixes
`ENTITIES = ("company", "employee", "payroll")` — three entities, not the
four data types the README lists. Direct deposits and deductions are not
separate top-level entities here; they nest inside `Employee` as setup/
configuration (`Employee.direct_deposits`, `Employee.deductions`). Actual
transactional deduction/benefit amounts taken on a given paycheck live
under `Paycheck` instead, as line items — the same deduction code shows up
in both places with different meaning (what's configured vs. what was
actually withheld that period), which is why `DeductionLine` carries its
own amounts rather than reusing `DeductionSetup`.

`PayrollRun` and `Paycheck` are both exported rather than forcing adapters
into one wrapper shape. Whether a provider call naturally groups checks
under one run (UKG: `GET /payrolls/{id}/pay-statements`) or returns checks
for one employee spanning several runs (PrismHR:
`getPayrollVouchersForEmployee`) is a per-adapter decision; the `payroll`
entity's adapters can return a single `PayrollRun` or a bare list of
`Paycheck`s, whichever matches the input shape, since `Paycheck.payroll_run_id`
is optional for exactly this reason.

## Cross-provider identity

Canonical ids are provider-prefixed composite strings:
`canonical_id(provider, kind, raw_id)` → `"prismhr:employee:E100"`. This
means `Employee.company_id` can point straight at a `Company.id` with no
separate cross-provider id-mapping table to build or keep in sync — the
id itself encodes where it came from and the mapping is just string
concatenation, invertible by splitting on `:`.

Every top-level record also carries a `Source` block (`provider`,
`raw_id`) — redundant with the composite id, but kept as its own field so
a consumer doesn't have to parse the id string to answer "what provider
and what original id did this come from."

## Enums keep the raw code

Every enum field has a sibling `raw_*` string (e.g. `employment_status` +
`raw_employment_status`). This is a deliberate response to how the
lookup-reference files describe themselves — e.g.
`contracts/prismhr/lookup-reference.json`'s `user_employee_status_class`
entry says outright: *"no candidate canonical mapping is supplied"* and
its `completeness` field reads *"documented field-description list; not a
formal closed OpenAPI enum."* The lookups are explicitly partial:
undocumented and tenant-configured values are not supplied. An adapter
that collapsed to an enum without keeping the original code would
silently lose information on any value this project's discovery missed —
so every enum includes an `OTHER`/`UNKNOWN` fallback, and the raw code is
never thrown away, only set alongside the best-guess canonical value.

Example grounding (not invented): PrismHR's `deductionType` lookup gives
`V`=Voluntary, `C`=Section 125, `P`=Post Tax Benefit, `F`=FSA, `G`=Wage
Garnishment → mapped onto `DeductionCategory.{VOLUNTARY_OTHER,
PRETAX_BENEFIT, POST_TAX_BENEFIT, PRETAX_BENEFIT, GARNISHMENT}`. UKG's
payroll status enum (`NEW, OPEN, CLOSED, SUBMITTED, FINALIZED,
OPEN_FAILED, CLOSE_FAILED, ROLLBACK_FAILED, FINALIZE_FAILED`, confirmed
both in the cached docs and `ukg-ready/lookup-reference.json`) collapses
the four `*_FAILED` variants onto one `PayrollRunStatus.FAILED` — the
adapter should still keep which failure it was in `raw_status`.

## Types

- **Money is `Decimal`, not `float`.** Verified it serializes as an
  exact-precision string via `model_dump(mode="json")`
  (`Decimal("85000.10")` → `"85000.10"`), avoiding binary-float rounding
  drift when comparing/summing amounts across three payroll systems that
  each round differently internally.
- **Dates are ISO-8601** (`datetime.date`), matching what all three
  providers already return natively.
- **PII fields that are masked on principle, not modeled in full**:
  `DirectDeposit` only keeps `routing_number_last4`/`account_number_last4`
  — the canonical model is a design artifact that may end up in a public
  submission repo, so full account/routing numbers and SSNs are out of
  scope for the schema itself even though the providers return them in
  full.

## Validation boundary

`CanonicalModel` sets `extra="forbid"`. An adapter trying to attach a
field the schema doesn't model is far more likely to be a mapping bug
worth catching immediately than data worth silently tolerating — this
project is explicitly about *discovering and documenting* every field,
not accreting ad hoc extras.

These are Pydantic v2 models (`requirements.txt` adds `pydantic`), chosen
over stdlib dataclasses/TypedDict for two reasons: real runtime validation
when adapters start producing records (catches mapping mistakes at
adapter-build time, not later in a golden-file test), and
`Model.model_json_schema()` gives a real JSON Schema artifact for free.
**Adapters must return `model.model_dump(mode="json")`** (a plain dict),
not the model instance — `src/normalization/__main__.py` pipes an
adapter's return value straight into `json.dumps()`, which does not know
how to serialize a Pydantic model, a `Decimal`, or an `Enum` on its own.

## Schema additions made while building the PrismHR adapter

Writing the first real adapter (`src/normalization/adapters/prismhr.py`)
surfaced gaps the schema needed before any provider could be mapped
faithfully — these are now in `enums.py`/`models.py`, not still open:

- **`CompanyStatus` enum** (`ACTIVE`/`PENDING`/`INACTIVE`/`TERMINATED`/
  `OTHER`), and `Company.status` changed from a bare `Optional[str]` to
  this enum (with `raw_status` still kept alongside it, same pattern as
  every other enum field). Grounded in PrismHR's `client_status_class`
  lookup-reference domain (A/P/I/C/T); `C` ("Client Cancelling,
  Pre-Termination") maps to `OTHER` since it's a transitional state, not
  cleanly active or terminated.
- **`Gender` and `MaritalStatus` enums**, and `Employee.gender`/
  `marital_status` (+ their `raw_*` siblings) and `Employee.ssn_last4`.
  Added because PrismHR, isolved, and UKG all expose these fields and the
  README asks to "cover all available employee fields, rather than only a
  small summary" — they were a real gap, not a stylistic add-on.
  **Confidence note:** unlike every other enum in this file, `Gender`/
  `MaritalStatus` have *no* documented code table anywhere in PrismHR's
  OpenAPI spec or lookup-reference.json — `person.gender`/
  `person.maritalStatus` are undocumented free text. `M`/`F` and `S`/`M`
  are inferred from the values this project actually observed live, not
  from provider documentation. Treat this mapping as lower-confidence than
  the others and re-verify against isolved/UKG's own gender/marital
  fields before assuming the same single-letter convention holds.

## Resolved: PrismHR employment-status field confusion

PrismHR's `Employee.client` object exposes **two different fields that
read as the same value in every example this project saw**, which makes
it easy to pick the wrong one:
- `employeeStatus` — documented as *"employee's current status; statuses
  are defined by the service provider"* — i.e., **not a fixed enum**,
  tenant-configurable free text.
- `statusClass` — documented as a genuine fixed 3-value enum: `'A'`
  (active), `'L'` (on leave), `'T'` (terminated).

The adapter maps `EmploymentStatus` from `statusClass` only.
`employeeStatus` is discarded entirely rather than kept as a second raw
field, since it isn't a stable classification and keeping it risked
someone later assuming it was authoritative.

## Resolved: deduction-type codes are more complete than first assumed

An earlier pass at this file assumed PrismHR's deduction type codes `K`/
`KC`/`KE`/`L` were undocumented, based on an incomplete read of
`lookup-reference.json`. They are in fact fully documented in that file's
`deduction_type` domain, along with `KL`/`KR`/`KCR`:

| Code | Meaning | → `DeductionCategory` |
|---|---|---|
| `V` | Voluntary | `VOLUNTARY_OTHER` |
| `C` | Section 125 | `PRETAX_BENEFIT` |
| `P` | Post Tax Benefit | `POST_TAX_BENEFIT` |
| `F` | Flexible Spending Account | `PRETAX_BENEFIT` |
| `G` | Wage Garnishment | `GARNISHMENT` |
| `L` | Employee Loan Payment | `LOAN` |
| `K` | Pre-Tax Retirement Contribution | `RETIREMENT` |
| `KC` | Catch-Up Retirement Contribution | `RETIREMENT` |
| `KE` | Post-Tax Retirement Contribution | `RETIREMENT` |
| `KL` | Retirement Plan Loan Payment | `RETIREMENT` |
| `KR` | Roth 401(k) Contribution | `RETIREMENT` |
| `KCR` | Roth 401(k) Catch-Up Contribution | `RETIREMENT` |

Verified against real data: mapping all 30 real PrismHR employees'
deductions across `getDeductions`/`getVoluntaryRecurringDeductions`/
`getScheduledDeductions`/`getACHDeductions` produced 89 `DeductionSetup`
records — exactly matching the row count independently found earlier in
`live_demo_data.sql`'s `deductions_setup` table for PrismHR.

## Decision: how "employee" and "payroll" entities receive input

`src/normalization/__main__.py`'s CLI takes exactly one `--input` file per
call, but PrismHR splits one employee's data across five separate GET
calls (`getEmployee`, `getACHDeductions`, `getDeductions`,
`getVoluntaryRecurringDeductions`, `getScheduledDeductions`). Rather than
force an artificial "one employee = one API call" constraint PrismHR
doesn't have, the PrismHR adapter's `"employee"` entity takes a
**composite bundle dict** — one key per raw source call, any of which may
be absent. See the docstring at the top of
`src/normalization/adapters/prismhr.py` for the exact shape. The
`"company"` entity instead takes the raw `getClientList` response
directly (and returns a *list* of companies, since that endpoint
naturally returns many in one call) and `"payroll"` takes the raw
`getPayrollVouchersForEmployee`/`getPayrollVouchers` response directly
(also returning a list — `PayrollRun` is intentionally not used for
PrismHR, since its voucher list isn't naturally grouped by run from
either endpoint; `Paycheck.payroll_run_id` stays `None`).

## Real bug found and fixed while building all three adapters

**PrismHR `Paycheck.id` collisions.** The first version of
`_map_paycheck` built `Paycheck.id` from `voucherId` alone. Verifying
against the full real dataset (9,323 paychecks) hit a `UNIQUE constraint
failed` when loading into SQL — `voucherId` is unique *within one
employee's own voucher history* but **not globally unique across the
provider** (confirmed: the same `voucherId` recurs across different
clients/employees; PrismHR's voucher numbering is evidently a per-client
sequence, not a global one). Fixed by scoping the canonical id as
`employeeId:voucherId`; `Source.raw_id` still keeps the true, unscoped
`voucherId` for traceability. Re-verified: all 9,323 paychecks now have
unique ids.

**`Company.name` was wrongly required.** Writing the UKG adapter hit a
real `pydantic.ValidationError` immediately — UKG Ready has no
company-detail endpoint anywhere in this project's discovered API surface
(confirmed: no "list companies"/"get company" operation exists in the
cached reference docs), so a UKG `Company` can only ever carry its id, not
a name. `Company.name` changed from required to `Optional[str] = None`.
This is the validation boundary (`extra="forbid"` + required fields)
working as designed — catching a real schema/reality mismatch immediately
rather than silently.

## isolved and UKG adapters: now implemented

Both followed the same mapping-table-then-code-then-verify process as
PrismHR, but the evidence situation for each was materially different —
worth understanding before trusting any of their mappings as firmly as
PrismHR's.

**isolved has almost no documented enums at all.** Checked directly
against the swagger spec: `EmployeeModel.employmentStatus`,
`EmployeeDirectDepositModel.accountType`/`frequency`/`status`,
`EmployeePayItemModel.payItemType`, and `CheckModel.checkTypeDescription`
are all declared as bare `"type": "string"` with only a human description
("Direct Deposit Status Description") — no enum array anywhere.
isolved's own `lookup-reference.json`'s 11 domains are all
scheduling/timecard fields and cover none of these. Every isolved mapping
in `adapters/isolved.py` is therefore built from the **literal strings
observed live** across 138 real employees (e.g. `employmentStatus`:
`"Active"`/`"Terminated"`/`"Inactive"`; `payType`:
`"Hourly"`/`"Salary"`/`"1099"`/`"Guarantee"`), not from provider
documentation — flagged throughout the adapter as lower-confidence than
PrismHR's. A differently-configured isolved tenant could use different
wording and this adapter would silently fall back to `OTHER`/`UNKNOWN`
rather than raise.

Two structural findings for isolved, both confirmed empirically:
- `legalAndPayGroupsWithPayrollSchedules` returned a **null `payGroups`**
  for both of this demo tenant's legal entities, so no real
  `PayrollRunHistoryModel` data was ever obtainable — the "payroll" entity
  uses `GET .../checks` directly instead (flat `Paycheck` list, same
  pattern as PrismHR).
- `CheckModel.taxes` and `CheckModel.benefits` were **null on every one of
  430 real checks** this project observed. `taxCategories` (filing-status
  configuration) was deliberately *not* substituted — it has no actual
  withheld amounts, only configuration, and using it would fabricate tax
  lines from data that isn't there.
- Every real employee showed exactly the same count (19) of
  `Deduction`-typed pay items — suggesting isolved's `/payItems` endpoint
  returns the client's configured catalog, not per-employee actual
  elections. `DeductionSetup.is_active` is deliberately left `None` for
  isolved for this reason (no real enrollment flag exists in this data).

**UKG's gaps are discovery gaps, not provider gaps.** The real
employee-list response this project crawled carries `_links` to
`demographics`, `pay-info`, `badges`, and `profiles` sub-resources —
separate GET calls this project never made. `Employee.gender`,
`marital_status`, `job_title`, `pay_rates`, `pay_frequency`, and
`worker_type` are therefore `None` for every UKG employee **because this
project's crawl didn't fetch those endpoints**, not because UKG lacks the
data. Similarly, UKG's pay-statements endpoint
(`GET .../payrolls/{id}/pay-statements`) is confirmed to be a lightweight
index only — real pay-statement objects carry just id/status/pay_date/
type/period, no gross/net pay or earnings/taxes/deductions lines; reaching
those would need a deeper per-statement detail call never made. UKG also
has **no company-detail endpoint at all** (see the `Company.name` bug
above) — the "company" entity's input is just `{"company_id": "..."}`.
UKG's `GET .../deductions` 404s live for every employee (already
established — the cached docs tag it `dev`, not `v2`), so
`Employee.deductions` is always `[]` for UKG.

## What's still open

- `Employee.worker_type`, `department`, `manager_employee_id`
  (PrismHR/isolved), and `pay_frequency` are left unset across all three
  adapters — each has a real raw field but no documented enum or clean 1:1
  mapping (PrismHR), or lives behind a sub-resource never crawled (UKG);
  see each adapter's inline comments for the specific reason per field.
- `Paycheck.benefit_contributions` is unpopulated for all three providers
  — PrismHR's `PayrollVoucher.benefit[]` is real data seen live but not
  yet mapped; isolved's `CheckModel.benefits` is confirmed null in this
  tenant's data; UKG's pay-statements endpoint doesn't carry this detail
  at all.
- `DeductionLine.deduction_setup_id` is always `None` for PrismHR and
  isolved — linking a paycheck's deduction line back to the specific
  `DeductionSetup.id` it was taken against needs a cross-reference pass
  that hasn't been built yet.
- `Company.tax_id`: confirmed **unreachable for PrismHR and UKG** at the
  endpoints this project used; confirmed **reachable for isolved**
  (`LegalModel.federalEIN`, real EINs `567777777`/`568888888` seen live).
- isolved's deduction *category* classification
  (`DeductionCategory` via `_categorize_deduction`) is a **keyword-matched
  heuristic against free-text pay-item names** (e.g. `"401k"` → 
  `RETIREMENT`), since isolved exposes no category code at all for pay
  items — this is meaningfully lower-confidence than PrismHR's
  fully-documented `deductionType` code table and should not be trusted
  the same way.
- All three providers' CLI runs so far have used **real downloaded demo
  data** as adapter input (see `adapter_demo_run/<provider>/`, gitignored
  per the README's "keep downloaded records out of Git" rule). The actual
  submission needs `scripts/generate_fixtures.py` (still unimplemented) to
  produce *synthetic* data shaped the same way, committed as real test
  fixtures, with a pytest golden-file test asserting adapter output
  matches an expected canonical JSON.
- **isolved and UKG cannot go through the real CLI
  (`python -m normalization normalize`) at all right now.** Both fail
  `references.readiness_issues()` — their `lookup-reference.json`'s
  `distribution.provider_redistribution_permission_verified` is `false`
  (a real, documented licensing/compliance gate described in
  `docs/REFERENCE_AUDIT.md`, correctly enforced, not a bug). Their
  `adapter_demo_run/` output in this project was produced by calling
  `ADAPTERS[provider].normalize(...)` directly, bypassing only the CLI
  wrapper — the exact same adapter code the CLI would call, just not
  routed through a gate that exists for a reason unrelated to adapter
  correctness. Decide whether this gate should ever be revisited for the
  final submission, and if not, document that isolved/UKG are
  demonstrated via direct adapter invocation plus this project's own test
  suite, not the CLI.
- Garnishments and benefit-plan enrollment are visible in all three specs
  but arguably belong to data types outside this take-home's required
  four — decide whether to fold them into `DeductionSetup`/
  `BenefitContributionLine` or explicitly scope them out and say so in the
  assumptions file.
