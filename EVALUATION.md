# Evaluation rubric

The assessment measures reasoning and implementation, not the number of frameworks
or the visual polish of an optional UI. Score only against the approved input pack
and disclosed scope. Assessors must distinguish unavailable evidence from defects.

| Area | Points | Strong evidence |
| --- | ---: | --- |
| Canonical model and boundaries | 20 | Coherent company/employee/payroll schemas, candidate-designed enums, scoped identity and relationships, validation and versioning rationale |
| Transformation and semantic correctness | 30 | Nine supported paths, evidenced mappings, correct units/status/categories, precise money, explicit missing/unknown behavior, no loss of provenance |
| Contract discovery and evidence | 15 | Endpoint/schema inventory, field-level citations, lookup provenance, uncertainties and unsupported concepts recorded |
| Mock generation and testing | 20 | Deterministic contract-valid fixtures, separate adversarial cases, assertions for conversions and relationships, equivalence and rerun checks |
| Engineering and reproducibility | 10 | Understandable adapter boundary, useful diagnostics, local documented commands, clean-clone execution, no secrets or live service requirement |
| Communication and responsible AI use | 5 | Honest limitations/timebox, concise decisions, useful AI disclosure and independent verification |
| **Total** | **100** | |

## Scoring anchors

Within each area, award 0% for absent evidence; about 25% for a proposal without
working proof; about 50% for a working happy path with material omissions; about
75% for mostly correct behavior with limited gaps; and 100% for robust,
well-supported behavior across the approved scope. Use intermediate values as
appropriate. Record the exact test, output, or design decision supporting a score.

For the 30 transformation points, use: supported provider/entity coverage (9),
duration conversion (5), status/category interpretation (5), missing/unknown handling
(4), money/date correctness (4), identity/provenance (3). If the approved pack lacks
a duration field, use an explicitly illustrative unit-bearing domain test and
record that the provider field integration remains unassessed.

## Review process

1. Follow submission commands from a clean environment and regenerate fixtures.
2. Review mapping citations before evaluating numeric or category expectations.
3. Exercise unknown codes, absent/null fields, precision boundaries, and identity
   collisions. Any assessor-generated fixtures must follow the supplied contracts
   and disclosed semantics; maintain them outside this starter repository.
4. Review one equivalent business scenario across all providers and one uncertain
   mapping. Ask the candidate to explain their evidence and failure policy.
5. Record category scores, uncovered cases, strengths, and improvement priorities.

Do not reward invented provider codes, unsupported unit claims, fabricated source
citations, or passing tests that merely repeat the implementation. Any ungrounded
mapping earns no correctness credit for that mapping. Discuss integrity concerns
with the candidate before a hiring decision. No automatic hiring cutoff is set here.

No hidden fixtures, answer key, canonical schema, or completed transformations
are included in this repository. The rubric is intentionally candidate-visible.
