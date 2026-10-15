"""Verifies the UKG Ready adapter against the synthetic fixtures in
tests/fixtures/ukg-ready/ (see scripts/generate_fixtures.py).

Same role as tests/test_prismhr_adapter.py, for UKG Ready: generate_fixtures.py
only ever writes raw fixture JSON to disk and never imports an adapter -
this file is what actually calls ADAPTERS["ukg-ready"].normalize() on that
data and checks the result. It runs only when this test suite runs (e.g.
`python -m unittest discover -s tests`), independently of and at a
different time than fixture generation.

Two structural gaps are asserted here deliberately, not glossed over (see
src/normalization/adapters/ukg_ready.py's module docstring for why):
- UKG has no company-detail endpoint at all in this project's discovered
  API surface, so every canonical Company has name=None by design - not
  a mapping failure.
- The pay-statements endpoint this project crawled is a lightweight index
  only (no gross/net pay or earnings/taxes/deductions), so every canonical
  Paycheck here has gross_pay=None/net_pay=None and empty line-item lists.
"""
import json
import unittest
from pathlib import Path

from normalization.adapters import ADAPTERS
from normalization.canonical import Company, Employee, Paycheck
from normalization.references import load_reference

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ukg-ready"

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


class UkgReadyAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = load_reference("ukg-ready")
        cls.adapter = ADAPTERS["ukg-ready"]
        cls.company_input = json.loads((FIXTURES / "company_input.json").read_text())
        cls.employees_input = json.loads((FIXTURES / "employees_input.json").read_text())
        cls.payroll_input = json.loads((FIXTURES / "payroll_input.json").read_text())

    @classmethod
    def _companies(cls):
        # UKG's "company" entity processes ONE minimal {"company_id": ...}
        # record per call and returns a single dict (never a list) - unlike
        # PrismHR/isolved, which take the whole raw list/envelope in one
        # call. company_input.json is itself a list of several such
        # single-company records, so the caller loops, not the adapter.
        return [cls.adapter.normalize("company", rec, cls.reference) for rec in cls.company_input]

    @classmethod
    def tearDownClass(cls):
        # For human inspection only, not for test assertions (see module
        # docstring): write the canonical output next to the raw input it
        # came from, in the same tests/fixtures/ukg-ready/ folder.
        # Regenerated fresh every time this test runs, so it can never
        # silently go stale against the adapter.
        companies = cls._companies()
        employees = [cls.adapter.normalize("employee", b, cls.reference) for b in cls.employees_input]
        paychecks = cls.adapter.normalize("payroll", cls.payroll_input, cls.reference)
        (FIXTURES / "company_output.json").write_text(json.dumps(companies, indent=2) + "\n")
        (FIXTURES / "employees_output.json").write_text(json.dumps(employees, indent=2) + "\n")
        (FIXTURES / "payroll_output.json").write_text(json.dumps(paychecks, indent=2) + "\n")

    def test_company_entity_produces_valid_canonical_companies(self):
        companies = self._companies()
        self.assertEqual(len(companies), 2)
        for c in companies:
            Company(**c)  # raises pydantic.ValidationError if it doesn't conform
            self.assertTrue(c["id"].startswith("ukg-ready:company:"))
            # No company-detail endpoint exists in this project's discovered
            # UKG API surface - name is None by design, not a mapping failure.
            self.assertIsNone(c["name"])

    def test_employee_entity_produces_valid_canonical_employees(self):
        employees = [self.adapter.normalize("employee", bundle, self.reference) for bundle in self.employees_input]
        self.assertEqual(len(employees), 6)
        for emp in employees:
            Employee(**emp)  # raises pydantic.ValidationError if it doesn't conform
            # GET .../deductions 404s live for every real UKG employee this
            # project observed - deductions is always empty by design.
            self.assertEqual(emp["deductions"], [])

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
            # "Leave of Absence" is not a value this project ever observed
            # live - proves the adapter falls back to UNKNOWN rather than
            # guessing ON_LEAVE for an unconfirmed status string.
            emp = by_variant["on_leave_or_undocumented"]
            self.assertEqual(emp["employment_status"], "UNKNOWN")
            self.assertEqual(emp["raw_employment_status"], "Leave of Absence")

        with self.subTest("no_deposits_no_deductions"):
            emp = by_variant["no_deposits_no_deductions"]
            self.assertEqual(emp["direct_deposits"], [])

        with self.subTest("multiple_deposits"):
            emp = by_variant["multiple_deposits"]
            self.assertEqual(len(emp["direct_deposits"]), 3)
            methods = {dd["allocation_method"] for dd in emp["direct_deposits"]}
            self.assertEqual(methods, {"FLAT_AMOUNT", "PERCENT_OF_NET", "REMAINING_BALANCE"})

        with self.subTest("unknown_status_code"):
            # "Furloughed" is not a real observed UKG value - proves the
            # adapter falls back to UNKNOWN instead of raising.
            emp = by_variant["unknown_status_code"]
            self.assertEqual(emp["employment_status"], "UNKNOWN")
            self.assertEqual(emp["raw_employment_status"], "Furloughed")

        # Every employee's company_id must resolve to a company this same
        # fixture's "company" entity actually produces.
        companies = self._companies()
        company_ids = {c["id"] for c in companies}
        for emp in employees:
            self.assertIn(emp["company_id"], company_ids)

    def test_payroll_entity_produces_valid_canonical_paychecks(self):
        paychecks = self.adapter.normalize("payroll", self.payroll_input, self.reference)
        self.assertEqual(len(paychecks), 13)
        for pc in paychecks:
            Paycheck(**pc)  # raises pydantic.ValidationError if it doesn't conform
            # The pay-statements endpoint this project crawled is a
            # lightweight index only - no amount fields at all, for any
            # real UKG pay statement observed.
            self.assertIsNone(pc["gross_pay"])
            self.assertIsNone(pc["net_pay"])
            self.assertEqual(pc["earnings"], [])

        statuses = [pc["status"] for pc in paychecks]
        self.assertEqual(statuses.count("OPEN"), 12)
        self.assertEqual(statuses.count("OTHER"), 1)  # the deliberately unrecognized "PENDING_REVIEW" status

    def test_none_input_still_raises_not_implemented(self):
        # Preserves the scaffolding contract tests/test_starter.py already
        # asserts for every provider.
        with self.assertRaises(NotImplementedError):
            self.adapter.normalize("employee", None, self.reference)


if __name__ == "__main__":
    unittest.main()
