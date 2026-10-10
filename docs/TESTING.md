# Test expectations

Write tests with explicit expected meaning. The included tests validate only
starter plumbing and deliberate unimplemented boundaries; replace or extend them.

| Dimension | Required evidence |
| --- | --- |
| Coverage | Company, employee, payroll for each approved provider: nine paths |
| Shape | Generated valid payloads validate against the relevant supplied response schemas |
| Units | Evidence-based duration conversions; fractions, boundaries, missing/conflicting units, rounding |
| Enums | Known meanings, unseen codes, wrong domain, distinct codes that must not collapse |
| Missingness | Absent, null, empty, zero, false, malformed and unsupported concepts remain distinguishable |
| Payroll | Decimal precision, currency policy, period/date policy, line categories where supported |
| Relationships | Cross-company/provider source-ID collisions, leading zeros, dangling references, duplicates |
| Equivalence | Independently generate equivalent business situations for all providers and compare canonical meaning |
| Reproducibility | Same seed reproduces fixtures; same inputs produce stable outputs and diagnostics |
| Isolation | Input mutation does not contaminate another transformation or provider |

Use contract-valid generated fixtures for normal cases. For malformed-input tests,
keep adversarial fixtures separate and describe exactly which source constraint
they violate. Unknown-code tests may deliberately violate a closed enum; label
that distinction. Never misrepresent an illustrative unit test as a documented
provider response. Validate references and schema support before claiming coverage.

Include a small end-to-end run generated from your own fixtures, with output and
diagnostic assertions. Exercise unsupported fields and unresolved mappings. A
snapshot alone is insufficient for semantic conversion or category interpretation.
Document test tooling and any local dependencies; live APIs must not be needed.
