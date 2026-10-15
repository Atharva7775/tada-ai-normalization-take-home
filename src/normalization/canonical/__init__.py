"""Canonical schema shared by every provider adapter.

Adapters import from here, map provider fields onto these models (never
the reverse), and return `model.model_dump(mode="json")`. See models.py
for the field-level design decisions and docs/CANONICAL_SCHEMA.md for the
full rationale and provider-by-provider mapping notes.
"""
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
from .models import (
    Address,
    BenefitContributionLine,
    CanonicalModel,
    Company,
    ContactInfo,
    DeductionLine,
    DeductionSetup,
    DirectDeposit,
    EarningLine,
    Employee,
    PayRate,
    Paycheck,
    PayrollRun,
    Source,
    TaxLine,
    canonical_id,
)

__all__ = [
    "AllocationMethod",
    "CompanyStatus",
    "DeductionCategory",
    "DirectDepositAccountType",
    "DirectDepositStatus",
    "EarningCategory",
    "EmploymentStatus",
    "Gender",
    "MaritalStatus",
    "PayBasis",
    "PayFrequency",
    "PaycheckStatus",
    "PayrollRunStatus",
    "WorkerType",
    "Address",
    "BenefitContributionLine",
    "CanonicalModel",
    "Company",
    "ContactInfo",
    "DeductionLine",
    "DeductionSetup",
    "DirectDeposit",
    "EarningLine",
    "Employee",
    "PayRate",
    "Paycheck",
    "PayrollRun",
    "Source",
    "TaxLine",
    "canonical_id",
]
