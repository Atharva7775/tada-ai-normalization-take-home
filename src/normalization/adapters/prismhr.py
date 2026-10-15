"""PrismHR adapter: maps raw PrismHR API responses onto the canonical schema
in src/normalization/canonical/.

Spec: contracts/prismhr/openapi/prismhr-2025.09.openapi.json
Lookup reference: contracts/prismhr/lookup-reference.json

Input shape per entity (a deliberate design decision - see docs/CANONICAL_SCHEMA.md):

- "company": the raw response of GET /clientMaster/v1/getClientList
  (contains clientListResult.clientList[], possibly many clients in one
  call). Returns a LIST of canonical Company dicts, one per client -
  matches how the endpoint itself naturally returns a batch.

- "employee": PrismHR splits one employee's data across five separate GET
  calls (getEmployee, getACHDeductions, getDeductions,
  getVoluntaryRecurringDeductions, getScheduledDeductions), but
  __main__.py's CLI only supports one --input file. Rather than force an
  artificial "one employee = one API call" constraint PrismHR doesn't
  have, `response` for this entity is a composite bundle dict:
      {
        "profile": <raw getEmployee response, called with
                    options=Person,ContactInformation,Client,Compensation,DirectDeposit>,
        "ach_deductions": <raw getACHDeductions response>,
        "deductions": <raw getDeductions response>,
        "voluntary_deductions": <raw getVoluntaryRecurringDeductions response>,
        "scheduled_deductions": <raw getScheduledDeductions response>,
      }
  Any key may be omitted or None; this adapter treats every section as
  optional. Returns a single canonical Employee dict.

- "payroll": the raw response of either GET getPayrollVouchersForEmployee
  (one employee, many vouchers) or GET getPayrollVouchers (one client,
  many employees) - both return the same payrollVoucher[] shape, so one
  mapping function handles either. Returns a LIST of canonical Paycheck
  dicts. No PayrollRun wrapper: PrismHR's voucher list isn't naturally
  grouped by payroll run from either endpoint (Paycheck.payroll_run_id is
  None for exactly this reason - see models.py).

Known PrismHR quirks this adapter accounts for (see docs/CANONICAL_SCHEMA.md
for the full discovery log):
- The live API returns the voucher list under the key "payrollVoucher"
  (singular) even though the OpenAPI schema's declared JSON property name
  is "payrollVouchers" - the schema's xml:name override is what the server
  actually follows for JSON too.
- getEmployee returns every optional section as null unless you pass the
  matching comma-separated `options` keyword(s) - this adapter assumes the
  caller already requested the sections it reads (profile.person,
  .contactInformation, .client, .compensation, .directDeposit).
- Client.employeeStatus is explicitly documented as "defined by the
  service provider" (i.e. NOT a fixed enum) - the employment-status
  mapping below uses Client.statusClass instead, which IS a documented
  fixed 3-value enum (A/L/T). Don't substitute employeeStatus here even
  though it happened to read the same as statusClass in every example
  this project observed.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from normalization.canonical import (
    Address,
    AllocationMethod,
    CompanyStatus,
    ContactInfo,
    Company,
    DeductionCategory,
    DeductionLine,
    DeductionSetup,
    DirectDeposit,
    DirectDepositAccountType,
    DirectDepositStatus,
    EarningLine,
    EarningCategory,
    Employee,
    EmploymentStatus,
    Gender,
    MaritalStatus,
    PayBasis,
    PayRate,
    Paycheck,
    PaycheckStatus,
    Source,
    TaxLine,
    canonical_id,
)

PROVIDER = "prismhr"

# ---------------------------------------------------------------------------
# Enum translation tables. Every one of these is grounded in
# contracts/prismhr/openapi/...json field descriptions or
# contracts/prismhr/lookup-reference.json entries - see the module docstring
# and docs/CANONICAL_SCHEMA.md for the citation of each. Unrecognized codes
# fall back to the enum's OTHER/UNKNOWN member; the original code is always
# kept on the matching raw_* field, never discarded.
# ---------------------------------------------------------------------------

# Client.statusClass - documented fixed enum: "'A' (active), 'L' (on leave), or 'T' (terminated)"
_EMPLOYMENT_STATUS = {
    "A": EmploymentStatus.ACTIVE,
    "L": EmploymentStatus.ON_LEAVE,
    "T": EmploymentStatus.TERMINATED,
}

# ClientMaster.statusClass (company-level) - lookup-reference.json client_status_class domain
_COMPANY_STATUS = {
    "A": CompanyStatus.ACTIVE,
    "P": CompanyStatus.PENDING,
    "I": CompanyStatus.INACTIVE,
    "T": CompanyStatus.TERMINATED,
    "C": CompanyStatus.OTHER,  # "Client Cancelling, Pre-Termination" - transitional, not cleanly active or terminated
}

# Compensation.payMethod - documented: "'S' (salary), 'H' (hourly), 'C' (commission), or 'D' (driver)"
_PAY_BASIS = {
    "S": PayBasis.SALARY,
    "H": PayBasis.HOURLY,
    "C": PayBasis.COMMISSION,
    # "D" (driver) has no equivalent canonical basis - falls through to OTHER
}

# AchVoucher.accountType - documented: "'C' (checking account or pay card), 'S' (savings account), and IP (instant pay)"
_ACCOUNT_TYPE = {
    "C": DirectDepositAccountType.CHECKING,
    "S": DirectDepositAccountType.SAVINGS,
    "IP": DirectDepositAccountType.OTHER,  # instant pay has no dedicated canonical type
}

# AchVoucher.method - documented: F/P/FS/PN/B
_ALLOCATION_METHOD = {
    "F": AllocationMethod.FLAT_AMOUNT,
    "FS": AllocationMethod.FLAT_AMOUNT,  # "fixed, skip if can't take full amount" - still a flat amount, just with different overflow handling we don't model
    "P": AllocationMethod.PERCENT_OF_GROSS,
    "PN": AllocationMethod.PERCENT_OF_NET,
    "B": AllocationMethod.REMAINING_BALANCE,
}

# AchVoucher.status - documented: "'P' (Pre-notification), 'D' (Deposit Active), or 'I' (Deposit Inactive)"
_DIRECT_DEPOSIT_STATUS = {
    "P": DirectDepositStatus.PRENOTE,
    "D": DirectDepositStatus.ACTIVE,
    "I": DirectDepositStatus.INACTIVE,
}

# deductionType - fully documented in lookup-reference.json's deduction_type domain
_DEDUCTION_CATEGORY = {
    "V": DeductionCategory.VOLUNTARY_OTHER,       # Voluntary
    "C": DeductionCategory.PRETAX_BENEFIT,        # Section 125
    "P": DeductionCategory.POST_TAX_BENEFIT,      # Post Tax Benefit
    "F": DeductionCategory.PRETAX_BENEFIT,        # Flexible Spending Account (pretax)
    "G": DeductionCategory.GARNISHMENT,           # Wage Garnishment
    "L": DeductionCategory.LOAN,                  # Employee Loan Payment
    "K": DeductionCategory.RETIREMENT,            # Pre-Tax Retirement Contribution
    "KC": DeductionCategory.RETIREMENT,           # Catch-Up Retirement Contribution
    "KE": DeductionCategory.RETIREMENT,           # Post-Tax Retirement Contribution
    "KL": DeductionCategory.RETIREMENT,           # Retirement Plan Loan Payment
    "KR": DeductionCategory.RETIREMENT,           # Roth 401(k) Contribution
    "KCR": DeductionCategory.RETIREMENT,          # Roth 401(k) Catch-Up Contribution
}

# ScheduledDeduction.status - documented: "'A' (active), 'I' (inactive), or 'O' (one time)"
# This project's DeductionSetup models active-ness as a bool, not its own
# enum, so "O" (one-time) is treated as active=True (it does occur) with
# the original code kept on no sibling field since DeductionSetup has no
# raw_is_active - this is a lossy simplification worth flagging if
# one-time-vs-recurring distinction ever becomes load-bearing.
_SCHEDULED_DEDUCTION_ACTIVE = {"A": True, "I": False, "O": True}

# Gender - PrismHR's person.gender is a single-letter free-text field with
# NO documented enum in the OpenAPI spec or lookup-reference.json (unlike
# statusClass/payMethod/etc). M/F are inferred from every value observed in
# this project's live data, not from provider documentation - flagged as a
# lower-confidence mapping than the ones above.
_GENDER = {"M": Gender.MALE, "F": Gender.FEMALE}

# MaritalStatus - person.maritalStatus is likewise undocumented free text;
# "S" (single) is the only value this project has observed live. "M"
# (married) is a reasonable guess by convention but UNVERIFIED against any
# real PrismHR response - do not treat this mapping as confirmed.
_MARITAL_STATUS = {"S": MaritalStatus.SINGLE, "M": MaritalStatus.MARRIED}

# PayrollVoucher.status is documented as free text ("voucher status, such
# as printed") - NOT a fixed enum. "PRNT" (printed) is the only value this
# project observed live; FINALIZED is an inferred best guess (a printed
# check is presumably done processing), not a confirmed provider-documented
# mapping. Any other value falls back to OTHER with raw_status preserved.
_PAYCHECK_STATUS = {"PRNT": PaycheckStatus.FINALIZED}


def _dec(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _date(value: Any) -> Optional[str]:
    """Pass through PrismHR's already-ISO-8601 date strings; treat blanks as absent."""
    if not value:
        return None
    return value


