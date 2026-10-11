# Tada AI · Data Normalization Take-Home

**Seven calendar days · About 12–16 focused hours · AI assistance welcome**

Build a local platform that normalizes company, employee, and payroll data from
**PrismHR, isolved, and UKG Ready** into a consistent model. Discover the provider
mappings, design your own canonical schemas and enums, generate synthetic test
data, and implement transformations that preserve the meaning of the source data.

## Reference materials

| Provider | Source specifications | Lookup reference |
| --- | --- | --- |
| PrismHR | [OpenAPI 3.0.1, API 2025.09](contracts/prismhr/openapi/prismhr-2025.09.openapi.json) | [Documented codes and meanings](contracts/prismhr/lookup-reference.json) |
| isolved | [Primary Swagger 2.0, API version 6](contracts/isolved/openapi/isolved-v6.swagger.json); [alternate snapshot](contracts/isolved/openapi/isolved-v6.alternate.swagger.json) for comparison | [Documented enum values](contracts/isolved/lookup-reference.json) |
| UKG Ready | [Cached reference pages](contracts/ukg-ready/reference-docs/index.html) and [extracted JSON schemas](contracts/ukg-ready/reference-schemas.json) | [Documented enum values](contracts/ukg-ready/lookup-reference.json) |

UKG Ready's material is cached HTML documentation and an extracted schema bundle,
**not an official Swagger/OpenAPI contract**. Read the pages for endpoint bindings,
parameters, response statuses, XML schemas, and opaque schema blocks. Use isolved's
primary snapshot consistently; do not mix schemas between its two snapshots.
The reference versions have not been verified against the latest live APIs.

The lookup files contain actual, cited source values. They are partial references;
undocumented meanings remain unknown, and tenant-configured lookup values are not
supplied. Discover the mappings and define your own canonical enums. Documented
sample payloads are retained as illustrative source examples; generate and validate
your own fixtures rather than treating those samples as exhaustive contracts.

**Reference status:** this repository is private. PrismHR's artifact license is
retained, and the organizer has approved sharing this reference pack with candidates.
The seven-day period begins with the organizer's approved handoff,
scope, deadline, and timezone. Keep materials and submissions private and use the
organizer-approved sharing channel and AI tools.

Source history and evidence remain in the [reference audit](docs/REFERENCE_AUDIT.md),
[isolved manifest](contracts/isolved/SOURCE_MANIFEST.json), and
[UKG manifest](contracts/ukg-ready/SOURCE_MANIFEST.json). Attribution/modification
notices and PrismHR's license stay alongside the specifications.

## Access live demo data

You can inspect live demo responses from all three providers to understand their
data and validate mapping assumptions. The organizer supplies the **API key
privately**; it is not included in this repository.

Send `POST https://tada-demo-provider-signin.onrender.com/signin` with an
`X-API-Key` header and a JSON body containing `tenant`:

```sh
curl -X POST 'https://tada-demo-provider-signin.onrender.com/signin' \
  -H "X-API-Key: $DEMO_SIGNIN_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"tenant":"ukg"}'
```

Set `DEMO_SIGNIN_API_KEY` locally to the key provided by the organizer. Change
`tenant` to `prism`, `isol`, or `ukg` to select the corresponding demo account.

| Tenant | Authentication returned | Demo identifiers returned |
| --- | --- | --- |
| `prism` | `auth.sessionId`; use it in the provider's `sessionId` header | `context.companies[].client_id` |
| `isol` | `auth.access_token` and the refresh token when issued; use `Authorization: Bearer <access_token>` | `context.companies[].client_id` and `legal_id` |
| `ukg` | `auth.access_token`; use `Authorization: Bearer <access_token>` | `context.companies[].company_id` |

Each response also includes the provider's `base_url`, `tenant_id`, token expiry
when supplied, and `usage.header_name` / `usage.header_prefix`. Use the returned
authentication and identifiers with the provider endpoints in the reference
materials. Retrieve company names, employees, and payroll records through those
provider APIs; company names and employee/payroll records are not returned by
the sign-in endpoint. Prism client IDs and isolved client/legal-entity IDs identify
the seeded demo companies available for exploration.

