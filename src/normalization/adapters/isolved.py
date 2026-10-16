"""isolved adapter: maps raw isolved API responses onto the canonical schema
in src/normalization/canonical/.

Spec: contracts/isolved/openapi/isolved-v6.swagger.json (PRIMARY snapshot only
- per the README, do not mix in the alternate snapshot's schemas)
Lookup reference: contracts/isolved/lookup-reference.json

**Fundamentally different evidence situation than PrismHR.** PrismHR's spec
documents real fixed enums in field descriptions (e.g. Client.statusClass:
"'A' (active), 'L' (on leave), or 'T' (terminated)"), and
lookup-reference.json's deduction_type domain is a genuine closed code
table. isolved has neither: every status/type-like field below
(EmployeeModel.employmentStatus, gender, maritalStatus, payType;
EmployeeDirectDepositModel.accountType/frequency/status;
EmployeePayItemModel.payItemType; CheckModel.checkTypeDescription) is
declared in the swagger spec as a bare `"type": "string"` with only a
human description like "Direct Deposit Status Description" - there is no
enum array anywhere, and isolved's own lookup-reference.json's 11 domains
are all scheduling/timecard fields, covering none of these. Its EXTRA (the
`demo-provider-signin` service's organizer-approved pack) does not change
this. Every mapping table below is therefore built from the literal string
values this project observed live (contracts/isolved via the crawled demo
tenant), not from provider documentation - flagged throughout as
lower-confidence than PrismHR's. A differently-configured isolved tenant
could use different wording for any of these and this adapter would not
recognize it (falling back to OTHER/UNKNOWN, never raising).

Input shape per entity (see docs/CANONICAL_SCHEMA.md for the full
rationale, parallel to the PrismHR adapter's documented decisions):

- "company": the raw response of GET /api/clients/{clientId}/legals (a
  bare array of LegalModel - isolved's EIN-bearing legal entity is the
  right level to equate with the canonical "Company" concept; the parent
  ClientModel is more like a staffing-company/brand wrapper around one or
  more legal entities and has no EIN of its own). Returns a LIST of
  canonical Company dicts.

- "employee": isolved splits one employee's data across four separate GET
  calls, and - like PrismHR's getEmployee - the single-employee endpoint
  does NOT self-report its own clientId/legalId (EmployeeModel has
  `legalCode`, a short text code, but no legalId/clientId field at all;
  confirmed against the swagger spec, not assumed). `response` is a
  composite bundle dict:
      {
        "profile": <raw GET .../employees/{id} response, called with
                    includeOrganizations=true&includeTaxes=true&includeAlternateRates=true>,
        "direct_deposits": <raw GET .../employees/{id}/directdeposits response - a bare array>,
        "pay_items": <raw GET .../employees/{id}/payItems response - a bare array>,
        "corestream_deductions": <raw GET /api/corestream/.../employees/{id}/deductions response - a bare array or null>,
        "client_id": "<the clientId this employee was queried under>",
        "legal_id": "<the legalId this employee was queried under>",
      }
  Any key may be omitted or None. Returns a single canonical Employee dict.

- "payroll": the raw response of GET .../employees/{employeeId}/checks
  (a PagedModelItemListOfCheckModel, `.results[]`). Returns a LIST of
  canonical Paycheck dicts. No PayrollRun wrapper is used: this project's
  live crawl found `legalAndPayGroupsWithPayrollSchedules` returned a null
  `payGroups` for both of this demo tenant's legal entities, so no real
  PayrollRunHistoryModel data was ever obtainable to group checks under -
  see docs/CANONICAL_SCHEMA.md "what's still open" for isolved.
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

PROVIDER = "isolved"

# ---------------------------------------------------------------------------
# Enum translation tables. NONE of these are documented closed enums in
# isolved's OpenAPI spec or lookup-reference.json (see module docstring) -
# every mapping below is grounded only in the literal strings this project
# observed live, across 138 real employees in two legal entities. Treat all
# of these as lower-confidence than PrismHR's documented mappings.
# ---------------------------------------------------------------------------

_EMPLOYMENT_STATUS = {
    "Active": EmploymentStatus.ACTIVE,
    "Terminated": EmploymentStatus.TERMINATED,
    # "Inactive" was observed once live with no documented meaning anywhere
    # (confirmed: this project's own employees_canonical_status demo view
    # in live_demo_data.sql already treats this the same way) - UNKNOWN,
    # not a guess at ACTIVE or TERMINATED.
}

# isolved exposes no company-level status field distinct from the legal
# entity's own `status` (LegalModel.status) - only "Active" observed live
# for both of this project's legal entities; no Pending/Inactive/Terminated
# example has been seen to confirm those words.
_COMPANY_STATUS = {
    "Active": CompanyStatus.ACTIVE,
}

_GENDER = {"Male": Gender.MALE, "Female": Gender.FEMALE}

_MARITAL_STATUS = {
    "Single": MaritalStatus.SINGLE,
    "Married": MaritalStatus.MARRIED,
    "Chose not to answer": MaritalStatus.UNKNOWN,  # respecting a declined disclosure as UNKNOWN, not OTHER
}

_PAY_BASIS = {
    "Hourly": PayBasis.HOURLY,
    "Salary": PayBasis.SALARY,
    # "1099" (contractor) and "Guarantee" observed live with no clean canonical
    # equivalent - left to fall through to OTHER rather than guessed.
}

_ACCOUNT_TYPE = {
    "Checking": DirectDepositAccountType.CHECKING,
    "Savings": DirectDepositAccountType.SAVINGS,
}

_DIRECT_DEPOSIT_STATUS = {
    "Active": DirectDepositStatus.ACTIVE,
    "Inactive": DirectDepositStatus.INACTIVE,
}

# EmployeePayItemModel.payItemType real observed values: "Earning",
# "Deduction", "Memo Calc". Only "Deduction"-typed items are mapped into
# DeductionSetup here; "Memo Calc" items are informational/non-cash and
# excluded, matching the same filter already applied when this project
# built live_demo_data.sql.
_DEDUCTION_PAY_ITEM_TYPE = "Deduction"

# payItemName/payItemCode have no code table at all (free-text names like
# "401K", "Dental Pre-tax", "GTL") - DeductionCategory below is assigned by
# keyword match against the name, which is explicitly a heuristic, not an
# authoritative classification. Unmatched names fall to OTHER/VOLUNTARY_OTHER.
_DEDUCTION_NAME_KEYWORDS = [
    (("401k", "401(k)", "retirement", "roth"), DeductionCategory.RETIREMENT),
    (("garnish",), DeductionCategory.GARNISHMENT),
    (("loan",), DeductionCategory.LOAN),
    (("pre-tax", "pretax", "125", "dental", "medical", "vision", "fsa", "hsa"), DeductionCategory.PRETAX_BENEFIT),
    (("post-tax", "posttax"), DeductionCategory.POST_TAX_BENEFIT),
]

# CheckModel has no separate lifecycle-status field distinct from
# checkTypeDescription (confirmed: `taxes`/`benefits` were null on every one
# of 430 real checks this project observed, and there is no `status` field
# on CheckModel at all per the swagger spec). "Adjustment" is the only value
# observed live, and does not map cleanly onto OPEN/FINALIZED/VOID/REISSUED
# - it describes a check TYPE (an out-of-cycle correction), not a lifecycle
# stage, so this project deliberately maps it to OTHER rather than guessing
# a stage. A future "Regular" or "Void" value, if ever observed, would need
# its own entry here.
_CHECK_TYPE_TO_STATUS: Dict[str, PaycheckStatus] = {}


def _dec(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _date(value: Any) -> Optional[str]:
    """isolved returns timestamps like '2025-07-02T00:00:00'; keep just the date part."""
    if not value:
        return None
    return str(value).split("T")[0]


def _categorize_deduction(name: Optional[str]) -> DeductionCategory:
    if not name:
        return DeductionCategory.OTHER
    lowered = name.lower()
    for keywords, category in _DEDUCTION_NAME_KEYWORDS:
        if any(k in lowered for k in keywords):
            return category
    return DeductionCategory.VOLUNTARY_OTHER


# ---------------------------------------------------------------------------
# company
# ---------------------------------------------------------------------------

def _map_company(legal: Dict[str, Any]) -> Dict[str, Any]:
    legal_id = legal.get("id")
    raw_status = legal.get("status")
    address = legal.get("legalAddress") or {}
    company = Company(
        id=canonical_id(PROVIDER, "company", str(legal_id)),
        source=Source(provider=PROVIDER, raw_id=str(legal_id)),
        name=legal.get("legalName"),
        legal_name=legal.get("dbaName") or legal.get("legalName"),
        tax_id=legal.get("federalEIN") or None,
        status=_COMPANY_STATUS.get(raw_status, CompanyStatus.OTHER),
        raw_status=raw_status,
        address=Address(
            line1=address.get("address1") or None,
            line2=address.get("address2") or None,
            city=address.get("city") or None,
            state=address.get("state") or None,
            postal_code=address.get("zipCode") or None,
            country="USA" if address.get("state") else None,
        ) if address else None,
    )
    return company.model_dump(mode="json")


def _normalize_company(response: Any) -> List[Dict[str, Any]]:
    legals = response or []
    return [_map_company(l) for l in legals]


# ---------------------------------------------------------------------------
# employee
# ---------------------------------------------------------------------------

def _map_direct_deposits(employee_id: str, deposits: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out = []
    for dd in deposits or []:
        raw_account_type = dd.get("accountType")
        raw_status = dd.get("status")
        # dd["id"] is NOT globally unique on its own - confirmed empirically
        # (this project's own synthetic fixtures reuse the same deposit id
        # across two different employees' records, which previously caused
        # a UNIQUE constraint failure saving to canonical.db). Scoping by
        # employee_id is the same fix already applied to this file's own
        # _map_deductions, for the same root cause.
        dd_model = DirectDeposit(
            id=canonical_id(PROVIDER, "directdeposit", f"{employee_id}:{dd.get('id')}"),
            source=Source(provider=PROVIDER, raw_id=str(dd.get("id"))),
            account_type=_ACCOUNT_TYPE.get(raw_account_type, DirectDepositAccountType.OTHER),
            raw_account_type=raw_account_type,
            bank_name=dd.get("bankName") or None,
            routing_number_last4=(dd.get("routingNumber") or "")[-4:] or None,
            account_number_last4=(dd.get("accountNumber") or "").replace("*", "")[-4:] or None,
            # isolved's direct deposits don't expose a flat/percent/balance
            # calculation method distinct from "amount" vs "percent" being
            # populated - inferred from which field has a value, not a
            # documented method code.
            allocation_method=AllocationMethod.PERCENT_OF_GROSS if dd.get("percent") is not None
                else (AllocationMethod.FLAT_AMOUNT if dd.get("amount") is not None else AllocationMethod.REMAINING_BALANCE),
            raw_allocation_method=None,
            amount=_dec(dd.get("amount")),
            percent=_dec(dd.get("percent")),
            priority=dd.get("sequenceNumber"),
            status=_DIRECT_DEPOSIT_STATUS.get(raw_status, DirectDepositStatus.OTHER),
            raw_status=raw_status,
        )
        out.append(dd_model.model_dump(mode="json"))
    return out


def _map_deductions(employee_id: str, pay_items: Optional[List[Dict[str, Any]]],
                     corestream_deductions: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out = []
    for item in pay_items or []:
        if item.get("payItemType") != _DEDUCTION_PAY_ITEM_TYPE:
            continue
        name = item.get("payItemName")
        # payItem.id is NOT globally unique on its own - confirmed empirically:
        # small negative ids (-1..-19) recur identically across different
        # employees (they're shared catalog-level placeholders, consistent
        # with the "catalog, not elections" finding noted below), while
        # large positive ids are genuinely employee-specific. The canonical
        # id must be scoped by employeeId to stay globally unique, same fix
        # already applied to PrismHR's Paycheck.id for the same root cause.
        ded = DeductionSetup(
            id=canonical_id(PROVIDER, "deduction", f"payitem:{employee_id}:{item.get('id')}"),
            source=Source(provider=PROVIDER, raw_id=str(item.get("id"))),
            code=item.get("payItemCode") or "UNKNOWN",
            description=name,
            category=_categorize_deduction(name),
            raw_category=None,  # isolved provides no category code at all for pay items, only a free-text name
            calc_method=AllocationMethod.OTHER,  # calcParams (Rate/Amount pairs) don't map cleanly to a single documented method
            raw_calc_method=None,
            amount=None,
            percent=None,
            start_date=_date(item.get("startDate")),
            stop_date=_date(item.get("stopDate")),
            is_active=None,  # payItems doesn't expose an active/inactive flag
        )
        out.append(ded.model_dump(mode="json"))

    # corestream_deductions was null for every employee this project observed
    # live in both legal entities - included for completeness in case a
    # differently-configured tenant returns real rows.
    for item in corestream_deductions or []:
        ded = DeductionSetup(
            id=canonical_id(PROVIDER, "deduction", f"corestream:{employee_id}:{item.get('id')}"),
            source=Source(provider=PROVIDER, raw_id=str(item.get("id"))),
            code=item.get("payItemCode") or "UNKNOWN",
            description=None,
            category=DeductionCategory.OTHER,
            raw_category=None,
            calc_method=AllocationMethod.OTHER,
            raw_calc_method=None,
            amount=None,
            percent=None,
            start_date=_date(item.get("startDate")),
            stop_date=_date(item.get("stopDate")),
            is_active=None,
        )
        out.append(ded.model_dump(mode="json"))

    return out


def _map_pay_rates(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_basis = profile.get("payType")
    basis = _PAY_BASIS.get(raw_basis, PayBasis.OTHER)
    if raw_basis == "Hourly":
        amount = profile.get("hourlyRate")
    else:
        amount = profile.get("annualSalary") or profile.get("perPaySalary")
    dec_amount = _dec(amount)
    if dec_amount is None:
        return []
    rate = PayRate(
        basis=basis,
        raw_basis=raw_basis,
        amount=dec_amount,
        effective_date=_date(profile.get("salaryEffectiveDate")),
    )
    return [rate.model_dump(mode="json")]


def _normalize_employee(bundle: Dict[str, Any]) -> Dict[str, Any]:
    profile = bundle.get("profile") or {}
    employee_id = profile.get("id")
    na = profile.get("nameAddress") or {}
    personal = profile.get("personal") or {}

    legal_id_raw = bundle.get("legal_id")
    raw_status = profile.get("employmentStatus")
    raw_gender = profile.get("gender")
    raw_marital = profile.get("maritalStatus")

    employee = Employee(
        id=canonical_id(PROVIDER, "employee", str(employee_id)),
        source=Source(provider=PROVIDER, raw_id=str(employee_id)),
        company_id=canonical_id(PROVIDER, "company", str(legal_id_raw)) if legal_id_raw else "",
        employee_number=profile.get("employeeNumber"),
        first_name=na.get("firstName") or None,
        last_name=na.get("lastName") or None,
        middle_name=na.get("middleName") or None,
        preferred_name=na.get("preferredName") or None,
        date_of_birth=_date(profile.get("birthDate")),
        gender=_GENDER.get(raw_gender, Gender.UNKNOWN) if raw_gender else None,
        raw_gender=raw_gender or None,
        marital_status=_MARITAL_STATUS.get(raw_marital, MaritalStatus.UNKNOWN) if raw_marital else None,
        raw_marital_status=raw_marital or None,
        ssn_last4=(profile.get("ssn") or "").replace("-", "")[-4:] or None,
        contact=ContactInfo(
            email=profile.get("emailAddress") or personal.get("personalEmailAddress") or None,
            mobile_phone=personal.get("mobilePhone") or None,
            home_phone=personal.get("homePhone") or None,
            work_phone=personal.get("officePhone") or None,
        ),
        address=Address(
            line1=na.get("address1") or None,
            city=na.get("city") or None,
            state=na.get("state") or None,
            postal_code=na.get("zipCode") or None,
            country="USA" if na.get("state") else None,
        ) if na else None,
        employment_status=_EMPLOYMENT_STATUS.get(raw_status, EmploymentStatus.UNKNOWN),
        raw_employment_status=raw_status,
        worker_type=None,  # employmentCategoryCode ("FT") has no documented or empirically-confirmed closed set
        raw_worker_type=profile.get("employmentCategoryCode") or None,
        job_title=profile.get("jobTitle") or None,
        department=None,  # organizations[] carries department info but in a shape this adapter doesn't yet flatten - see docs/CANONICAL_SCHEMA.md
        manager_employee_id=None,  # assignedManager exists on EmployeeModel but as a nested reference this adapter doesn't yet resolve to a canonical employee id
        hire_date=_date(profile.get("hireDate")),
        rehire_date=_date(profile.get("rehireDate")),
        termination_date=_date(profile.get("terminationDate")),
        termination_reason=profile.get("terminationReason") or None,
        pay_frequency=None,  # payFrequency is an integer (pay periods per year, e.g. 12) with no documented mapping to the canonical PayFrequency enum's named cadences
        raw_pay_frequency=str(profile.get("payFrequency")) if profile.get("payFrequency") is not None else None,
        pay_rates=_map_pay_rates(profile),
        direct_deposits=_map_direct_deposits(employee_id, bundle.get("direct_deposits")),
        deductions=_map_deductions(employee_id, bundle.get("pay_items"), bundle.get("corestream_deductions")),
    )
    return employee.model_dump(mode="json")


# ---------------------------------------------------------------------------
# payroll
# ---------------------------------------------------------------------------

def _map_paycheck(check: Dict[str, Any]) -> Dict[str, Any]:
    check_id = check.get("id")
    employee_id = check.get("employeeId")
    raw_type = check.get("checkTypeDescription")

    earnings = [
        EarningLine(
            category=EarningCategory.REGULAR if (e.get("itemDescription") or "").lower() == "regular" else EarningCategory.OTHER,
            raw_category=e.get("itemCode"),
            description=e.get("itemDescription"),
            hours=_dec(e.get("checkHours")),
            rate=None,
            amount=_dec(e.get("checkDollars")) or Decimal("0"),
        ).model_dump(mode="json")
        for e in check.get("earnings") or []
    ]

    # CheckModel.taxes was null on every real check this project observed;
    # taxCategories (filing-status configuration, not actual withheld
    # amounts) is deliberately NOT used as a substitute - it would fabricate
    # tax-line amounts from config data that has none. taxes stays empty.
    taxes: List[Dict[str, Any]] = [
        TaxLine(
            code=t.get("id") or t.get("code") or "UNKNOWN",
            jurisdiction=t.get("description"),
            employee_amount=_dec(t.get("checkDollars") or t.get("amount")),
            employer_amount=None,
        ).model_dump(mode="json")
        for t in check.get("taxes") or []
    ]

    deductions = [
        DeductionLine(
            deduction_setup_id=None,  # no cross-reference pass between a check's deduction line and the employee's DeductionSetup.id has been built yet
            code=d.get("itemCode") or "UNKNOWN",
            employee_amount=_dec(d.get("checkDollars")),
            employer_amount=None,
        ).model_dump(mode="json")
        for d in check.get("deductions") or []
    ]

    # CheckModel.benefits was null on every real check this project observed.
    benefit_contributions: List[Dict[str, Any]] = []

    paycheck = Paycheck(
        id=canonical_id(PROVIDER, "paycheck", str(check_id)),
        source=Source(provider=PROVIDER, raw_id=str(check_id)),
        employee_id=canonical_id(PROVIDER, "employee", str(employee_id)) if employee_id else "",
        payroll_run_id=None,  # see module docstring: no real PayrollRunHistoryModel data was obtainable for either legal entity in this project's live crawl
        status=_CHECK_TYPE_TO_STATUS.get(raw_type, PaycheckStatus.OTHER),
        raw_status=raw_type,
        check_date=_date(check.get("checkDate")),
        period_start=_date(check.get("periodBeginDate")),
        period_end=_date(check.get("periodEndDate")),
        gross_pay=_dec(check.get("grossPay") or check.get("grossWages")),
        net_pay=_dec(check.get("netPay")),
        total_hours=None,  # no single total-hours field on CheckModel; would need summing earnings[].checkHours, deliberately left to the caller rather than silently approximated
        earnings=earnings,
        taxes=taxes,
        deductions=deductions,
        benefit_contributions=benefit_contributions,
    )
    return paycheck.model_dump(mode="json")


def _normalize_payroll(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    checks = (response or {}).get("results") or []
    return [_map_paycheck(c) for c in checks]


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def normalize(entity: str, response: Any, reference: Dict[str, Any]) -> Any:
    """Map a raw isolved API response (or, for "employee", a composite bundle
    of several raw responses - see module docstring) onto the canonical
    schema. `reference` (the loaded lookup-reference.json) is accepted for
    interface consistency with the other adapters; isolved's lookup
    reference doesn't cover any field this adapter maps (see module
    docstring), so it isn't consulted at runtime.
    """
    if response is None:
        raise NotImplementedError("isolved adapter requires a response payload; see module docstring for the expected shape per entity.")
    if entity == "company":
        return _normalize_company(response)
    if entity == "employee":
        return _normalize_employee(response)
    if entity == "payroll":
        return _normalize_payroll(response)
    raise ValueError(f"Unknown entity for isolved adapter: {entity!r}")
