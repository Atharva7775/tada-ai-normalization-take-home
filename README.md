# Tada AI · Data Normalization Take-Home

**Seven calendar days · About 12–16 focused hours · AI assistance welcome**

Build a local platform that normalizes company, employee, and payroll data from
**PrismHR, isolved, and UKG Ready** into a consistent model. Discover the provider
mappings, design your own canonical schemas and enums, generate synthetic test
data, and implement transformations that preserve the meaning of the source data.
Use any programming language or stack.

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
