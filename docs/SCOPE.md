# Scope and acceptance boundaries

## Required

Local normalization of company, employee, and payroll responses for PrismHR,
isolved, and UKG Ready. Design a provider-independent canonical model and enums;
generate synthetic responses from approved source contracts; implement adapters,
validation, diagnostics, and tests. Preserve relationship identity and trace the
origin and meaning of mapped data. Document transport envelopes and whether
payroll represents a run, statement, payment, or another evidenced source concept.

You choose storage, output representation, batching, and the implementation stack.
The optional Python scaffold accepts a JSON payload and returns a JSON-serializable
result. That transport choice does not prescribe canonical fields or enums.

The submission must provide repeatable generation, normalization, and test commands.
The same inputs/configuration must produce equivalent normalized results; explain
ordering and any volatile metadata. Show that processing different companies or
providers does not merge entities because their source IDs happen to match.

## Out of scope

Live provider calls, authentication flows, infrastructure, scheduling, a production
database, hosted deployment, and a polished frontend. Payroll tax calculations,
legal compliance determinations, currency exchange, and guessing missing wages
are not required. Do not access real employee or customer data for this exercise.

## Reference gaps

The organizer must release an approved reference pack before starting the clock.
Candidates should surface gaps early, using the discovery log. When a requested
concept is absent or ambiguous, agree a documented scope adjustment, extension,
or explicit illustrative test with the organizer. An illustrative test proves
your domain conversion policy; it does not establish a provider's actual fields.
No extra-credit feature compensates for an unsupported semantic claim.
