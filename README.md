# Tada AI · Data Normalization Take-Home

**Seven calendar days · Provider-agnostic HR and payroll · AI-assisted engineering**

Build a local data normalization platform that turns provider-specific company,
employee, and payroll responses into one consistent, well-documented model.
Your job is to discover the mappings, design the canonical schema and enums,
and show that the transformations preserve meaning across providers.

> **Starter status: private reference pack; candidate handoff remains pending.**
> PrismHR's licensed 2025.09 derivative is included. At the organizer's explicit
> private-upload instruction, isolved's two Swagger version-6 snapshots and
> UKG Ready's cached HTML/schema references are now included, with partial
> documented enum references. Provider redistribution permission for isolved/UKG
> is still unverified. UKG's references are not an official OpenAPI contract.
> Provider-documented sample payloads are included and labeled illustrative.
> No customer exports, independently generated fixtures or implementation solution are supplied.
> The seven-day assessment begins only after candidate sharing and scope are approved.

## The product problem

Tada needs to use HR/payroll information without binding downstream workflows to
one provider's field names, identifiers, status codes, or measurement conventions.
Support **PrismHR, isolved, and UKG Ready** through separate adapters and a shared
canonical model. Demonstrate company-to-employee-to-payroll relationships,
traceable decisions, and predictable handling of imperfect source data.

## What you receive

| Provider | Contract location | Enum / lookup reference |
| --- | --- | --- |
| PrismHR | [OpenAPI 3.0.1 snapshot, API 2025.09](contracts/prismhr/openapi/prismhr-2025.09.openapi.json) | [Partial evidenced reference](contracts/prismhr/lookup-reference.json) |
| isolved | [Primary Swagger 2.0, API version 6](contracts/isolved/openapi/isolved-v6.swagger.json) | [Partial explicit enums](contracts/isolved/lookup-reference.json) |
| UKG Ready | [Cached HTML and JSON Schema reference pack](contracts/ukg-ready/README.md), not OpenAPI | [Partial explicit enums](contracts/ukg-ready/lookup-reference.json) |

PrismHR inclusion relies on its artifact license. isolved/UKG private inclusion
was explicitly authorized by the organizer after the permission gaps were disclosed.
Their provider redistribution permission and candidate sharing remain unverified.
Release materials to candidates **only when availability, rights and scope are confirmed**. Each provider receives exactly one
lookup-reference JSON, containing evidenced codes/meanings and source citations,
not additional API response files. Provider-documented payload examples are retained
in the contracts/reference pages; candidates still generate and validate their own
seeded test data. A reference may be intentionally incomplete; completeness
and missing domains must be explicit. See [reference rules](contracts/README.md)
and the [source and permission audit](docs/REFERENCE_AUDIT.md).

## What you build

1. **Discover and document mappings.** Identify relevant endpoints, response
   schemas, fields, identifiers, enums, and units. Link every factual mapping to
   a contract JSON Pointer or an approved lookup citation. Track unresolved facts.
2. **Design the canonical model.** Define your own company, employee, and payroll
   schemas, enums, identity rules, relationships, validation, schema versioning,
   and treatment of source provenance. No target schema or canonical enum list
   is prescribed. Explain the tradeoffs.
3. **Generate your own mock responses.** Create deterministic, seeded synthetic
   fixtures from the supplied contracts and lookup references. Validate their
   shapes against the contracts and retain a generation manifest. Generate
   adversarial invalid inputs separately and label them as such.
4. **Implement all nine provider/entity combinations.** Normalize company,
   employee, and payroll for all three providers. Separate provider extraction
   from shared validation and semantic conversion. Produce JSON outputs through
   a documented local CLI or an equivalent local API.
5. **Preserve meaning.** Address duration units, status and category semantics,
   missing/null/unknown values, money precision, dates/time zones, and scoped
   relationships. Demonstrate explicit decisions, not silent coercion.
6. **Prove behavior.** Add transformation, boundary, cross-provider equivalence,
   and deterministic regeneration tests. Include clear diagnostics for unsupported
   or ambiguous inputs. A successful starter test run does not complete the assignment.

Only claim coverage for endpoints/entities supported by the approved pack.
If a contract cannot represent a requested concept, document the gap and agree
scope with the organizer. Do not fabricate a real provider endpoint or code.

## Local quick start

This optional scaffold uses **Python 3.9+ and the standard library**, with no
credentials, live provider calls, container, cloud account, or package download.
You may use another stack; preserve the deliverables and replace the run commands.

```sh
python3 -m venv .venv
source .venv/bin/activate
PYTHONPATH=src python3 -m normalization list-providers
PYTHONPATH=src python3 -m normalization check-inputs
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

`check-inputs` deliberately exits **2** while the reference pack is incomplete.
It checks manifest readiness, not OpenAPI correctness or legal approval.
The adapters and fixture generator raise explicit `NotImplementedError` until
you implement them. Once ready, the example interface is:

```sh
PYTHONPATH=src python3 -m normalization normalize \
  --provider prismhr --entity employee \
  --input path/to/your-generated-response.json \
  --output path/to/your-normalized-output.json
```

The scaffold is scaffolding: it does not define the canonical output shape,
solve mappings, generate your test fixtures, or assert unsupported provider-specific units.

## Starter layout

```text
contracts/           Provider contracts/references, partial enums and provenance records
docs/                Scope, semantics, testing, discovery/design/submission templates
schemas/             Your canonical schemas and enums
src/normalization/   CLI, reference readiness checks, three unimplemented adapters
scripts/             Your fixture generator stub
fixtures/            Empty documented locations for your generated/adversarial data
tests/               Starter and reference-integrity checks; add transformation tests
```

See [CONTENTS.md](CONTENTS.md) for the complete file inventory.

## Suggested seven-day plan

| Day | Milestone | Reviewable evidence |
| --- | --- | --- |
| 1 | Inspect approved inputs and define scope | Discovery log, endpoint inventory, unresolved questions |
| 2 | Design the canonical model | Schemas/enums, relationship and precision decisions |
| 3 | Build deterministic mock generation | Contract-valid fixtures, seed and validation manifest |
| 4 | Complete the first provider end to end | Three entity transformations and tests |
| 5 | Add the remaining providers | Nine provider/entity paths and semantic mappings |
| 6 | Challenge assumptions and boundaries | Unknown-value, conversion, relationship and equivalence tests |
| 7 | Polish reproducibility and submission | Clean-clone run, limitations, AI log, short demo |

Plan for roughly **12–16 focused hours within seven calendar days**. Timebox your
work and record actual time. A transparent partial implementation is preferable
to overstated completeness; explain priorities and the next steps. UI, hosted
deployment, production provider authentication, ETL scheduling, and a database
are not required. See [scope](docs/SCOPE.md).

## How we evaluate and what to submit

The [100-point rubric](EVALUATION.md) rewards semantic correctness, model design,
evidence, tests, reproducibility, and engineering judgment. Read the
[submission checklist](SUBMISSION.md), [semantic requirements](docs/SEMANTICS.md),
and [test expectations](docs/TESTING.md) before building.

AI tools are welcome. You remain responsible for every mapping and behavior;
record meaningful assistance and verification in [your AI log](docs/AI_USAGE.md).
Use only tools approved for any restricted reference material.

Keep this repository and your submission **private**. Submit through the channel
specified by the organizer. Public publishing, collaborator invitations, and
distribution of provider materials require separate approval.
