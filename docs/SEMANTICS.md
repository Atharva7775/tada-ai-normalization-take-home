# Semantic requirements

These are behaviors to design and prove, not a supplied canonical schema or mapping.

## Durations and units

Record units per source field from the approved evidence, including precision and
whether a value is elapsed time, a paid quantity, a clock timestamp, or another
concept. A duration is not a timestamp; a payroll amount is not a duration.
Define a canonical unit and rounding policy. Validate fractions, zero, negatives,
large values, missing units, and conflicting unit metadata. Preserve exactness
where practical and make lossy conversions observable.

General arithmetic may include 60 minutes per hour or 1,000 milliseconds per
second **only when the input field's unit is established**. No UKG Ready
millisecond field is confirmed by this starter. Do not infer units from provider
name, magnitude, field naming alone, or a plausible generated fixture. When
evidence is missing, report an unresolved mapping or unsupported conversion.

## Statuses and categories

Discover the provider's actual codes and meanings. Define your own canonical
categories and justify grouping, splitting, or preserving distinctions. Consider
employment state, worker classification, pay frequency, earnings/deductions/taxes,
or payroll lifecycle only where documented by the supplied pack. Do not assume
the same raw code has the same meaning across providers or lookup domains.
Unknown codes should retain their source meaning/context and produce a visible
diagnostic or explicit unknown representation, not silently become a familiar code.

## Missing and unknown data

Distinguish absent fields, explicit null, empty text, zero, false, unrecognized
codes, invalid values, and a concept not supported by the source. Define required
versus optional fields and your reject/quarantine/partial-result policy. Never
turn unknown hours into zero or infer employment status from an absent end date
unless approved evidence defines that behavior. Document raw-value retention.

## Identity and relationships

Preserve source identifiers and their provider/company/tenant scope. Treat IDs
as opaque; protect leading zeros. Resolve company/employee/payroll references,
or explicitly report dangling/ambiguous links. Define duplicate and rerun behavior.

## Money and dates

Explain currency, decimal precision, rounding and numeric parsing. Do not mix
currencies or infer a currency from a provider's brand. Define date-only versus
instant handling, offsets/time zones, invalid dates and payroll-period boundaries.
If a time zone or currency is absent, state your policy instead of guessing.

## Evidence and diagnostics

Each mapping should identify source endpoint, schema/field pointer, code domain,
verified unit, reference version and canonical decision. Diagnostics should carry
enough source identity and field context to investigate a failure without leaking
unnecessary personal data. Separate factual source evidence from candidate design
decisions and explicitly labeled illustrative assumptions.
