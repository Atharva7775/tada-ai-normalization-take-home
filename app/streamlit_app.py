"""Tada AI Normalization - end-to-end app, all 5 steps.

A step-by-step wizard: each step is its own screen - only the current
step's UI is shown. You move forward with a "Next" button once that
step has something to carry into the next one, and back with a "Back"
button. Steps:
  1. Sign in - get base_url/auth/company identifiers for one or all
     three tenants.
  2. Pull one employee's full bundle from the live API.
  3. (Optional) Generate a synthetic employee instead of the live one,
     using the project's existing scripts/generate_fixtures.py generator -
     same generator, same scripted scenarios, nothing duplicated. Skipping
     this step (not clicking its button) just carries the live-pulled
     bundle forward unchanged.
  4. Convert whichever bundle is active (live or synthetic) into
     canonical form via the real adapters in src/normalization/adapters/.
  5. Save the canonical record into one shared SQLite database. The data
     itself isn't browsed inside this app - instead, download it as a
     plain .sql script and run it in any browser-based SQLite tool.

Run with:  streamlit run app/streamlit_app.py

Sign-in/pull/canonicalize/save/synthetic logic lives in
app/signin_client.py, app/data_client.py, app/canonicalize_client.py,
app/db_client.py, and app/synthetic_client.py, deliberately separate from
this UI file so a future non-Streamlit caller could reuse any of them.
Nothing here writes a token to disk - auth results live only in
st.session_state for the duration of the browser session, consistent
with the README's "keep returned tokens...out of Git and your
submission." The database itself (canonical.db) is a real file on disk,
gitignored like the project's other live-pulled artifacts.
"""
import os

import streamlit as st

from canonicalize_client import CanonicalizeError, canonicalize_employee
from data_client import DataPullError, pull_sample_employee_bundle
from db_client import export_sql, provider_counts, save_employee
from signin_client import TENANTS, SignInError, mask_token, sign_in
from synthetic_client import generate_synthetic_employee

st.set_page_config(page_title="Tada AI Normalization", page_icon="🔗", layout="centered")

if "wizard_step" not in st.session_state:
    st.session_state.wizard_step = 1
if "signed_in" not in st.session_state:
    st.session_state.signed_in = {}  # tenant selector -> SignInResult
if "sample_employee" not in st.session_state:
    st.session_state.sample_employee = {}  # tenant selector -> raw employee bundle dict (live pull)
if "synthetic_employee" not in st.session_state:
    st.session_state.synthetic_employee = {}  # tenant selector -> raw employee bundle dict (synthetic)
if "active_source" not in st.session_state:
    st.session_state.active_source = {}  # tenant selector -> "live" | "synthetic" - which bundle Step 4 converts
if "canonical_employee" not in st.session_state:
    st.session_state.canonical_employee = {}  # tenant selector -> canonical Employee dict
if "saved_to_db" not in st.session_state:
    st.session_state.saved_to_db = {}  # tenant selector -> True once saved this session

STEP_LABELS = ["Sign in", "Pull data", "Synthetic data (optional)", "Convert to canonical", "Save to database"]


def _goto(step: int) -> None:
    # Used as an on_click callback - Streamlit already reruns the script
    # after any callback, so no explicit st.rerun() is needed (and would
    # just be a no-op that prints a warning).
    st.session_state.wizard_step = step


def _use_live(t: str) -> None:
    st.session_state.active_source[t] = "live"
    st.session_state.canonical_employee.pop(t, None)  # stale - belonged to the synthetic bundle
    st.session_state.saved_to_db.pop(t, None)


st.title("Tada AI Normalization")

breadcrumb_cols = st.columns(len(STEP_LABELS))
for i, label in enumerate(STEP_LABELS, start=1):
    with breadcrumb_cols[i - 1]:
        if i < st.session_state.wizard_step:
            st.caption(f"✓ {i}. {label}")
        elif i == st.session_state.wizard_step:
            st.markdown(f"**{i}. {label}**")
        else:
            st.caption(f"{i}. {label}")
st.divider()

