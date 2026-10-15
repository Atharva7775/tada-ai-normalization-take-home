"""Step 2: pull ONE employee's FULL bundle per provider - profile plus every
section its adapter's "employee" entity expects (direct deposits,
deductions, etc.) - using the auth already stored from step 1's sign-in
(app/signin_client.py). Deliberately scoped to one employee, not the
full-breadth crawl scripts/generate_fixtures.py's real-data discovery
phase did earlier in this project. Kept Streamlit-free, same reasoning as
signin_client.py: step 3 (adapter conversion) can reuse
pull_sample_employee_bundle() without depending on the UI layer.

**The dict this module returns is a direct, valid input to
ADAPTERS[provider_key].normalize("employee", bundle, reference)** - no
further wrapping needed. Every key matches exactly what each adapter's own
module docstring documents as its expected composite-bundle shape.

Per-provider call count, each reusing the first company identifier step 1
already captured:
  - PrismHR: 6 calls - getEmployeeList (discover an id) -> getEmployee
    (full profile, options=Person,ContactInformation,Client,Compensation,
    DirectDeposit) -> getACHDeductions, getDeductions,
    getVoluntaryRecurringDeductions, getScheduledDeductions.
  - isolved: 5 calls - employees?pageSize=1 (discover an id, cheaply) ->
    employees/{id} (full profile - richer than the list response: the
    list endpoint omits several fields includeAlternateRates exposes) ->
    directdeposits, payItems, corestream deductions.
  - UKG Ready: 4 calls - employees (discover an id; no page-size-limiting
    parameter is documented for this endpoint, so it returns its full
    list regardless) -> employees/{id} (full profile - the list response
    is missing address/phones/social_security/managers/etc. entirely,
    confirmed against this project's own earlier real pull) ->
    direct-deposits, deductions (confirmed to 404 live for every real
    employee this project has ever pulled - treated as "no data", not a
    hard failure, matching the adapter's own documented known gap).

Only the PROFILE call is hard-required per provider - if it fails, the
whole pull aborts. Every other section is optional, exactly like the real
adapters already treat it (see each adapter's own docstring): a failure
there is captured as `None` in the bundle rather than aborting the pull,
UNLESS it's specifically a 401 (token expired) - in that case every
remaining call would fail too, so the whole pull aborts immediately with
token_expired=True rather than making several more doomed requests.

Auth headers are NOT hardcoded per provider - they're built from
result.usage.header_name/header_prefix, the exact values the real sign-in
response already returned.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from signin_client import SignInResult

REQUEST_TIMEOUT_SECONDS = 30

# Fields never shown raw, regardless of provider - either a secret
# (photo_href is a working short-lived access ticket, not just data) or
# PII masked to last 4 characters, same discipline used everywhere else
# in this project (see live_demo_data.sql / scripts/generate_fixtures.py).
_DROP_KEYS = {"photo_href"}
_MASK_LAST4_KEYS = {"ssn", "social_security", "accountnumber", "account_number"}
# UKG buries a SECOND copy of the SSN under a generically-named "value"
# key inside national_id_numbers[] items, identifiable only via a sibling
# "type" field (e.g. {"type": "SSN", "value": "592-07-3333"}) - confirmed
# as a real leak in this exact module during live testing (the top-level
# "social_security" mask above does NOT catch this second copy). Same
# pattern already handled in scripts/generate_fixtures.py / build_sql.py.
_SENSITIVE_ID_TYPES = {"SSN", "BSN", "SIN", "NATIONAL_ID", "NATIONALID", "SOCIAL_SECURITY", "SOCIAL_INSURANCE"}


def _mask_last4(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    digits = "".join(c for c in value if c.isdigit())
    tail = digits[-4:] if len(digits) >= 4 else digits
    return "*" * max(0, len(value) - len(tail)) + tail


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        type_val = next((v.upper() for k, v in obj.items() if k.lower() == "type" and isinstance(v, str)), None)
        out = {}
        for k, v in obj.items():
            kl = k.lower()
            if kl in _DROP_KEYS:
                continue
            if kl == "value" and type_val in _SENSITIVE_ID_TYPES:
                out[k] = _mask_last4(v)
                continue
            out[k] = _mask_last4(v) if kl in _MASK_LAST4_KEYS else _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


class DataPullError(Exception):
    """Raised for a failed REQUIRED call. `token_expired` distinguishes a
    401 (the stored sign-in token has expired or is invalid) from any
    other failure, so the UI can show the right remedy - re-sign-in vs. a
    different error - and never retries silently either way."""

    def __init__(self, message: str, token_expired: bool = False):
        self.token_expired = token_expired
        super().__init__(message)


def _auth_headers(result: SignInResult) -> Dict[str, str]:
    header_name = result.usage.get("header_name")
    header_prefix = result.usage.get("header_prefix", "")
    if not header_name or not result.token_value:
        raise DataPullError("Sign-in result is missing its auth header info - sign in again.")
    return {header_name: f"{header_prefix}{result.token_value}"}


def _get(url: str, headers: Dict[str, str], params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Hard call: raises DataPullError on any failure. Use for profile
    calls, where there's no point continuing without a result."""
    try:
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise DataPullError(f"Could not reach the provider API: {exc}")
    if response.status_code == 401:
        raise DataPullError("The provider rejected this request with HTTP 401 - the token has expired or is invalid.", token_expired=True)
    if response.status_code != 200:
        raise DataPullError(f"Provider returned HTTP {response.status_code}: {response.text[:200]}")
    try:
        return response.json()
    except ValueError:
        raise DataPullError("Provider returned a non-JSON response.")


