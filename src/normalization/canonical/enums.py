"""Canonical enums shared across the PrismHR, isolved, and UKG Ready adapters.

Every enum here carries an OTHER (or UNKNOWN, for status fields) fallback
member. The provider lookup-reference.json files are explicitly partial -
undocumented and tenant-configured codes are not supplied - so an adapter
must never raise on an unrecognized source code. It maps to the fallback
member and the model keeps the original code on a sibling `raw_*` field
instead of discarding it. Values are grounded in the codes actually found
in contracts/*/lookup-reference.json and the provider specs, not invented.
"""
from enum import Enum


class EmploymentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ON_LEAVE = "ON_LEAVE"
    TERMINATED = "TERMINATED"
    PENDING = "PENDING"  # hired/onboarding, not yet active
    RETIRED = "RETIRED"
    UNKNOWN = "UNKNOWN"


class WorkerType(str, Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    SEASONAL = "SEASONAL"
    TEMPORARY = "TEMPORARY"
    CONTRACTOR = "CONTRACTOR"
    OTHER = "OTHER"


class PayBasis(str, Enum):
    HOURLY = "HOURLY"
    SALARY = "SALARY"
    COMMISSION = "COMMISSION"
    PIECE_RATE = "PIECE_RATE"
    OTHER = "OTHER"


class PayFrequency(str, Enum):
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    SEMIMONTHLY = "SEMIMONTHLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUALLY = "ANNUALLY"
    OTHER = "OTHER"


class DirectDepositAccountType(str, Enum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"
    PAY_CARD = "PAY_CARD"
    OTHER = "OTHER"


class AllocationMethod(str, Enum):
    """How a direct-deposit line or a deduction amount is calculated."""
    FLAT_AMOUNT = "FLAT_AMOUNT"
    PERCENT_OF_GROSS = "PERCENT_OF_GROSS"
    PERCENT_OF_NET = "PERCENT_OF_NET"
    REMAINING_BALANCE = "REMAINING_BALANCE"
    OTHER = "OTHER"


class DirectDepositStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PRENOTE = "PRENOTE"
    OTHER = "OTHER"


class DeductionCategory(str, Enum):
    """Coarse grouping a provider-specific deduction code maps into.

    E.g. PrismHR deductionType: V->VOLUNTARY_OTHER, C (Section 125) and
    F (FSA)->PRETAX_BENEFIT, P->POST_TAX_BENEFIT, G->GARNISHMENT.
    """
    PRETAX_BENEFIT = "PRETAX_BENEFIT"
    POST_TAX_BENEFIT = "POST_TAX_BENEFIT"
    RETIREMENT = "RETIREMENT"
    GARNISHMENT = "GARNISHMENT"
    LOAN = "LOAN"
    VOLUNTARY_OTHER = "VOLUNTARY_OTHER"
    OTHER = "OTHER"


class PayrollRunStatus(str, Enum):
    NEW = "NEW"
    OPEN = "OPEN"
    SUBMITTED = "SUBMITTED"
    FINALIZED = "FINALIZED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"  # collapses provider-specific *_FAILED variants, e.g. UKG's OPEN_FAILED/CLOSE_FAILED/ROLLBACK_FAILED/FINALIZE_FAILED
    OTHER = "OTHER"


class PaycheckStatus(str, Enum):
    OPEN = "OPEN"
    FINALIZED = "FINALIZED"
    VOID = "VOID"
    REISSUED = "REISSUED"
    OTHER = "OTHER"


class EarningCategory(str, Enum):
    REGULAR = "REGULAR"
    OVERTIME = "OVERTIME"
    BONUS = "BONUS"
    VACATION = "VACATION"
    SICK = "SICK"
    HOLIDAY = "HOLIDAY"
    OTHER = "OTHER"


class CompanyStatus(str, Enum):
    """E.g. PrismHR Client.statusClass: A->ACTIVE, P->PENDING, I->INACTIVE,
    T->TERMINATED, C (Client Cancelling, Pre-Termination)->OTHER (a
    transitional state that isn't cleanly active or terminated)."""
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    INACTIVE = "INACTIVE"
    TERMINATED = "TERMINATED"
    OTHER = "OTHER"


class Gender(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class MaritalStatus(str, Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"