Call `/signin` again when authentication expires. A refresh token is returned
only if the provider issues one; Prism uses a session ID. The hosted service may
take longer on its first request after inactivity. See the
[sign-in service README](https://github.com/Niwant/demo-provider-signin) for the
response fields and error behavior.

Live access is optional for discovery. Keep fixture generation and submitted
tests deterministic and able to run locally without credentials or live services.
Use the demo accounts for inspection, and keep returned tokens and any downloaded
records out of Git and your submission.

## What to build

1. **Discover the contracts.** Identify endpoints, response schemas, identifiers,
   fields, code domains, units, and company/employee/payroll relationships. Cite
   exact source fields or schema pointers for factual mapping decisions and record
   unresolved questions.
2. **Design a canonical model.** Define company, employee, and payroll schemas,
   enums, identity scope, relationships, validation, versioning, and provenance.
   Explain your tradeoffs. No target schema or canonical enum list is prescribed.
3. **Generate synthetic responses.** Implement deterministic, seeded fixture
   generation from the supplied reference schemas. Validate normal fixtures and
   record seed, generator version, reference checksums, schema pointers, and
   validation results. Keep deliberately invalid cases separate and labeled.
4. **Implement normalization.** Cover all nine provider/entity combinations within
   the approved scope. Separate provider extraction from shared conversions and
   validation. Expose JSON input/output through a documented local CLI or API.
5. **Test and demonstrate behavior.** Show an end-to-end run, equivalent business
   situations across providers, repeatable generation, and useful diagnostics for
   ambiguous or invalid inputs.

Only claim support for concepts evidenced by the reference pack. If a requested
concept is absent or ambiguous, document the gap and agree scope with the organizer.
You choose the stack, storage, output representation, and batching. Live provider
calls, authentication, cloud infrastructure, a production database, a frontend,
and payroll tax calculations are not required. Use synthetic identities and data.

## Semantic requirements and tests

| Area | Required behavior and test cases |
| --- | --- |
| Durations | Establish units for each source field; distinguish elapsed time, paid quantities, and timestamps. Choose a canonical unit and precision/rounding policy. Test fractions, zero, negatives, large values, and missing/conflicting units. |
| Statuses and categories | Cite actual source codes and meanings; justify canonical grouping and preserve relevant distinctions. Test unknown values, wrong code domains, and codes that must remain distinct. |
| Missing data | Distinguish absent, null, empty, zero, false, malformed, unknown, and unsupported concepts. Define reject/partial-result behavior and avoid silent coercion. |
| Identity and relationships | Preserve opaque IDs and leading zeros, scope IDs by provider/company, and resolve or report dangling links. Test collisions, duplicates, and reruns. |
| Money and dates | Define currency, decimal precision, rounding, date-only versus instant handling, time zones, and period boundaries. Report missing currency/time-zone information explicitly. |
| Reproducibility | The same seed regenerates the same fixtures; the same inputs produce stable outputs and diagnostics. Processing one input must not mutate another input or provider's state. |

Infer units from field-specific evidence, not provider names, field names alone,
or numeric magnitude. Keep factual source evidence separate from your own design
decisions and illustrative assumptions. Make unsupported or lossy conversions
observable. Assertions should check expected meaning, relationships, and failure
behavior, including all supported provider/entity paths.

## Local quick start

The optional Python scaffold uses **Python 3.9+ and the standard library**. No
credentials or package downloads are needed. You may replace it with another
stack if you document equivalent setup, generation, normalization, and test commands.

```sh
python3 -m venv .venv
source .venv/bin/activate
PYTHONPATH=src python3 -m normalization list-providers
PYTHONPATH=src python3 -m normalization check-inputs
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

`check-inputs` currently exits **2** because the candidate reference pack remains
incomplete. It checks basic metadata readiness, not complete schema validity or
distribution approval. The three adapters and fixture generator deliberately
raise `NotImplementedError` until you implement them. The ten included checks cover
starter plumbing and source-reference integrity; add transformation tests and
update the assertions that expect unimplemented adapters as you build.

After implementing an adapter, use the scaffold interface:

```sh
PYTHONPATH=src python3 -m normalization normalize \
  --provider prismhr --entity employee \
  --input path/to/generated-response.json \
  --output path/to/normalized-output.json
```

The starter refuses to overwrite an existing output file. Provider choices are
`prismhr`, `isolved`, and `ukg-ready`; entity choices are `company`, `employee`, and
`payroll`. The CLI does not prescribe your canonical output shape.

```text
contracts/                  Source specifications, lookup facts, and provenance
docs/REFERENCE_AUDIT.md      Existing source and distribution evidence
src/normalization/          CLI, reference checks, and three adapter stubs
scripts/generate_fixtures.py Fixture generator stub
tests/                      Starter and reference-integrity tests
```

Create schema, fixture, shared-transform, and design-document locations as needed;
no empty documentation templates are required.

## Suggested seven-day plan

| Day | Focus |
| --- | --- |
| 1 | Inspect the approved inputs, discover endpoints, and record gaps. |
| 2 | Design canonical schemas, enums, relationships, and precision policies. |
| 3 | Build seeded fixture generation and schema validation. |
| 4 | Implement the first provider end to end. |
| 5 | Add the remaining providers. |
| 6 | Test conversions, unknown values, relationships, and equivalence. |
| 7 | Verify a clean-clone run and prepare the submission. |

Timebox your work and record actual hours. Be clear about incomplete scope,
priorities, and next steps.

## Submission

Submit a private repository URL and exact commit SHA, or an archive if requested
by the organizer. Include:

- Updated README with setup, fixture generation, normalization, validation, and
  test commands that work from a clean clone without live services.
- Canonical schemas/enums and a concise explanation of design decisions.
- Mapping evidence covering source endpoints/fields, codes, meanings, units,
  canonical decisions, reference versions, and unresolved questions.
- Seeded fixture generator, generation manifest, synthetic fixtures, and example
  outputs produced by your implementation.
- Meaningful transformation and boundary tests with results and uncovered cases.
- Supported scope, hours spent, limitations, assumptions, and next steps.
- Brief AI-use disclosure: tools used, meaningful assistance, verification, and
  corrected assumptions. You remain responsible for the submitted work.
- One end-to-end walkthrough and one ambiguous/invalid case. A short video is
  optional; a written walkthrough is sufficient.

Preserve source specifications and provenance; document any derivative changes.
Do not include credentials or real employee/payroll data. Assessment focuses on
semantic correctness, canonical model design, source evidence, tests,
reproducibility, and clear engineering decisions. Passing the starter checks alone
does not complete the assignment.
