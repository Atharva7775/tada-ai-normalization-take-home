# Provider input contracts

There are three provider folders and **one lookup-reference JSON per provider**.
PrismHR includes an Apache-2.0-declared 2025.09 OpenAPI derivative and eight
partial lookup domains. isolved includes two version-6 Swagger snapshots and
11 partial enum domains. UKG Ready includes 381 cached HTML pages, an extracted
JSON Schema bundle and 15 partial enum domains; **it is not an OpenAPI contract**.
Provider-documented examples are included at the organizer's instruction, with
authentication token examples redacted. These are illustrative documentation,
not customer exports or a complete candidate fixture suite. Each reference preserves
raw values, cites source locations and leaves undocumented meanings null.

The organizer explicitly authorized isolved/UKG's private upload after the rights
gaps were disclosed. Their provider redistribution permission and candidate
sharing remain unverified. See [the audit](../docs/REFERENCE_AUDIT.md).

## Authoring a verified lookup reference

Use the existing JSON as a wrapper. `lookups` becomes an array of domain objects:
each has `domain`, `source_field_pointers`, `entries` (raw `code`, `meaning`,
`evidence_reference`), and `completeness`. Preserve the documented raw code type;
never silently convert an opaque string ID/code into a number. Use explicit
unknown/unverified markers outside the lookup values, not invented code entries.

`authoring_template` documents the structure only. Its nulls and bracketed markers
are **not real code values**. Remove it after supplying the verified reference.
Source pointers may refer to an approved spec or approved external lookup document;
record version, exact location and permission evidence in the readiness record.
Do not put canonical enums, guessed mappings, or mock API responses in this file.

Set `openapi.relative_path` to the exact approved filename under `openapi/`;
set `openapi.status`, `lookup_status`, and `distribution.status` to `verified`
only after an evidence-backed distribution and artifact review. Supply version/source/checksum and distribution
evidence. `check-inputs` detects missing files and basic metadata but does not
verify license terms, complete scope, schema syntax, checksum accuracy, or codes.

An incomplete verified lookup reference may remain intentionally partial when
documented and agreed; candidates must handle unknown codes and cite known ones.
Provider-documented employee/company/payroll examples may appear in the source
contracts and reference pages. Candidates must still generate their own seeded
fixtures, validate them against the contracts and add boundary/unknown-value cases.
