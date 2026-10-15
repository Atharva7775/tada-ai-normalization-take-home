"""Thin, reusable client for the organizer's demo-provider-signin service.

Kept separate from any UI code (Streamlit or otherwise) so later steps in
the end-to-end app - data extraction, canonical conversion, DB write - can
import TENANTS/sign_in() without depending on Streamlit at all.

Per the README's "Access live demo data" section: this calls
POST https://tada-demo-provider-signin.onrender.com/signin with an
X-API-Key header and {"tenant": "prism"|"isol"|"ukg"}, returning the
provider's base_url, short-lived auth, and demo company identifiers.
Tokens are never written to disk here - callers decide where they live
(e.g. Streamlit's in-memory session_state), consistent with the README's
"keep returned tokens...out of Git and your submission."
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

SIGNIN_URL = "https://tada-demo-provider-signin.onrender.com/signin"
REQUEST_TIMEOUT_SECONDS = 30

# tenant selector -> (display name, canonical provider key used elsewhere in this project)
TENANTS: Dict[str, Dict[str, str]] = {
    "prism": {"label": "PrismHR", "provider_key": "prismhr"},
    "isol": {"label": "isolved", "provider_key": "isolved"},
    "ukg": {"label": "UKG Ready", "provider_key": "ukg-ready"},
}


class SignInError(Exception):
    """Raised for any non-200 /signin response, with the HTTP status and
    the organizer service's own error detail (never a raw provider error -
    the signin service itself filters those out, per its own README)."""

    def __init__(self, status_code: Optional[int], message: str):
        self.status_code = status_code
        super().__init__(message)


@dataclass
class SignInResult:
    tenant: str
    provider_key: str
    provider: str
    tenant_id: str
    base_url: str
    auth: Dict[str, Any]
    context: Dict[str, Any]
    usage: Dict[str, Any]

    @property
    def token_value(self) -> Optional[str]:
        """The one real credential in the response - PrismHR's sessionId or
        isolved/UKG's access_token - whichever field is actually present."""
        return self.auth.get("sessionId") or self.auth.get("access_token")

    @property
    def company_identifiers(self) -> list:
        return (self.context or {}).get("companies") or []


def sign_in(tenant: str, api_key: str) -> SignInResult:
    """Calls POST /signin for the given tenant selector ('prism'/'isol'/'ukg').
    Raises SignInError on any failure (bad key, bad tenant, rate limit,
    upstream failure, network/timeout issue) with a message safe to show
    directly in a UI - never includes the api_key or any raw token.
    """
    if tenant not in TENANTS:
        raise SignInError(None, f"Unknown tenant selector {tenant!r}; expected one of {list(TENANTS)}")
    if not api_key:
        raise SignInError(None, "API key is required.")

    try:
        response = requests.post(
            SIGNIN_URL,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={"tenant": tenant},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        raise SignInError(None, "The sign-in service timed out. It may be waking up after inactivity - try again.")
    except requests.RequestException as exc:
        raise SignInError(None, f"Could not reach the sign-in service: {exc}")

    if response.status_code != 200:
        detail = _extract_error_detail(response)
        friendly = {
            401: "Invalid API key.",
            400: "Invalid tenant selector.",
            413: "Request was too large.",
            415: "Request must be JSON.",
            429: "Rate limit exceeded (30 attempts/minute) - wait a moment and retry.",
            502: "The upstream provider rejected authentication.",
        }.get(response.status_code, "Sign-in failed.")
        message = f"{friendly} (HTTP {response.status_code})" + (f" - {detail}" if detail else "")
        raise SignInError(response.status_code, message)

    try:
        data = response.json()
    except ValueError:
        raise SignInError(response.status_code, "Sign-in service returned a non-JSON response.")

    return SignInResult(
        tenant=tenant,
        provider_key=TENANTS[tenant]["provider_key"],
        provider=data.get("provider", tenant),
        tenant_id=data.get("tenant_id", ""),
        base_url=data.get("base_url", ""),
        auth=data.get("auth") or {},
        context=data.get("context") or {},
        usage=data.get("usage") or {},
    )


def _extract_error_detail(response: requests.Response) -> str:
    try:
        body = response.json()
        return str(body.get("message") or body.get("error") or "")
    except ValueError:
        return ""


def mask_token(token: Optional[str], visible: int = 4) -> str:
    """Never show a real credential in full in any UI - first/last `visible`
    characters only, matching this project's existing redaction convention."""
    if not token:
        return ""
    if len(token) <= visible * 2:
        return "*" * len(token)
    return f"{token[:visible]}...{token[-visible:]} ({len(token)} chars)"
