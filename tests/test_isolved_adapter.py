"""Verifies the isolved adapter against the synthetic fixtures in
tests/fixtures/isolved/ (see scripts/generate_fixtures.py).

Same role as tests/test_prismhr_adapter.py, for isolved: generate_fixtures.py
only ever writes raw fixture JSON to disk and never imports an adapter -
this file is what actually calls ADAPTERS["isolved"].normalize() on that
data and checks the result. It runs only when this test suite runs (e.g.
`python -m unittest discover -s tests`), independently of and at a
different time than fixture generation.

isolved has almost no documented enums anywhere in its OpenAPI spec or
lookup-reference.json (every status/type field is declared as bare free
text - see src/normalization/adapters/isolved.py's module docstring), so
several expectations below reflect that lower-confidence, string-matched
mapping rather than a closed code table: notably "Inactive" maps to
UNKNOWN (undocumented meaning), and every real check in this project's
live data mapped to PaycheckStatus.OTHER regardless of its
checkTypeDescription, since isolved exposes no separate lifecycle-status
field - that behavior is asserted here deliberately, not glossed over.
"""
import json
import unittest
from pathlib import Path

from normalization.adapters import ADAPTERS
from normalization.canonical import Company, Employee, Paycheck
from normalization.references import load_reference

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "isolved"

# Must match the VARIANTS order in scripts/generate_fixtures.py - the Nth
# employee in employees_input.json corresponds to the Nth variant here.
VARIANT_ORDER = (
    "active_simple",
    "terminated",
    "on_leave_or_undocumented",
    "no_deposits_no_deductions",
    "multiple_deposits",
    "unknown_status_code",
)


class IsolvedAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = load_reference("isolved")
        cls.adapter = ADAPTERS["isolved"]
        cls.company_input = json.loads((FIXTURES / "company_input.json").read_text())
        cls.employees_input = json.loads((FIXTURES / "employees_input.json").read_text())
        cls.payroll_input = json.loads((FIXTURES / "payroll_input.json").read_text())

    @classmethod
    def tearDownClass(cls):
        # For human inspection only, not for test assertions (see module
        # docstring): write the canonical output next to the raw input it
        # came from, in the same tests/fixtures/isolved/ folder. Regenerated
        # fresh every time this test runs, so it can never silently go
        # stale against the adapter.
        companies = cls.adapter.normalize("company", cls.company_input, cls.reference)
        employees = [cls.adapter.normalize("employee", b, cls.reference) for b in cls.employees_input]
        paychecks = cls.adapter.normalize("payroll", cls.payroll_input, cls.reference)
        (FIXTURES / "company_output.json").write_text(json.dumps(companies, indent=2) + "\n")
        (FIXTURES / "employees_output.json").write_text(json.dumps(employees, indent=2) + "\n")
        (FIXTURES / "payroll_output.json").write_text(json.dumps(paychecks, indent=2) + "\n")

    def test_company_entity_produces_valid_canonical_companies(self):
        # isolved's "company" entity takes the whole raw /legals array in
        # one call and returns a list - unlike UKG, which processes one
        # company record per call (see test_ukg_ready_adapter.py).
        companies = self.adapter.normalize("company", self.company_input, self.reference)
        self.assertEqual(len(companies), 2)
        for c in companies:
            Company(**c)  # raises pydantic.ValidationError if it doesn't conform
            self.assertTrue(c["id"].startswith("isolved:company:"))
            self.assertIsNotNone(c["tax_id"])  # isolved's LegalModel.federalEIN is confirmed reachable, unlike PrismHR/UKG

    def test_employee_entity_produces_valid_canonical_employees(self):
        employees = [self.adapter.normalize("employee", bundle, self.reference) for bundle in self.employees_input]
        self.assertEqual(len(employees), 6)
        for emp in employees:
            Employee(**emp)  # raises pydantic.ValidationError if it doesn't conform

        by_variant = dict(zip(VARIANT_ORDER, employees))

        with self.subTest("active_simple"):
            emp = by_variant["active_simple"]
            self.assertEqual(emp["employment_status"], "ACTIVE")
            self.assertEqual(emp["raw_employment_status"], "Active")

        with self.subTest("terminated"):
            emp = by_variant["terminated"]
            self.assertEqual(emp["employment_status"], "TERMINATED")
            self.assertEqual(emp["raw_employment_status"], "Terminated")

        with self.subTest("on_leave_or_undocumented"):
            # isolved has no real "on leave" status observed anywhere in
            # this project's live data - "Inactive" is the closest real
            # value, and its meaning is undocumented, so the adapter maps
            # it to UNKNOWN rather than guessing ON_LEAVE or TERMINATED.
            emp = by_variant["on_leave_or_undocumented"]
            self.assertEqual(emp["employment_status"], "UNKNOWN")
            self.assertEqual(emp["raw_employment_status"], "Inactive")

        with self.subTest("no_deposits_no_deductions"):
            emp = by_variant["no_deposits_no_deductions"]
            self.assertEqual(emp["direct_deposits"], [])
            self.assertEqual(emp["deductions"], [])

        with self.subTest("multiple_deposits"):
            emp = by_variant["multiple_deposits"]
            self.assertEqual(len(emp["direct_deposits"]), 2)
            methods = {dd["allocation_method"] for dd in emp["direct_deposits"]}
            self.assertEqual(methods, {"FLAT_AMOUNT", "PERCENT_OF_GROSS"})

        with self.subTest("unknown_status_code"):
            # "Pending Review" is not a real isolved value - proves the
            # adapter falls back to UNKNOWN instead of raising.
            emp = by_variant["unknown_status_code"]
            self.assertEqual(emp["employment_status"], "UNKNOWN")
            self.assertEqual(emp["raw_employment_status"], "Pending Review")

        # Every employee's company_id must resolve to a company this same
        # fixture's "company" entity actually produces.
        companies = self.adapter.normalize("company", self.company_input, self.reference)
        company_ids = {c["id"] for c in companies}
        for emp in employees:
            self.assertIn(emp["company_id"], company_ids)

    def test_payroll_entity_produces_valid_canonical_paychecks(self):
        paychecks = self.adapter.normalize("payroll", self.payroll_input, self.reference)
        self.assertEqual(len(paychecks), 13)
        for pc in paychecks:
            Paycheck(**pc)  # raises pydantic.ValidationError if it doesn't conform
            if pc["gross_pay"] is not None:
                # Decimal must serialize as an exact string via model_dump(mode="json"), never a float.
                self.assertIsInstance(pc["gross_pay"], str)

        # isolved's CheckModel exposes no lifecycle-status field distinct
        # from checkTypeDescription (a check TYPE, not a status) - every
        # real check this project observed mapped to OTHER regardless of
        # type. Asserted explicitly so a future real mapping addition is a
        # deliberate change to this test, not a silent behavior shift.
        statuses = [pc["status"] for pc in paychecks]
        self.assertEqual(statuses.count("OTHER"), 13)

    def test_none_input_still_raises_not_implemented(self):
        # Preserves the scaffolding contract tests/test_starter.py already
        # asserts for every provider.
        with self.assertRaises(NotImplementedError):
            self.adapter.normalize("employee", None, self.reference)


if __name__ == "__main__":
    unittest.main()
