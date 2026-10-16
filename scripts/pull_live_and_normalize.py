"""Pull one real employee bundle live from a provider's demo tenant and run
it through the real adapter - entirely from the terminal, no Streamlit.

Edit the three settings below, then just run this file - no need to retype
or paste anything into the terminal each time:

    python3 scripts/pull_live_and_normalize.py

Requires DEMO_SIGNIN_API_KEY to be set first:

    export DEMO_SIGNIN_API_KEY=<key the organizer gave you>

This calls the same Streamlit-free client modules the app itself uses
(app/signin_client.py's sign_in(), app/data_client.py's
pull_employee_bundles(), app/canonicalize_client.py's
canonicalize_employee() - which internally calls
ADAPTERS[provider_key].normalize("employee", bundle, reference), the exact
same adapter function python -m normalization normalize and the Streamlit
app both call). Deliberately bypasses the CLI's readiness-gate check
(src/normalization/references.py's readiness_issues()), which currently
refuses to run for isolved/UKG Ready - a real licensing gate, not a bug
(see ASSUMPTIONS_AND_DECISIONS.md). Scoped to the "employee" entity only,
since pull_employee_bundles() is the only live-pull function this project
has - there's no equivalent reusable "pull company"/"pull payroll"
function.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from canonicalize_client import canonicalize_employee  # noqa: E402
from data_client import pull_employee_bundles  # noqa: E402
from signin_client import sign_in  # noqa: E402

# --- edit these, then just re-run this file ---------------------------------
TENANT = "prism"          # "prism" (PrismHR) | "isol" (isolved) | "ukg" (UKG Ready)
PROVIDER_KEY = "prismhr"  # "prismhr" | "isolved" | "ukg-ready" - must match TENANT above
COUNT = 1                 # how many companies to pull one employee from; None = all companies
# -----------------------------------------------------------------------------

# Gitignored - matches this project's existing adapter_demo_run/ convention
# for real downloaded live data (see .gitignore and ASSUMPTIONS_AND_DECISIONS.md
# - "keep downloaded records out of Git and your submission").
OUTPUT_DIR = _ROOT / "adapter_demo_run" / PROVIDER_KEY


def main() -> None:
    api_key = os.environ.get("DEMO_SIGNIN_API_KEY")
    if not api_key:
        raise SystemExit(
            "Set DEMO_SIGNIN_API_KEY first: export DEMO_SIGNIN_API_KEY=<key the organizer gave you>"
        )

    result = sign_in(TENANT, api_key)  # live POST /signin
    bundles, skipped = pull_employee_bundles(TENANT, result, count=COUNT)  # live pull
    print(f"Pulled {len(bundles)} employee bundle(s); {len(skipped)} company(ies) skipped.")
    for company_id, reason in skipped:
        print(f"  skipped {company_id}: {reason}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for i, bundle in enumerate(bundles):
        canonical = canonicalize_employee(PROVIDER_KEY, bundle)  # runs the real adapter
        out_path = OUTPUT_DIR / f"employee_{i}_canonical.json"
        out_path.write_text(json.dumps(canonical, indent=2) + "\n")
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
