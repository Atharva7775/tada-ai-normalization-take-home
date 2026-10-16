"""Step 2 (optional): generate synthetic employee bundles for one
provider, in the exact same shape a live pull produces, using the
project's existing scripts/generate_fixtures.py generator - the same
generate() function, the same per-provider bundle builders, the same six
scripted scenarios already used for this project's pytest fixtures.
Nothing here duplicates that generation logic; this module only adds a
thin wrapper that points its output at a disposable temp directory
(tests/fixtures/ itself is never touched - it stays exactly as committed)
and reads the generated employee bundles back into memory.
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from generate_fixtures import VARIANTS, generate  # noqa: E402


def generate_synthetic_employees(provider_key: str) -> List[Tuple[str, Dict[str, Any]]]:
    """Returns all six scripted-variant synthetic employee bundles for
    provider_key ("prismhr", "isolved", or "ukg-ready") - a fresh random
    seed each call, written to a throwaway temp directory via the real
    generate_fixtures.generate(), then read back and discarded. Each
    bundle has the same shape as data_client.pull_employee_bundles()'s
    output - a valid input to ADAPTERS[provider_key].normalize("employee",
    bundle, reference), same as canonicalize_client.canonicalize_employee()
    already expects.

    Returns a list of (variant_name, bundle) pairs in
    generate_fixtures.VARIANTS order (active_simple, terminated,
    on_leave_or_undocumented, no_deposits_no_deductions,
    multiple_deposits, unknown_status_code).

    The temp directory is created INSIDE the project root (not /tmp):
    generate_fixtures.py's own _write() always records each file's path
    relative to the project root, so an output_dir outside the project
    would make that computation fail. Using dir=_ROOT keeps
    generate_fixtures.py completely untouched."""
    seed = random.randint(0, 2**31 - 1)
    with tempfile.TemporaryDirectory(dir=_ROOT, prefix=".synthetic_tmp_") as tmp_dir:
        generate(provider=provider_key, seed=seed, output_dir=Path(tmp_dir))
        employees_path = Path(tmp_dir) / provider_key / "employees_input.json"
        with employees_path.open(encoding="utf-8") as f:
            bundles = json.load(f)
    return list(zip(VARIANTS, bundles))
