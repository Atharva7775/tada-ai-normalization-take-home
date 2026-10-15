"""UKG Ready adapter: maps raw UKG Ready API responses onto the canonical
schema in src/normalization/canonical/.

No official OpenAPI/Swagger contract exists for UKG Ready in this project;
every field mapped below comes from the cached reference pages in
contracts/ukg-ready/reference-docs/res/ and from this project's own live
crawl of the demo tenant (company 33704016, its only company).

**UKG's gaps are discovery gaps, not provider gaps.** The real employee-list
response this project crawled includes `_links` pointing at `demographics`,
`pay-info`, `badges`, and `profiles` sub-resources - separate GET calls
this project never made. Gender, marital status, job title, pay rate, pay
frequency, and worker type are therefore left unmapped below NOT because
UKG Ready lacks this data, but because fetching it would require following
those links, which is future work (see docs/CANONICAL_SCHEMA.md).

Two structural gaps specific to this provider:
- **No company entity exists in UKG's discovered API surface at all** -
  there is no "list companies" or "get company" endpoint anywhere in the
  cached docs. The only company information available is the numeric
  company_id itself, from the demo-provider-signin response's
  `context.companies[].company_id`. The "company" entity below reflects
  only that id; name/status/tax_id are all left unset, which is the
  honest answer, not a mapping failure.
- **GET /deductions 404s live** for this demo tenant ("Unresolvable URL") -
  the cached docs tag this endpoint `dev` rather than `v2`, suggesting
  it's a non-production-tier endpoint not exposed on this server. Every
  UKG employee's `deductions` list is therefore empty in practice.

Input shape per entity:

- "company": a minimal dict `{"company_id": "<id>"}` - see the structural
  gap above. Returns a single canonical Company dict.

- "employee": like PrismHR/isolved, UKG's single-employee response doesn't
  need external company context passed through a composite key here,
  since the company_id is supplied directly rather than inferred from the
  employee payload. `response` is a composite bundle dict:
      {
        "profile": <raw GET /v2/companies/{cid}/employees/{aid} response>,
        "direct_deposits": <raw GET .../employees/{aid}/direct-deposits
                            response - a dict with a "deposits" key>,
        "deductions": <raw GET .../employees/{aid}/deductions response, if
                        reachable - "deductions" key; expect this to be
                        absent/None in practice, see structural gap above>,
        "company_id": "<the company id this employee was queried under>",
      }
  Returns a single canonical Employee dict.

- "payroll": the raw response of GET
  /v2/companies/{cid}/payrolls/{id}/pay-statements (a dict with a
  "pay_statements" key). Returns a LIST of canonical Paycheck dicts.
  **This endpoint is a lightweight index, not a full paycheck record** -
  real pay-statement objects this project crawled carry only id/status/
  pay_date/type/period, no gross/net pay or earnings/taxes/deductions
  lines. Reaching those would require a deeper per-statement detail call
  this project never made (see docs/CANONICAL_SCHEMA.md "what's still
  open"). No PayrollRun wrapper is used, for the same reason as the other
  two adapters: consistency with how this project returns flat Paycheck
  lists everywhere rather than mixing wrapper shapes per provider.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from normalization.canonical import (
    Address,
    AllocationMethod,
    CompanyStatus,
    Company,
    ContactInfo,
    DirectDeposit,
    DirectDepositAccountType,
    DirectDepositStatus,
    Employee,
    EmploymentStatus,
    Paycheck,
    PaycheckStatus,
    Source,
    canonical_id,
)

PROVIDER = "ukg-ready"

# ---------------------------------------------------------------------------
# Enum translation tables.
# ---------------------------------------------------------------------------

# Employee.status - only "Active"/"Terminated" observed live across all 103
# real employees this project crawled; no documented enum found in the
# cached reference pages for this specific field.
_EMPLOYMENT_STATUS = {
    "Active": EmploymentStatus.ACTIVE,
    "Terminated": EmploymentStatus.TERMINATED,
}

# Direct deposit account_type - matches the canonical member names directly;
# confirmed against both the cached HTML docs' response sample and this
# project's live crawl (CHECKING/SAVINGS, nothing else observed).
_ACCOUNT_TYPE = {
    "CHECKING": DirectDepositAccountType.CHECKING,
    "SAVINGS": DirectDepositAccountType.SAVINGS,
}

# Direct deposit calc_method.type. FULL/FLAT_AMOUNT/NET_PAY are confirmed
# from this project's live GET responses. GROSS_EARNING and
# DIRECT_DEPOSIT_PER_OF_REMAINDER are additionally included because they
# appear in the cached POST /direct-deposits doc's request-body description
# - included defensively for a differently-configured tenant, but NOT
# confirmed against any real GET response this project has seen.
_ALLOCATION_METHOD = {
    "FULL": AllocationMethod.REMAINING_BALANCE,       # display_name "Entire/Remainder" in real data
    "FLAT_AMOUNT": AllocationMethod.FLAT_AMOUNT,
    "NET_PAY": AllocationMethod.PERCENT_OF_NET,        # display_name "% Of Net Pay" in real data; uses the "percentage" field
    "GROSS_EARNING": AllocationMethod.PERCENT_OF_GROSS,                 # documented in deprecated POST doc only - unconfirmed live
    "DIRECT_DEPOSIT_PER_OF_REMAINDER": AllocationMethod.REMAINING_BALANCE,  # documented in deprecated POST doc only - unconfirmed live
}

# Pay-statement status - documented in contracts/ukg-ready/lookup-reference.json
# (__v2__companies__(cid)__payrolls__(id)__pay-statements__(id).html domain):
# INVALID/NEW/OPEN/CLOSED/FINALIZED. Only "OPEN" observed live. NEW (not yet
# started processing) has no exact canonical equivalent and is deliberately
# NOT folded into OPEN - they're different lifecycle stages.
_PAY_STATEMENT_STATUS = {
    "NEW": PaycheckStatus.OTHER,
    "OPEN": PaycheckStatus.OPEN,
    "CLOSED": PaycheckStatus.FINALIZED,
    "FINALIZED": PaycheckStatus.FINALIZED,
    "INVALID": PaycheckStatus.OTHER,
}


def _dec(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


# ---------------------------------------------------------------------------
# company
# ---------------------------------------------------------------------------

def _normalize_company(response: Dict[str, Any]) -> Dict[str, Any]:
    company_id = (response or {}).get("company_id")
    company = Company(
        id=canonical_id(PROVIDER, "company", str(company_id)),
        source=Source(provider=PROVIDER, raw_id=str(company_id)),
        name=None,  # no company-detail endpoint exists in this project's discovered UKG API surface - see module docstring
        legal_name=None,
        tax_id=None,
        status=CompanyStatus.OTHER,  # no status data available at all for this entity, not a guessed value
        raw_status=None,
    )
    return company.model_dump(mode="json")


# ---------------------------------------------------------------------------
# employee
# ---------------------------------------------------------------------------

def _map_direct_deposits(deposits_response: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for dep in (deposits_response or {}).get("deposits") or []:
        raw_account_type = dep.get("account_type")
        raw_calc_type = (dep.get("calc_method") or {}).get("type")
        dd = DirectDeposit(
            id=canonical_id(PROVIDER, "directdeposit", str(dep.get("id"))),
            source=Source(provider=PROVIDER, raw_id=str(dep.get("id"))),
            account_type=_ACCOUNT_TYPE.get(raw_account_type, DirectDepositAccountType.OTHER),
            raw_account_type=raw_account_type,
            bank_name=None,  # not returned by this endpoint
            routing_number_last4=(dep.get("routing_number") or "")[-4:] or None,
            account_number_last4=(dep.get("account_number") or "").replace("*", "")[-4:] or None,
            allocation_method=_ALLOCATION_METHOD.get(raw_calc_type, AllocationMethod.OTHER),
            raw_allocation_method=raw_calc_type,
            amount=_dec(dep.get("amount")),
            percent=_dec(dep.get("percentage")),
            priority=dep.get("sequence"),
            status=DirectDepositStatus.ACTIVE if dep.get("active") else DirectDepositStatus.INACTIVE,
            raw_status=str(dep.get("active")),
            effective_from=dep.get("active_from") or None,
            effective_to=dep.get("active_to") or None,
        )
        out.append(dd.model_dump(mode="json"))
    return out


def _first_manager_account_id(profile: Dict[str, Any]) -> Optional[str]:
    managers = profile.get("managers") or []
    if not managers:
        return None
    account_id = (managers[0].get("empl_ref") or {}).get("account_id")
    return str(account_id) if account_id is not None else None


def _normalize_employee(bundle: Dict[str, Any]) -> Dict[str, Any]:
    profile = bundle.get("profile") or {}
    employee_id = profile.get("id")
    company_id_raw = bundle.get("company_id")
    addr = profile.get("address") or {}
    phones = profile.get("phones") or {}
    dates = profile.get("dates") or {}
    raw_status = profile.get("status")

    employee = Employee(
        id=canonical_id(PROVIDER, "employee", str(employee_id)),
        source=Source(provider=PROVIDER, raw_id=str(employee_id)),
        company_id=canonical_id(PROVIDER, "company", str(company_id_raw)) if company_id_raw else "",
        employee_number=profile.get("employee_id"),
        first_name=profile.get("first_name") or None,
        last_name=profile.get("last_name") or None,
        middle_name=profile.get("middle_name") or None,
        preferred_name=profile.get("nickname") or None,
        date_of_birth=dates.get("birthday") or None,
        gender=None,  # lives under the /demographics sub-resource this project did not crawl - see module docstring
        raw_gender=None,
        marital_status=None,  # same - /demographics
        raw_marital_status=None,
        ssn_last4=(profile.get("social_security") or "").replace("-", "")[-4:] or None,
        contact=ContactInfo(
            email=profile.get("primary_email") or None,
            mobile_phone=phones.get("cell_phone") or None,
            home_phone=phones.get("home_phone") or None,
            work_phone=phones.get("work_phone") or None,
        ),
        address=Address(
            line1=addr.get("address_line_1") or None,
            line2=addr.get("address_line_2") or None,
            city=addr.get("city") or None,
            state=addr.get("state_code") or addr.get("state") or None,
            postal_code=addr.get("zip") or None,
            country=addr.get("country") or None,
        ) if addr else None,
        employment_status=_EMPLOYMENT_STATUS.get(raw_status, EmploymentStatus.UNKNOWN),
        raw_employment_status=raw_status,
        worker_type=None,  # lives under /pay-info, not crawled
        raw_worker_type=None,
        job_title=None,  # lives under /pay-info, not crawled
        department=None,
        manager_employee_id=_first_manager_account_id(profile),
        hire_date=dates.get("hired") or None,
        rehire_date=dates.get("re_hired") or None,
        termination_date=dates.get("terminated") or None,
        termination_reason=None,  # not present on this endpoint's response
        pay_frequency=None,  # lives under /pay-info, not crawled
        raw_pay_frequency=None,
        pay_rates=[],  # lives under /pay-info, not crawled
        direct_deposits=_map_direct_deposits(bundle.get("direct_deposits")),
        deductions=[],  # GET .../deductions 404s live for this demo tenant - see module docstring
    )
    return employee.model_dump(mode="json")


# ---------------------------------------------------------------------------
# payroll
# ---------------------------------------------------------------------------

def _map_paycheck(stmt: Dict[str, Any]) -> Dict[str, Any]:
    stmt_id = stmt.get("id")
    employee_account_id = (stmt.get("employee") or {}).get("account_id")
    raw_status = stmt.get("status")

    paycheck = Paycheck(
        id=canonical_id(PROVIDER, "paycheck", str(stmt_id)),
        source=Source(provider=PROVIDER, raw_id=str(stmt_id)),
        employee_id=canonical_id(PROVIDER, "employee", str(employee_account_id)) if employee_account_id else "",
        payroll_run_id=None,  # see module docstring
        status=_PAY_STATEMENT_STATUS.get(raw_status, PaycheckStatus.OTHER),
        raw_status=raw_status,
        check_date=stmt.get("pay_date") or None,
        period_start=stmt.get("pay_period_start") or None,
        period_end=stmt.get("pay_period_end") or None,
        gross_pay=None,  # this endpoint's response has no amount fields at all - see module docstring
        net_pay=None,
        total_hours=None,
        earnings=[],
        taxes=[],
        deductions=[],
        benefit_contributions=[],
    )
    return paycheck.model_dump(mode="json")


def _normalize_payroll(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    statements = (response or {}).get("pay_statements") or []
    return [_map_paycheck(s) for s in statements]


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def normalize(entity: str, response: Any, reference: Dict[str, Any]) -> Any:
    """Map a raw UKG Ready API response onto the canonical schema.
    `reference` (the loaded lookup-reference.json) is accepted for interface
    consistency with the other adapters; the enum tables above were built
    from it, not consulted dynamically at runtime.
    """
    if response is None:
        raise NotImplementedError("UKG Ready adapter requires a response payload; see module docstring for the expected shape per entity.")
    if entity == "company":
        return _normalize_company(response)
    if entity == "employee":
        return _normalize_employee(response)
    if entity == "payroll":
        return _normalize_payroll(response)
    raise ValueError(f"Unknown entity for UKG Ready adapter: {entity!r}")
