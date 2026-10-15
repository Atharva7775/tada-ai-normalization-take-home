"""Step 3: run a pulled employee bundle (app/data_client.py's output) through
the real adapter in src/normalization/adapters/ and return the canonical
Employee dict. Kept Streamlit-free, same reasoning as signin_client.py /
data_client.py: this is the exact function a future step 4 (DB write) would
also call.

Each adapter's normalize("employee", bundle, reference) already returns
employee.model_dump(mode="json") internally - this module does no further
transformation, just loads the provider's lookup-reference.json once and
calls through.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from normalization.adapters import ADAPTERS  # noqa: E402
from normalization.references import load_reference  # noqa: E402


class CanonicalizeError(Exception):
    """Raised when the adapter can't map the pulled bundle - a malformed or
    unexpected provider response, not a network/auth problem (those surface
    earlier, in data_client.py)."""


def canonicalize_employee(provider_key: str, bundle: Dict[str, Any]) -> Dict[str, Any]:
    """provider_key is the adapters/contracts folder name - "prismhr",
    "isolved", or "ukg-ready" (TENANTS[...]["provider_key"] in
    signin_client.py already uses these exact values). Returns the
    canonical Employee as a JSON-safe dict, ready for st.json() or a
    database write."""
    if provider_key not in ADAPTERS:
        raise CanonicalizeError(f"Unknown provider key {provider_key!r}; expected one of {list(ADAPTERS)}")
    try:
        reference = load_reference(provider_key)
    except (OSError, ValueError) as exc:
        raise CanonicalizeError(f"Could not load {provider_key}'s lookup-reference.json: {exc}")
    try:
        return ADAPTERS[provider_key].normalize("employee", bundle, reference)
    except Exception as exc:  # adapter can raise ValueError/NotImplementedError/pydantic ValidationError
        raise CanonicalizeError(f"The {provider_key} adapter could not map this bundle: {exc}")