# ---------------------------------------------------------------------------
# Step 1 - sign in
# ---------------------------------------------------------------------------
if st.session_state.wizard_step == 1:
    st.header("Step 1 · Sign in")

    with st.expander("What this step does", expanded=False):
        st.markdown(
            "Calls the organizer's demo-provider-signin service "
            "(`POST https://tada-demo-provider-signin.onrender.com/signin`) for the "
            "selected tenant and returns its `base_url`, a short-lived auth token "
            "(PrismHR: `sessionId`; isolved/UKG: `access_token`), and the demo "
            "company identifiers to use in later steps. The API key is provided "
            "privately by the organizer and is never stored to disk here - it "
            "only lives in this browser tab's session while the app is open."
        )

    api_key = st.text_input(
        "Demo sign-in API key",
        value=os.environ.get("DEMO_SIGNIN_API_KEY", ""),
        type="password",
        key="api_key",
        help="Pre-filled from the DEMO_SIGNIN_API_KEY environment variable if it's set locally.",
    )

    tenant = st.selectbox(
        "Tenant",
        options=list(TENANTS.keys()),
        format_func=lambda t: f"{TENANTS[t]['label']}  ({t})",
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        sign_in_clicked = st.button("Sign In", type="primary", use_container_width=True)
    with col2:
        if tenant in st.session_state.signed_in:
            st.success(f"Already signed in to {TENANTS[tenant]['label']} this session.")

    if sign_in_clicked:
        if not api_key:
            st.error("Enter the API key first - it's required to call the sign-in service.")
        else:
            with st.spinner(f"Signing in to {TENANTS[tenant]['label']}..."):
                try:
                    result = sign_in(tenant, api_key)
                except SignInError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.signed_in[tenant] = result
                    st.success(f"Signed in to {TENANTS[tenant]['label']}.")

    st.caption("— or —")
    sign_in_all_clicked = st.button("Sign In to All Three Tenants", use_container_width=True)

    if sign_in_all_clicked:
        if not api_key:
            st.error("Enter the API key first - it's required to call the sign-in service.")
        else:
            successes, failures = [], []
            progress = st.empty()
            for i, t in enumerate(TENANTS, start=1):
                progress.info(f"Signing in to {TENANTS[t]['label']}... ({i}/{len(TENANTS)})")
                try:
                    result = sign_in(t, api_key)
                except SignInError as exc:
                    # One tenant's demo server can be slow/cold or fail
                    # independently of the others (we've seen this live -
                    # UKG's rate limiter, isolved's short token life) -
                    # never let one failure stop the remaining sign-ins.
                    failures.append((TENANTS[t]["label"], str(exc)))
                else:
                    st.session_state.signed_in[t] = result
                    successes.append(TENANTS[t]["label"])
            progress.empty()
            if successes:
                st.success("Signed in: " + ", ".join(successes))
            for label, message in failures:
                st.error(f"{label}: {message}")

    st.divider()
    st.subheader("Signed-in tenants this session")

    if not st.session_state.signed_in:
        st.info("No tenant signed in yet. Choose one above and click **Sign In**.")
    else:
        for t, result in st.session_state.signed_in.items():
            with st.container(border=True):
                st.markdown(f"**{TENANTS[t]['label']}**  ·  tenant_id `{result.tenant_id}`")

                left, right = st.columns(2)
                with left:
                    st.markdown("**base_url**")
                    st.code(result.base_url, language=None)
                    st.markdown("**auth**")
                    token_field = "sessionId" if "sessionId" in result.auth else "access_token"
                    st.code(f"{token_field}: {mask_token(result.token_value)}", language=None)
                    if result.auth.get("token_type"):
                        st.caption(f"token_type: {result.auth['token_type']}")
                    if result.auth.get("expires_in"):
                        st.caption(f"expires_in: {result.auth['expires_in']}s")

                with right:
                    st.markdown("**usage header**")
                    st.code(
                        f"{result.usage.get('header_name', '')}: "
                        f"{result.usage.get('header_prefix', '')}<token>",
                        language=None,
                    )
                    st.markdown(f"**companies ({len(result.company_identifiers)})**")
                    if result.company_identifiers:
                        with st.expander("Show companies"):
                            # st.json rather than st.dataframe: the latter
                            # requires pyarrow, which isn't guaranteed to be
                            # installable/binary-compatible in every
                            # environment this app runs in - st.json has no
                            # such dependency.
                            st.json(result.company_identifiers)
                    else:
                        st.caption("No companies returned.")

    st.divider()
    st.button(
        "Next: Pull employee data →", type="primary", use_container_width=True,
        disabled=not st.session_state.signed_in,
        on_click=_goto, args=(2,),
    )
    if not st.session_state.signed_in:
        st.caption("Sign in to at least one tenant to continue.")

# ---------------------------------------------------------------------------
# Step 2 - pull live data
# ---------------------------------------------------------------------------
elif st.session_state.wizard_step == 2:
    st.header("Step 2 · Pull live data")
    st.caption("One employee's full bundle per tenant - profile, direct deposits, and deductions.")

    for t, result in st.session_state.signed_in.items():
        with st.container(border=True):
            st.markdown(f"**{TENANTS[t]['label']}**")
            pull_clicked = st.button(
                "Pull 1 Employee's Full Bundle", key=f"pull_{t}", use_container_width=True,
                help="Profile + direct deposits + deductions for one employee - "
                     "everything this provider's adapter needs as input.",
            )
            if pull_clicked:
                with st.spinner(f"Pulling one employee's full bundle from {TENANTS[t]['label']}..."):
                    try:
                        employee = pull_sample_employee_bundle(t, result)
                    except DataPullError as exc:
                        if exc.token_expired:
                            lifetime = result.auth.get("expires_in")
                            lifetime_note = f" ({lifetime}s lifetime)" if lifetime else ""
                            st.error(
                                f"{TENANTS[t]['label']}'s session token has expired{lifetime_note}. "
                                f"Go back to Step 1 and click **Sign In** again for {TENANTS[t]['label']} "
                                "to get a fresh token - this step does not retry automatically."
                            )
                        else:
                            st.error(f"Could not pull a sample employee: {exc}")
                    else:
                        st.session_state.sample_employee[t] = employee
                        # Stale - all belong to the bundle this pull just replaced.
                        st.session_state.synthetic_employee.pop(t, None)
                        st.session_state.active_source.pop(t, None)  # defaults back to "live"
                        st.session_state.canonical_employee.pop(t, None)
                        st.success("Pulled 1 employee's full bundle.")

            if t in st.session_state.sample_employee:
                with st.expander(f"Raw employee bundle ({TENANTS[t]['label']})"):
                    st.caption(
                        "This exact dict is a valid input to "
                        f"ADAPTERS[\"{TENANTS[t]['provider_key']}\"].normalize(\"employee\", ..., reference)."
                    )
                    st.json(st.session_state.sample_employee[t])

    st.divider()
    col_back, col_next = st.columns(2)
    with col_back:
        st.button("← Back", use_container_width=True, on_click=_goto, args=(1,))
    with col_next:
        st.button(
            "Next: Synthetic data (optional) →", type="primary", use_container_width=True,
            disabled=not st.session_state.sample_employee,
            on_click=_goto, args=(3,),
        )
    if not st.session_state.sample_employee:
        st.caption("Pull at least one employee to continue.")

# ---------------------------------------------------------------------------
# Step 3 - synthetic data (optional)
# ---------------------------------------------------------------------------
elif st.session_state.wizard_step == 3:
    st.header("Step 3 · Synthetic data (optional)")
    st.caption(
        "Not interested in the live-pulled record? Generate a synthetic employee instead - "
        "same provider shape, fake data, no live API involved - and Step 4 will convert that "
        "instead. Skip this step entirely to convert the live-pulled bundle as-is."
    )

    with st.expander("What this step does", expanded=False):
        st.markdown(
            "Calls `generate_synthetic_employee()` (app/synthetic_client.py), a thin wrapper "
            "around this project's existing `scripts/generate_fixtures.py` - the exact same "
            "generator already used for this project's test fixtures, not a separate "
            "implementation. It writes to a disposable temp directory (never the committed "
            "`tests/fixtures/`), reads back one generated employee bundle, and discards the rest."
        )

    for t in st.session_state.sample_employee:
        with st.container(border=True):
            st.markdown(f"**{TENANTS[t]['label']}**")

            generate_clicked = st.button(
                "Generate Synthetic Data Instead", key=f"synth_{t}", use_container_width=True,
                help="Produces one fake employee for this provider via scripts/generate_fixtures.py "
                     "and makes it the active bundle for Step 4 - the live-pulled bundle from Step 2 "
                     "stays untouched and you can switch back to it below.",
            )
            if generate_clicked:
                with st.spinner(f"Generating a synthetic {TENANTS[t]['label']} employee..."):
                    synthetic = generate_synthetic_employee(TENANTS[t]["provider_key"])
                st.session_state.synthetic_employee[t] = synthetic
                st.session_state.active_source[t] = "synthetic"
                st.session_state.canonical_employee.pop(t, None)  # stale - belongs to whichever bundle was active before
                st.session_state.saved_to_db.pop(t, None)
                st.success("Generated 1 synthetic employee.")

            # Read AFTER the click handling above, so this reflects what
            # just happened on this exact rerun rather than lagging by one.
            source = st.session_state.active_source.get(t, "live")
            st.caption(f"Will convert in Step 4: **{'synthetic' if source == 'synthetic' else 'live'} data**")

            if t in st.session_state.synthetic_employee:
                with st.expander(f"Synthetic employee bundle ({TENANTS[t]['label']})"):
                    st.json(st.session_state.synthetic_employee[t])

                if source == "synthetic":
                    st.button(
                        "Use Live Data Instead", key=f"use_live_{t}", use_container_width=True,
                        on_click=_use_live, args=(t,),
                    )

    st.divider()
    col_back, col_next = st.columns(2)
    with col_back:
        st.button("← Back", use_container_width=True, on_click=_goto, args=(2,))
    with col_next:
        st.button(
            "Next: Convert to canonical form →", type="primary", use_container_width=True,
            on_click=_goto, args=(4,),
        )

# ---------------------------------------------------------------------------
# Step 4 - convert to canonical form
# ---------------------------------------------------------------------------
elif st.session_state.wizard_step == 4:
    st.header("Step 4 · Convert to canonical form")
    st.caption("Runs each tenant's active bundle (live or synthetic) through the real adapter in src/normalization/adapters/.")

    for t in st.session_state.sample_employee:
        source = st.session_state.active_source.get(t, "live")
        active_bundle = st.session_state.synthetic_employee[t] if source == "synthetic" else st.session_state.sample_employee[t]
        with st.container(border=True):
            st.markdown(f"**{TENANTS[t]['label']}** · converting *{source}* data")
            convert_clicked = st.button(
                "Convert to Canonical Form", key=f"convert_{t}", use_container_width=True,
                help="Runs the active bundle from Step 2/3 through the real adapter in "
                     "src/normalization/adapters/ to produce a canonical Employee record.",
            )
            if convert_clicked:
                with st.spinner(f"Converting {TENANTS[t]['label']}'s bundle to canonical form..."):
                    try:
                        canonical = canonicalize_employee(TENANTS[t]["provider_key"], active_bundle)
                    except CanonicalizeError as exc:
                        st.error(f"Could not convert this bundle: {exc}")
                    else:
                        st.session_state.canonical_employee[t] = canonical
                        st.session_state.saved_to_db.pop(t, None)  # stale - belongs to the old conversion
                        st.success("Converted to canonical form.")

            if t in st.session_state.canonical_employee:
                with st.expander(f"Canonical employee ({TENANTS[t]['label']})"):
                    st.caption("This is the provider-agnostic Employee record - same shape regardless of source.")
                    st.json(st.session_state.canonical_employee[t])

    st.divider()
    col_back, col_next = st.columns(2)
    with col_back:
        st.button("← Back", use_container_width=True, on_click=_goto, args=(3,))
    with col_next:
        st.button(
            "Next: Save to database →", type="primary", use_container_width=True,
            disabled=not st.session_state.canonical_employee,
            on_click=_goto, args=(5,),
        )
    if not st.session_state.canonical_employee:
        st.caption("Convert at least one employee to continue.")

# ---------------------------------------------------------------------------
# Step 5 - save to database
# ---------------------------------------------------------------------------
elif st.session_state.wizard_step == 5:
    st.header("Step 5 · Save to database")

    for t in st.session_state.canonical_employee:
        with st.container(border=True):
            st.markdown(f"**{TENANTS[t]['label']}**")
            save_clicked = st.button(
                "Save to Database", key=f"save_{t}", use_container_width=True,
                help="Writes the canonical record from Step 4 into canonical.db - updates the "
                     "existing row if this employee was already saved, never duplicates it.",
            )
            if save_clicked:
                with st.spinner(f"Saving {TENANTS[t]['label']}'s employee to the database..."):
                    save_employee(st.session_state.canonical_employee[t])
                    st.session_state.saved_to_db[t] = True

            if st.session_state.saved_to_db.get(t):
                st.success(f"Saved to the database as `{st.session_state.canonical_employee[t]['id']}`.")

    st.divider()
    st.subheader("Canonical database")

    counts = provider_counts()
    total_saved = sum(counts.values())
    if total_saved == 0:
        st.info("Nothing saved yet - click **Save to Database** above.")
    else:
        st.caption(" · ".join(f"{TENANTS[t]['label']}: {counts.get(TENANTS[t]['provider_key'], 0)}" for t in TENANTS))
        st.download_button(
            "Download canonical_export.sql",
            data=export_sql(),
            file_name="canonical_export.sql",
            mime="text/plain",
            use_container_width=True,
            help="A plain SQL script - CREATE TABLE plus INSERT statements for everything saved so far. "
                 "Paste/run it in any browser-based SQLite tool (e.g. sqliteonline.com, sqlite.org/fiddle) "
                 "to rebuild and browse this exact database there - nothing is shown inside this app.",
        )

    st.divider()
    st.button("← Back", use_container_width=True, on_click=_goto, args=(4,))