# ---------------------------------------------------------------------------
# company
# ---------------------------------------------------------------------------

def _map_company(raw_client: Dict[str, Any]) -> Dict[str, Any]:
    client_id = raw_client.get("clientId")
    raw_status = raw_client.get("status")
    company = Company(
        id=canonical_id(PROVIDER, "company", client_id),
        source=Source(provider=PROVIDER, raw_id=client_id),
        name=raw_client.get("clientName"),
        legal_name=raw_client.get("legalName") or None,
        tax_id=None,  # not exposed by getClientList or getEmployee in this project's discovery - see docs/CANONICAL_SCHEMA.md "what's still open"
        status=_COMPANY_STATUS.get(raw_status, CompanyStatus.OTHER),
        raw_status=raw_status,
    )
    return company.model_dump(mode="json")


def _normalize_company(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    clients = ((response or {}).get("clientListResult") or {}).get("clientList") or []
    return [_map_company(c) for c in clients]


# ---------------------------------------------------------------------------
# employee
# ---------------------------------------------------------------------------
def _map_direct_deposits(employee_id: str, direct_deposit_block: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not direct_deposit_block:
        return []
    out = []
    for i, voucher in enumerate(direct_deposit_block.get("achVoucher") or []):
        raw_status = voucher.get("status")
        raw_method = voucher.get("method")
        raw_account_type = voucher.get("accountType")
        dd = DirectDeposit(
            id=canonical_id(PROVIDER, "directdeposit", f"{employee_id}:{i}"),
            source=Source(provider=PROVIDER, raw_id=f"{employee_id}:{i}"),
            account_type=_ACCOUNT_TYPE.get(raw_account_type, DirectDepositAccountType.OTHER),
            raw_account_type=raw_account_type,
            bank_name=voucher.get("bankName") or None,
            routing_number_last4=(voucher.get("transitNum") or "")[-4:] or None,
            account_number_last4=(voucher.get("accountNum") or "").replace("*", "")[-4:] or None,
            allocation_method=_ALLOCATION_METHOD.get(raw_method, AllocationMethod.OTHER),
            raw_allocation_method=raw_method,
            amount=_dec(voucher.get("amount")),
            percent=_dec(voucher.get("limit")) if raw_method == "P" else None,
            status=_DIRECT_DEPOSIT_STATUS.get(raw_status, DirectDepositStatus.OTHER),
            raw_status=raw_status,
        )
        out.append(dd.model_dump(mode="json"))
    return out


def _map_deduction_setup(employee_id: str, source_endpoint: str, index: int, code: Optional[str],
                          description: Optional[str], raw_category: Optional[str], amount: Any,
                          percent: Any, status_active: Optional[bool], start_date: Any, stop_date: Any) -> Dict[str, Any]:
    ded = DeductionSetup(
        id=canonical_id(PROVIDER, "deduction", f"{employee_id}:{source_endpoint}:{index}"),
        source=Source(provider=PROVIDER, raw_id=f"{employee_id}:{source_endpoint}:{index}"),
        code=code or "UNKNOWN",
        description=description or None,
        category=_DEDUCTION_CATEGORY.get(raw_category, DeductionCategory.OTHER),
        raw_category=raw_category,
        calc_method=AllocationMethod.OTHER,  # these endpoints don't expose a documented calc-method code distinct from usePercent (a bool) - see notes below
        raw_calc_method=None,
        amount=_dec(amount),
        percent=_dec(percent),
        start_date=_date(start_date),
        stop_date=_date(stop_date),
        is_active=status_active,
    )
    return ded.model_dump(mode="json")


def _map_deductions(employee_id: str, bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    for i, item in enumerate((bundle.get("ach_deductions") or {}).get("achDeductionSettings") or []):
        out.append(_map_deduction_setup(
            employee_id, "ach_deductions", i,
            code=item.get("accountType"), description=None, raw_category=None,
            amount=item.get("amount"), percent=None,
            status_active=(item.get("status") == "D"),  # AchVoucher.status reused here: D=Deposit Active
            start_date=None, stop_date=None,
        ))

    employee_deductions = ((bundle.get("deductions") or {}).get("employeeDeductions") or {}).get("deduction") or []
    for i, item in enumerate(employee_deductions):
        use_percent = bool(item.get("usePercent"))
        out.append(_map_deduction_setup(
            employee_id, "deductions", i,
            code=item.get("deductionCode"), description=item.get("description"),
            raw_category=item.get("deductionType"),
            amount=None if use_percent else item.get("amount"),
            percent=item.get("amount") if use_percent else None,
            status_active=None,  # this endpoint doesn't expose a status/active flag
            start_date=item.get("startDate"), stop_date=item.get("stopDate"),
        ))

    voluntary = ((bundle.get("voluntary_deductions") or {}).get("voluntaryDeduction") or {}).get("deduction") or []
    for i, item in enumerate(voluntary):
        use_percent = bool(item.get("usePercent"))
        out.append(_map_deduction_setup(
            employee_id, "voluntary_deductions", i,
            code=item.get("deductionCode"), description=item.get("description"),
            raw_category=item.get("deductionType"),
            amount=None if use_percent else item.get("amount"),
            percent=item.get("amount") if use_percent else None,
            status_active=None,
            start_date=item.get("startDate"), stop_date=item.get("stopDate"),
        ))

    for i, item in enumerate((bundle.get("scheduled_deductions") or {}).get("scheduledDeduction") or []):
        raw_status = item.get("status")
        out.append(_map_deduction_setup(
            employee_id, "scheduled_deductions", i,
            code=item.get("deductionCode"), description=item.get("checkStubDescription"),
            raw_category=None,  # this endpoint doesn't return deductionType
            amount=item.get("amount"), percent=None,
            status_active=_SCHEDULED_DEDUCTION_ACTIVE.get(raw_status),
            start_date=item.get("startDate"), stop_date=item.get("stopDate"),
        ))

    return out


def _map_pay_rates(compensation: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not compensation:
        return []
    raw_basis = compensation.get("payMethod")
    basis = _PAY_BASIS.get(raw_basis, PayBasis.OTHER)
    if raw_basis == "H":
        amount = compensation.get("hourlyPayRate") or compensation.get("hourlyPay")
    elif raw_basis == "S":
        amount = compensation.get("annualPay") or compensation.get("salary")
    else:
        amount = compensation.get("annualPay") or compensation.get("salary") or compensation.get("hourlyPayRate")
    dec_amount = _dec(amount)
    if dec_amount is None:
        return []
    rate = PayRate(
        basis=basis,
        raw_basis=raw_basis,
        amount=dec_amount,
        effective_date=_date(compensation.get("effectiveDate")),
    )
    return [rate.model_dump(mode="json")]


def _normalize_employee(bundle: Dict[str, Any]) -> Dict[str, Any]:
    profile_response = bundle.get("profile") or {}
    emp0 = (profile_response.get("employee") or [{}])[0] or {}

    employee_id = emp0.get("id")
    person = emp0.get("person") or {}
    contact_info = emp0.get("contactInformation") or {}
    client = emp0.get("client") or {}
    compensation = emp0.get("compensation") or {}

    company_id_raw = client.get("clientId") or (bundle.get("client_id"))
    raw_employment_status = client.get("statusClass")
    raw_worker_type = client.get("typeClass")
    raw_gender = person.get("gender")
    raw_marital = person.get("maritalStatus")
    raw_ssn = compensation.get("ssn")  # PrismHR already masks this server-side (e.g. "***-**-****")

    employee = Employee(
        id=canonical_id(PROVIDER, "employee", employee_id),
        source=Source(provider=PROVIDER, raw_id=employee_id),
        company_id=canonical_id(PROVIDER, "company", company_id_raw) if company_id_raw else "",
        employee_number=employee_id,
        first_name=emp0.get("firstName") or None,
        last_name=emp0.get("lastName") or None,
        middle_name=emp0.get("middleInitial") or None,
        preferred_name=emp0.get("preferredName") or None,
        date_of_birth=_date(person.get("birthDate")),
        gender=_GENDER.get(raw_gender, Gender.UNKNOWN) if raw_gender else None,
        raw_gender=raw_gender or None,
        marital_status=_MARITAL_STATUS.get(raw_marital, MaritalStatus.UNKNOWN) if raw_marital else None,
        raw_marital_status=raw_marital or None,
        ssn_last4=(raw_ssn or "").replace("*", "").replace("-", "")[-4:] or None,
        contact=ContactInfo(
            email=contact_info.get("emailAddress") or None,
            mobile_phone=contact_info.get("mobilePhone") or None,
            home_phone=contact_info.get("homePhone") or None,
        ),
        address=Address(
            line1=contact_info.get("addressLine1") or None,
            line2=contact_info.get("addressLine2") or None,
            city=contact_info.get("city") or None,
            state=contact_info.get("state") or None,
            postal_code=contact_info.get("zipcode") or None,
            country="USA" if contact_info.get("state") else None,  # PrismHR exposes no country field; inferred from the presence of a US state code
        ) if contact_info else None,
        employment_status=_EMPLOYMENT_STATUS.get(raw_employment_status, EmploymentStatus.UNKNOWN),
        raw_employment_status=raw_employment_status,
        worker_type=None,  # typeClass has no documented enum (see module docstring) - left unset rather than guessing
        raw_worker_type=raw_worker_type or None,
        job_title=client.get("jobCode") or None,
        department=None,  # PrismHR's department concept (codeFiles/getDepartmentCode) isn't present on the Employee.client object itself
        manager_employee_id=None,  # not exposed in this project's discovered employee fields
        hire_date=_date(client.get("firstHireDate")),
        rehire_date=_date(client.get("lastHireDate")) if client.get("lastHireDate") != client.get("firstHireDate") else None,
        termination_date=None,  # Client object has no termination date field observed; only termReasonCode/termExplanation
        termination_reason=client.get("termExplanation") or None,
        pay_frequency=None,  # compensation.payPeriod (W/B/S/M/A) describes pay-period CODE tables, not a single current frequency - needs its own dedicated mapping pass, deliberately left unset here rather than guessed
        raw_pay_frequency=compensation.get("payPeriod") or None,
        pay_rates=_map_pay_rates(compensation),
        direct_deposits=_map_direct_deposits(employee_id, emp0.get("directDeposit")),
        deductions=_map_deductions(employee_id, bundle),
    )
    return employee.model_dump(mode="json")


# ---------------------------------------------------------------------------
# payroll
# ---------------------------------------------------------------------------

def _map_paycheck(voucher: Dict[str, Any]) -> Dict[str, Any]:
    voucher_id = voucher.get("voucherId")
    employee_id = voucher.get("employeeId")
    raw_status = voucher.get("status")

    earnings = [
        EarningLine(
            category=EarningCategory.REGULAR if e.get("payCode") == "REG" else EarningCategory.OTHER,
            raw_category=e.get("payCode"),
            description=e.get("payClassDescription"),
            hours=_dec(e.get("hoursWorked")),
            rate=_dec(e.get("unitRate")),
            amount=_dec(e.get("payAmount")) or Decimal("0"),
        ).model_dump(mode="json")
        for e in voucher.get("earning") or []
    ]

    taxes = [
        TaxLine(
            code=t.get("empTaxDeductCode") or "UNKNOWN",
            jurisdiction=t.get("empTaxDeductCodeDesc"),
            employee_amount=_dec(t.get("empTaxAmount")),
            employer_amount=None,
        ).model_dump(mode="json")
        for t in voucher.get("employeeTax") or []
    ] + [
        TaxLine(
            code=t.get("comTaxDeductCode") or "UNKNOWN",
            jurisdiction=t.get("comTaxDeductCodeDesc"),
            employee_amount=None,
            employer_amount=_dec(t.get("comTaxAmount")),
        ).model_dump(mode="json")
        for t in voucher.get("companyTax") or []
    ]

    deductions = [
        DeductionLine(
            deduction_setup_id=None,  # PrismHR's voucher deduction lines (deductCode) aren't keyed to a stable DeductionSetup.id without a cross-reference pass this adapter doesn't yet perform
            code=d.get("deductCode") or "UNKNOWN",
            employee_amount=_dec(d.get("deductAmount")),
            employer_amount=None,
        ).model_dump(mode="json")
        for d in voucher.get("deduction") or []
    ]

    paycheck = Paycheck(
        # voucherId is unique within one employee's own voucher history but NOT
        # globally unique across the provider (confirmed empirically: the same
        # voucherId recurs across different clients/employees) - the canonical id
        # must be scoped by employeeId to stay globally unique. source.raw_id
        # keeps the true, unscoped voucherId PrismHR itself uses, for traceability.
        id=canonical_id(PROVIDER, "paycheck", f"{employee_id}:{voucher_id}"),
        source=Source(provider=PROVIDER, raw_id=voucher_id),
        employee_id=canonical_id(PROVIDER, "employee", employee_id) if employee_id else "",
        payroll_run_id=None,  # see module docstring: PrismHR's voucher list isn't grouped by run from this endpoint
        status=_PAYCHECK_STATUS.get(raw_status, PaycheckStatus.OTHER),
        raw_status=raw_status,
        check_date=_date(voucher.get("payDate")),
        period_start=_date(voucher.get("payPeriodStart")),
        period_end=_date(voucher.get("payPeriodEnd")),
        gross_pay=_dec(voucher.get("totalEarnings")),
        net_pay=_dec(voucher.get("netPay")),
        total_hours=None,  # no single total-hours field on PayrollVoucher; would need summing earning[].hoursWorked, deliberately left to the caller rather than silently approximated
        earnings=earnings,
        taxes=taxes,
        deductions=deductions,
        benefit_contributions=[],  # see docs/CANONICAL_SCHEMA.md "what's still open" - voucher.benefit[] (planId/empContrib/empDeduct) is real data not yet mapped
    )
    return paycheck.model_dump(mode="json")


def _normalize_payroll(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    vouchers = (response or {}).get("payrollVoucher") or (response or {}).get("payrollVouchers") or []
    return [_map_paycheck(v) for v in vouchers]


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def normalize(entity: str, response: Any, reference: Dict[str, Any]) -> Any:
    """Map a raw PrismHR API response (or, for "employee", a composite bundle
    of several raw responses - see module docstring) onto the canonical
    schema. `reference` (the loaded lookup-reference.json) is accepted for
    interface consistency with the other adapters but not yet consulted at
    runtime; the enum tables above were built from it, not from it dynamically.
    """
    if response is None:
        raise NotImplementedError("PrismHR adapter requires a response payload; see module docstring for the expected shape per entity.")
    if entity == "company":
        return _normalize_company(response)
    if entity == "employee":
        return _normalize_employee(response)
    if entity == "payroll":
        return _normalize_payroll(response)
    raise ValueError(f"Unknown entity for PrismHR adapter: {entity!r}")
