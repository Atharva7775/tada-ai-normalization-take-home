# Candidate tests

`test_starter.py` checks the scaffold, partial reference readiness and unimplemented
adapters. `test_reference_integrity.py` checks the included PrismHR artifact's
checksum/license, local schema references, documented-example inclusion and lookup citations,
plus the privately uploaded isolved/UKG manifests and exact enum citations.
These ten checks do not validate source-to-canonical semantics or certify a
complete OpenAPI document. As you implement the assignment, update the deliberate
unimplemented-adapter assertions and add meaningful behavior tests. See
`docs/TESTING.md`; passing these checks is not normalization coverage.
