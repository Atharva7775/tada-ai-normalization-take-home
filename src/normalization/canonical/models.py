"""Canonical data models shared across PrismHR, isolved, and UKG Ready.

Design decisions (full rationale in docs/CANONICAL_SCHEMA.md):

- IDs are provider-prefixed composite strings via canonical_id(), so
  Employee.company_id always resolves against a Company.id with no
  separate cross-provider id-mapping table to keep in sync.
- Every top-level record keeps a `source` block (provider + the original
  provider-native id) so a canonical record always traces back to the
  exact source call that produced it.
- Every enum field keeps a sibling `raw_*` string with the original
  provider code. The lookup-reference files are explicitly partial, so
  collapsing to an enum without keeping the raw code would silently lose
  information on any code this project didn't discover.
- Money is Decimal, not float, to avoid binary-rounding drift when
  re-deriving totals across three differently-rounded payroll systems.
- These models validate shape; they are not what adapters return. The CLI
  in __main__.py pipes an adapter's return value straight into
  json.dumps(), so adapters must return `SomeModel.model_dump(mode="json")`
  (plain dict, Decimal/date/Enum already coerced to JSON-safe values), not
  the model instance itself.
- PayrollRun and Paycheck are both exported rather than forcing one
  wrapper shape, because whether a given provider call naturally groups
  checks under one run (e.g. a UKG payroll's pay-statements) or returns
  checks spanning several runs for one employee (e.g. PrismHR's
  getPayrollVouchersForEmployee) is an adapter-level decision, not a
  schema one.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    AllocationMethod,
    CompanyStatus,
    DeductionCategory,
    DirectDepositAccountType,
    DirectDepositStatus,
    EarningCategory,
    EmploymentStatus,
    Gender,
    MaritalStatus,
    PayBasis,
    PayFrequency,
    PaycheckStatus,
    PayrollRunStatus,
    WorkerType,
)


def canonical_id(provider: str, kind: str, raw_id: str) -> str:
    """Build a globally-unique canonical id from a provider-native id.

    Lets e.g. Employee.company_id reference a Company.id directly.
    """
    return f"{provider}:{kind}:{raw_id}"


class CanonicalModel(BaseModel):
    """Base for every canonical model.

    extra="forbid" is deliberate: an adapter passing an unmodeled field is
    very likely a mapping bug worth surfacing now, not silently-dropped
    data worth tolerating.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Source(CanonicalModel):
    """Traceability back to the exact provider record this came from."""
    provider: str  # "prismhr" | "isolved" | "ukg-ready"
    raw_id: str


class Address(CanonicalModel):
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class ContactInfo(CanonicalModel):
    email: Optional[str] = None
    mobile_phone: Optional[str] = None
    home_phone: Optional[str] = None
    work_phone: Optional[str] = None


class Company(CanonicalModel):
    id: str
    source: Source
    name: Optional[str] = None  # Optional: UKG Ready has no company-detail endpoint in this project's discovered API surface, so a UKG Company carries only its id - see adapters/ukg_ready.py
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None  # EIN, where exposed (e.g. isolved LegalModel.federalEIN)
    status: CompanyStatus
    raw_status: Optional[str] = None
    address: Optional[Address] = None


class PayRate(CanonicalModel):
    basis: PayBasis
    raw_basis: Optional[str] = None
    amount: Decimal
    effective_date: Optional[date] = None


class DirectDeposit(CanonicalModel):
    id: str
    source: Source
    account_type: DirectDepositAccountType
    raw_account_type: Optional[str] = None
    bank_name: Optional[str] = None
    routing_number_last4: Optional[str] = None
    account_number_last4: Optional[str] = None
    allocation_method: AllocationMethod
    raw_allocation_method: Optional[str] = None
    amount: Optional[Decimal] = None
    percent: Optional[Decimal] = None
    priority: Optional[int] = None
    status: DirectDepositStatus
    raw_status: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class DeductionSetup(CanonicalModel):
    id: str
    source: Source
    code: str
    description: Optional[str] = None
    category: DeductionCategory
    raw_category: Optional[str] = None
    calc_method: AllocationMethod
    raw_calc_method: Optional[str] = None
    amount: Optional[Decimal] = None
    percent: Optional[Decimal] = None
    start_date: Optional[date] = None
    stop_date: Optional[date] = None
    is_active: Optional[bool] = None


class Employee(CanonicalModel):
    id: str
    source: Source
    company_id: str  # == some Company.id, built via canonical_id()

    employee_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    preferred_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    raw_gender: Optional[str] = None
    marital_status: Optional[MaritalStatus] = None
    raw_marital_status: Optional[str] = None
    ssn_last4: Optional[str] = None  # never the full SSN, by design - matches DirectDeposit's *_last4 fields
    contact: ContactInfo = Field(default_factory=ContactInfo)
    address: Optional[Address] = None

    employment_status: EmploymentStatus
    raw_employment_status: Optional[str] = None
    worker_type: Optional[WorkerType] = None
    raw_worker_type: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    manager_employee_id: Optional[str] = None

    hire_date: Optional[date] = None
    rehire_date: Optional[date] = None
    termination_date: Optional[date] = None
    termination_reason: Optional[str] = None

    pay_frequency: Optional[PayFrequency] = None
    raw_pay_frequency: Optional[str] = None
    pay_rates: list[PayRate] = Field(default_factory=list)

    direct_deposits: list[DirectDeposit] = Field(default_factory=list)
    deductions: list[DeductionSetup] = Field(default_factory=list)


class EarningLine(CanonicalModel):
    category: EarningCategory
    raw_category: Optional[str] = None
    description: Optional[str] = None
    hours: Optional[Decimal] = None
    rate: Optional[Decimal] = None
    amount: Decimal


class TaxLine(CanonicalModel):
    code: str
    jurisdiction: Optional[str] = None
    employee_amount: Optional[Decimal] = None
    employer_amount: Optional[Decimal] = None


class DeductionLine(CanonicalModel):
    deduction_setup_id: Optional[str] = None  # links back to Employee.deductions[].id when resolvable
    code: str
    employee_amount: Optional[Decimal] = None
    employer_amount: Optional[Decimal] = None  # employer match/contribution, when the provider reports it alongside


class BenefitContributionLine(CanonicalModel):
    code: str
    employee_amount: Optional[Decimal] = None
    employer_amount: Optional[Decimal] = None


class Paycheck(CanonicalModel):
    id: str
    source: Source
    employee_id: str
    payroll_run_id: Optional[str] = None  # None when the source call doesn't tie the check to a run (e.g. a per-employee voucher query)
    status: PaycheckStatus
    raw_status: Optional[str] = None
    check_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    gross_pay: Optional[Decimal] = None
    net_pay: Optional[Decimal] = None
    total_hours: Optional[Decimal] = None
    earnings: list[EarningLine] = Field(default_factory=list)
    taxes: list[TaxLine] = Field(default_factory=list)
    deductions: list[DeductionLine] = Field(default_factory=list)
    benefit_contributions: list[BenefitContributionLine] = Field(default_factory=list)


class PayrollRun(CanonicalModel):
    id: str
    source: Source
    company_id: str
    status: PayrollRunStatus
    raw_status: Optional[str] = None
    pay_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    paychecks: list[Paycheck] = Field(default_factory=list)
