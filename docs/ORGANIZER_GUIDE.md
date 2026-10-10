# Organizer guide

## Release gate

This is a private starter, **not yet a complete candidate reference pack**.
PrismHR's existing integration snapshot is now included on the basis of its
explicit Apache 2.0 declaration, with modification notices and a partial lookup
reference. isolved and UKG Ready are still withheld; see
[the audit](REFERENCE_AUDIT.md). This artifact/license review does not certify
the complete candidate scope or the latest live API. Do not start the seven-day
clock until the approved scope and materials are ready. A private repository does not establish rights
to redistribute third-party contracts.

For each provider:

1. Obtain the actual applicable Swagger/OpenAPI artifact through an authorized
   source. Identify product, API version and supported company/employee/payroll scope.
2. Verify availability and redistribution terms for the intended candidate group,
   storage location and any approved AI tooling. Record the reviewer, date,
   evidence and exact permitted scope in `REFERENCE_READINESS.md`.
3. Store only the approved contract under its `openapi/` directory. Preserve its
   source bytes; record checksum and provenance. Review for embedded real data,
   secrets and unauthorized example records; replace/redact only with a documented
   approved derivative. Do not copy company integration repositories or customer data.
4. Populate the provider's **one** `lookup-reference.json` with verified domains,
   raw codes, meanings and citations. Document incomplete domains and version.
   Remove the illustrative authoring template once populated; no response payloads.
5. Replace placeholder readiness metadata with verified values and exact filenames.
   Run `check-inputs`, then independently validate OpenAPI syntax, scope, lookup
   accuracy and rights. The scaffold's check does not perform those validations.
6. Confirm any unavailable concepts and disclose scope adjustments consistently
   to every candidate. Supply the deadline/timezone and approved submission channel.

If rights or access cannot be confirmed, keep the placeholder. Candidates must
not scrape gated documentation or guess proprietary lookup codes to compensate.

## Review consistency

Use the visible rubric and the same approved reference pack for each candidate.
Keep any independent assessor fixtures and answer keys outside this starter.
Do not penalize unavailable semantics as though they were documented facts.
Evaluate the implementation, tests and reasoning within the disclosed timebox.
This repository does not implement automated candidate ranking or hiring decisions.

## Repository handling

The intended destination is the organizer's verified personal GitHub account,
with a newly created private repository and no overwrites. Do not add external
collaborators, distribute provider materials, or change visibility without an
approved preview and explicit authorization. The PrismHR artifact's Apache 2.0
license applies to that artifact and its derivatives; it does not license the
whole hiring repository or the other providers' materials.
