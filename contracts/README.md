# Provider input contracts

There are three provider folders and **one lookup-reference JSON per provider**.
PrismHR includes an Apache-2.0-declared 2025.09 OpenAPI snapshot derivative and
eight partial lookup domains with source citations. Its example annotations and
embedded response renderings were removed. The two remaining JSONs are authoring
templates with empty lookup domains. Their `openapi/PLACEHOLDER.md` notices are
not API contracts. See [the audit](../docs/REFERENCE_AUDIT.md) for provenance,
distribution evidence and missing permissions.

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
No sample employee, company, or payroll response is distributed by this starter.
