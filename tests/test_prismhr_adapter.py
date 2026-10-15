"""Verifies the PrismHR adapter against the synthetic fixtures in
tests/fixtures/prismhr/ (see scripts/generate_fixtures.py).

This is the "trigger" discussed alongside generate_fixtures.py: that script
only ever writes raw fixture JSON to disk and never imports an adapter -
this file is what actually calls ADAPTERS["prismhr"].normalize() on that
data and checks the result. It runs only when this test suite runs (e.g.
`python -m unittest discover -s tests`), independently of and at a
different time than fixture generation - generating fixtures does not run
these tests, and running these tests does not regenerate fixtures.
"""
import json
import unittest
from pathlib import Path

from normalization.adapters import ADAPTERS
from normalization.canonical import Company, Employee, Paycheck
from normalization.references import load_reference

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "prismhr"

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


class PrismHRAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = load_reference("prismhr")
        cls.adapter = ADAPTERS["prismhr"]
        cls.company_input = json.loads((FIXTURES / "company_input.json").read_text())
        cls.employees_input = json.loads((FIXTURES / "employees_input.json").read_text())
        cls.payroll_input = json.loads((FIXTURES / "payroll_input.json").read_text())

    @classmethod
    def tearDownClass(cls):
        # For human inspection only, not for test assertions (see module
        # docstring): write the canonical output next to the raw input it
        # came from, in the same tests/fixtures/prismhr/ folder. Regenerated
        # fresh every time this test runs, so it can never silently go
        # stale against the adapter - there's nothing frozen to compare
        # against, it's just a byproduct you can open and read.
        companies = cls.adapter.normalize("company", cls.company_input, cls.reference)
        employees = [cls.adapter.normalize("employee", b, cls.reference) for b in cls.employees_input]
        paychecks = cls.adapter.normalize("payroll", cls.payroll_input, cls.reference)
        (FIXTURES / "company_output.json").write_text(json.dumps(companies, indent=2) + "\n")
        (FIXTURES / "employees_output.json").write_text(json.dumps(employees, indent=2) + "\n")
        (FIXTURES / "payroll_output.json").write_text(json.dumps(paychecks, indent=2) + "\n")

    def test_company_entity_produces_valid_canonical_companies(self):
        companies = self.adapter.normalize("company", self.company_input, self.reference)
        self.assertEqual(len(companies), 2)
        for c in companies:
            Company(**c)  # raises pydantic.ValidationError if it doesn't conform
            self.assertTrue(c["id"].startswith("prismhr:company:"))

    def test_employee_entity_produces_valid_canonical_employees(self):
        employees = [self.adapter.normalize("employee", bundle, self.reference) for bundle in self.employees_input]
        self.assertEqual(len(employees), 6)
        for emp in employees:
            Employee(**emp)  # raises pydantic.ValidationError if it doesn't conform

        by_variant = dict(zip(VARIANT_ORDER, employees))

        with self.subTest("active_simple"):
            emp = by_variant["active_simple"]
            self.assertEqual(emp["employment_status"], "ACTIVE")
            self.assertEqual(emp["raw_employment_status"], "A")

        with self.subTest("terminated"):
            emp = by_variant["terminated"]
            self.assertEqual(emp["employment_status"], "TERMINATED")
            self.assertEqual(emp["raw_employment_status"], "T")

        with self.subTest("on_leave_or_undocumented"):
            # PrismHR's "L" (on leave) never appeared anywhere in this
            # project's live-pulled sample across any real company this
            # project checked - this synthetic case is the only place this
            # mapping has ever actually been exercised end to end.
            emp = by_variant["on_leave_or_undocumented"]
            self.assertEqual(emp["employment_status"], "ON_LEAVE")
            self.assertEqual(emp["raw_employment_status"], "L")

        with self.subTest("no_deposits_no_deductions"):
            emp = by_variant["no_deposits_no_deductions"]
            self.assertEqual(emp["direct_deposits"], [])
            self.assertEqual(emp["deductions"], [])

        with self.subTest("multiple_deposits"):
            emp = by_variant["multiple_deposits"]
            self.assertEqual(len(emp["direct_deposits"]), 3)
            methods = {dd["allocation_method"] for dd in emp["direct_deposits"]}
            self.assertEqual(methods, {"FLAT_AMOUNT", "PERCENT_OF_GROSS", "REMAINING_BALANCE"})

        with self.subTest("unknown_status_code"):
            # "Z" is not a real PrismHR code - proves the adapter falls back
            # to UNKNOWN instead of raising on an unrecognized value.
            emp = by_variant["unknown_status_code"]
            self.assertEqual(emp["employment_status"], "UNKNOWN")
            self.assertEqual(emp["raw_employment_status"], "Z")

        # Every employee's company_id must resolve to a company this same
        # fixture's "company" entity actually produces - the cross-provider
        # linkage the README requires ("keep the company and employee
        # relationships so these records can be linked").
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
                # Decimal must serialize as an exact string via model_dump(mode="json"),
                # never a float - this is the precision guarantee docs/CANONICAL_SCHEMA.md commits to.
                self.assertIsInstance(pc["gross_pay"], str)

        statuses = [pc["status"] for pc in paychecks]
        self.assertEqual(statuses.count("FINALIZED"), 12)
        self.assertEqual(statuses.count("OTHER"), 1)  # the deliberately unrecognized "HELD" voucher status

    def test_none_input_still_raises_not_implemented(self):
        # Preserves the scaffolding contract tests/test_starter.py already
        # asserts for every provider - normalize() must still refuse a
        # missing payload rather than crash on it.
        with self.assertRaises(NotImplementedError):
            self.adapter.normalize("employee", None, self.reference)


if __name__ == "__main__":
    unittest.main()