def _get_soft(url: str, headers: Dict[str, str], params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """Like _get, but for OPTIONAL bundle sections: returns None on any
    failure, including a 401. Confirmed live against isolved: its
    corestream deductions endpoint returns 401 "Authorization has been
    denied for this request" on every pull even when the same token just
    succeeded on the profile/direct-deposits/pay-items calls moments
    earlier - a subsystem-specific permission gap, not token expiry. Only
    the required profile call's 401 (via _get, not this function) is
    trusted as real token expiry."""
    try:
        return _get(url, headers, params)
    except DataPullError:
        return None


def _prismhr_ok(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """PrismHR embeds business errors inside an HTTP 200 body (errorCode
    != "0") - confirmed repeatedly earlier in this project. Treated the
    same as a soft failure for these optional sections: None, not a crash."""
    if data is None or data.get("errorCode") not in (None, "", "0"):
        return None
    return data


def _pull_prismhr(result: SignInResult) -> Dict[str, Any]:
    if not result.company_identifiers:
        raise DataPullError("No PrismHR companies available from sign-in.")
    client_id = result.company_identifiers[0]["client_id"]
    headers = _auth_headers(result)

    list_data = _get(f"{result.base_url}/employee/v1/getEmployeeList", headers, {"clientId": client_id})
    if list_data.get("errorCode") not in (None, "", "0"):
        raise DataPullError(f"PrismHR error {list_data.get('errorCode')}: {list_data.get('errorMessage')}")
    employee_ids = ((list_data.get("employeeList") or {}).get("employeeId")) or []
    if not employee_ids:
        raise DataPullError(f"Client {client_id} has no employees to pull.")
    employee_id = employee_ids[0]

    profile = _get(
        f"{result.base_url}/employee/v1/getEmployee",
        headers,
        {"employeeId": employee_id, "clientId": client_id,
         "options": "Person,ContactInformation,Client,Compensation,DirectDeposit"},
    )
    if profile.get("errorCode") not in (None, "", "0"):
        raise DataPullError(f"PrismHR error {profile.get('errorCode')}: {profile.get('errorMessage')}")

    params = {"clientId": client_id, "employeeId": employee_id}
    bundle = {
        "profile": profile,
        "ach_deductions": _prismhr_ok(_get_soft(f"{result.base_url}/employee/v1/getACHDeductions", headers, params)),
        "deductions": _prismhr_ok(_get_soft(f"{result.base_url}/deductions/v1/getDeductions", headers, params)),
        "voluntary_deductions": _prismhr_ok(_get_soft(f"{result.base_url}/deductions/v1/getVoluntaryRecurringDeductions", headers, params)),
        "scheduled_deductions": _prismhr_ok(_get_soft(f"{result.base_url}/employee/v1/getScheduledDeductions", headers, params)),
        "client_id": client_id,
    }
    return _redact(bundle)


def _pull_isolved(result: SignInResult) -> Dict[str, Any]:
    if not result.company_identifiers:
        raise DataPullError("No isolved companies available from sign-in.")
    company = result.company_identifiers[0]
    client_id, legal_id = company["client_id"], company["legal_id"]
    headers = _auth_headers(result)

    list_data = _get(
        f"{result.base_url}/api/clients/{client_id}/legals/{legal_id}/employees",
        headers,
        {"pageSize": 1},
    )
    employees = list_data.get("results") or []
    if not employees:
        raise DataPullError(f"Legal entity {legal_id} has no employees to pull.")
    employee_id = employees[0]["id"]

    # Full single-employee detail - richer than the list response, which
    # omits several fields this project's adapter reads (confirmed earlier:
    # includeAlternateRates and others are only populated on this call).
    profile = _get(
        f"{result.base_url}/api/clients/{client_id}/legals/{legal_id}/employees/{employee_id}",
        headers,
        {"includeOrganizations": "true", "includeTaxes": "true", "includeAlternateRates": "true"},
    )

    base = f"{result.base_url}/api/clients/{client_id}/legals/{legal_id}/employees/{employee_id}"
    corestream_url = f"{result.base_url}/api/corestream/clients/{client_id}/legals/{legal_id}/employees/{employee_id}/deductions"
    bundle = {
        "profile": profile,
        "direct_deposits": _get_soft(f"{base}/directdeposits", headers),
        "pay_items": _get_soft(f"{base}/payItems", headers),
        "corestream_deductions": _get_soft(corestream_url, headers),
        "client_id": client_id,
        "legal_id": legal_id,
    }
    return _redact(bundle)


def _pull_ukg(result: SignInResult) -> Dict[str, Any]:
    if not result.company_identifiers:
        raise DataPullError("No UKG Ready company available from sign-in.")
    company_id = result.company_identifiers[0]["company_id"]
    headers = {**_auth_headers(result), "Accept": "application/json"}
    # UKG's sign-in base_url is missing the /rest path segment (confirmed
    # against the live service - its own documented API root is
    # {base_url}/rest/v2/...), unlike PrismHR/isolved whose base_url is
    # already the full API root.
    api_root = f"{result.base_url}/rest/v2/companies/{company_id}"

    list_data = _get(f"{api_root}/employees", headers)
    employees = list_data.get("employees") or []
    if not employees:
        raise DataPullError(f"Company {company_id} has no employees to pull.")
    employee_id = employees[0]["id"]

    # Full single-employee detail - the list response is missing
    # address/phones/social_security/managers/etc. entirely (confirmed
    # against this project's own earlier real pull of this exact endpoint).
    profile = _get(f"{api_root}/employees/{employee_id}", headers)

    dd_headers = {**headers, "X-End-of-Support-Timeline": "2026-01-29"}  # required: this endpoint is deprecated-but-functional
    bundle = {
        "profile": profile,
        "direct_deposits": _get_soft(f"{api_root}/employees/{employee_id}/direct-deposits", dd_headers),
        # Confirmed to 404 ("Unresolvable URL") for every real UKG employee
        # this project has ever pulled - a known, documented gap, not an
        # error - _get_soft already turns that into None, not a crash.
        "deductions": _get_soft(f"{api_root}/employees/{employee_id}/deductions", headers),
        "company_id": company_id,
    }
    return _redact(bundle)


_PULLERS = {"prism": _pull_prismhr, "isol": _pull_isolved, "ukg": _pull_ukg}


def pull_sample_employee_bundle(tenant: str, result: SignInResult) -> Dict[str, Any]:
    """Pulls one real employee's full bundle for the given tenant - profile
    plus every optional section its adapter's "employee" entity expects -
    using the sign-in result's stored base_url/token/company id. The
    returned dict is a direct, valid input to
    ADAPTERS[provider_key].normalize("employee", bundle, reference).
    Raises DataPullError (with .token_expired set on a 401) if the
    required profile call fails; optional sections fail soft (None).
    """
    if tenant not in _PULLERS:
        raise DataPullError(f"Unknown tenant selector {tenant!r}")
    return _PULLERS[tenant](result)
