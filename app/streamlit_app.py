"""Tada AI Normalization - end-to-end app, all 4 steps.

A step-by-step wizard: each step is its own screen - only the current
step's UI is shown. You move forward with a "Next" button once that
step has something to carry into the next one, and back with a "Back"
button. Steps:
  1. Sign in - get base_url/auth/company identifiers for one or all
     three tenants.
  2. Pull live data and/or generate synthetic data, side by side, per
     signed-in tenant. Pulling live data lets you choose how many of the
     tenant's signed-in companies to pull one employee from each - any
     count up to all of them. Generating synthetic data (optional) uses
     the project's existing scripts/generate_fixtures.py generator - same
     generator, same six scripted scenarios, nothing duplicated. When a
     tenant has both, a toggle picks which one is "active"; the active
     source is what the next step converts.
  3. Convert whichever bundles are active (live or synthetic) per tenant
     into canonical form via the real adapters in
     src/normalization/adapters/.
  4. Save the canonical records into one shared SQLite database. The data
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
import html
import os

import streamlit as st

from canonicalize_client import CanonicalizeError, canonicalize_employee
from data_client import DataPullError, pull_employee_bundles
from db_client import TABLE_NAMES, export_sql, fetch_table, save_employee
from signin_client import TENANTS, SignInError, mask_token, sign_in
from synthetic_client import generate_synthetic_employees

st.set_page_config(page_title="Tada AI Normalization", page_icon="🔗", layout="centered")

# st.json() has no built-in height cap - left alone, a large bundle renders
# fully expanded and stretches the whole page, so two JSON viewers open side
# by side (e.g. live "Raw bundles" next to "Synthetic bundles" in Step 2)
# visually run together. Capping height and adding our own scrollbar per
# viewer keeps each one visually self-contained regardless of how much is
# expanded inside it.
st.markdown(
    """
    <style>
    div[data-testid="stJson"] {
        max-height: 420px;
        overflow-y: auto;
        overflow-x: auto;
    }
    div[data-testid="stMarkdownContainer"] table td,
    div[data-testid="stMarkdownContainer"] table th {
        padding: 4px 10px;
        white-space: nowrap;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        text-align: left;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "wizard_step" not in st.session_state:
    st.session_state.wizard_step = 1
if "signed_in" not in st.session_state:
    st.session_state.signed_in = {}  # tenant selector -> SignInResult
if "sample_employees" not in st.session_state:
    st.session_state.sample_employees = {}  # tenant selector -> list of raw employee bundle dicts (live pull, one per company)
if "synthetic_employee" not in st.session_state:
    st.session_state.synthetic_employee = {}  # tenant selector -> {variant_name: raw employee bundle dict} (all 6)
if "active_source" not in st.session_state:
    st.session_state.active_source = {}  # tenant selector -> "live" | "synthetic" - only consulted when a tenant has BOTH
if "canonical_employees" not in st.session_state:
    st.session_state.canonical_employees = {}  # tenant selector -> list of canonical Employee dicts
if "saved_to_db" not in st.session_state:
    st.session_state.saved_to_db = {}  # tenant selector -> count saved this session
if "saved_employee_ids" not in st.session_state:
    st.session_state.saved_employee_ids = set()  # canonical employee ids saved this session, any tenant

STEP_LABELS = ["Sign in", "Pull or generate data", "Data normalization", "Save to database"]


def _goto(step: int) -> None:
    # Used as an on_click callback - Streamlit already reruns the script
    # after any callback, so no explicit st.rerun() is needed (and would
    # just be a no-op that prints a warning).
    st.session_state.wizard_step = step


def _effective_source(t: str):
    """Which source (live/synthetic) is active for tenant t, or None if
    neither has anything yet. Only tenants with BOTH live and synthetic
    data actually consult st.session_state.active_source - with just one
    side populated, that side is unambiguously "the" active source, no
    stored flag needed."""
    has_live = bool(st.session_state.sample_employees.get(t))
    has_synthetic = t in st.session_state.synthetic_employee
    if has_live and has_synthetic:
        return st.session_state.active_source.get(t, "live")
    if has_synthetic:
        return "synthetic"
    if has_live:
        return "live"
    return None


def _active_bundles(t: str):
    """The list of raw bundles Step 3 should convert for tenant t - every
    live-pulled company's bundle if the active source is "live", or all
    six scripted-variant synthetic bundles if "synthetic"."""
    source = _effective_source(t)
    if source == "live":
        return st.session_state.sample_employees.get(t) or []
    if source == "synthetic":
        return list(st.session_state.synthetic_employee.get(t, {}).values())
    return []


def _invalidate_downstream(t: str) -> None:
    st.session_state.canonical_employees.pop(t, None)
    st.session_state.saved_to_db.pop(t, None)


def _render_sql_table(columns, rows) -> None:
    """Renders a SELECT * result as a plain HTML table inside a scrollable
    box - both axes scroll independently (overflow: auto on the wrapper,
    nowrap cells so wide columns trigger the horizontal scrollbar instead
    of wrapping awkwardly). Deliberately not st.dataframe()/st.table():
    both require pyarrow, which this project's st.json() comment
    elsewhere already notes isn't guaranteed installable/binary-compatible
    in every environment this app runs in - a plain <table> has no such
    dependency."""
    thead = "".join(f"<th>{html.escape(str(c))}</th>" for c in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{'' if v is None else html.escape(str(v))}</td>" for v in row)
        body_rows.append(f"<tr>{cells}</tr>")
    tbody = "".join(body_rows) or f'<tr><td colspan="{len(columns)}"><em>No rows yet.</em></td></tr>'
    st.markdown(
        f"""
        <div style="max-height:420px; overflow:auto; border:1px solid rgba(128,128,128,0.3); border-radius:0.5rem;">
          <table style="border-collapse:collapse; width:max-content; min-width:100%; font-size:0.85rem;">
            <thead style="position:sticky; top:0;">
              <tr style="background:rgba(128,128,128,0.25);">{thead}</tr>
            </thead>
            <tbody>{tbody}</tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
        "Next: Pull or generate data →", type="primary", use_container_width=True,
        disabled=not st.session_state.signed_in,
        on_click=_goto, args=(2,),
    )
    if not st.session_state.signed_in:
        st.caption("Sign in to at least one tenant to continue.")

# ---------------------------------------------------------------------------
# Step 2 - pull live data and/or generate synthetic data
# ---------------------------------------------------------------------------
elif st.session_state.wizard_step == 2:
    st.header("Step 2 · Pull or generate data")
    st.caption(
        "Per tenant: pull real employees from the live API (left), and/or generate fake ones "
        "(right) - same provider shape, no live API involved. If you do both, pick which one "
        "Step 3 converts."
    )

    for t, result in st.session_state.signed_in.items():
        st.markdown(f"### {TENANTS[t]['label']}")
        col_live, col_synth = st.columns(2)

        # --- live pull -------------------------------------------------
        with col_live:
            with st.container(border=True):
                st.markdown(
                    "**Pull live data**",
                    help=(
                        "**Function:** `data_client.pull_employee_bundles()`\n\n"
                        "**What this does:** makes real HTTP calls to this tenant's live "
                        "demo API, using the auth token from Step 1's sign-in - no fake "
                        "data involved. For each company you pull from (up to the count "
                        "you choose below), it fetches one real employee's full bundle: "
                        "profile, direct deposits, and deductions. A company with zero "
                        "employees is skipped (and reported as skipped), not treated as "
                        "an error."
                    ),
                )
                total_companies = len(result.company_identifiers)
                st.caption(f"{total_companies} compan{'y' if total_companies == 1 else 'ies'} signed in")

                if total_companies > 1:
                    pull_all = st.checkbox(f"Pull from all {total_companies}", key=f"pull_all_{t}")
                    count = st.number_input(
                        "Companies to pull from", min_value=1, max_value=total_companies, value=1, step=1,
                        disabled=pull_all, key=f"pull_count_{t}",
                        help="One employee is pulled per company.",
                    )
                    effective_count = None if pull_all else int(count)
                else:
                    effective_count = 1

                pull_clicked = st.button(
                    "Pull Live Data", key=f"pull_{t}", use_container_width=True,
                    help="Profile + direct deposits + deductions for one employee per company - "
                         "everything this provider's adapter needs as input.",
                )
                if pull_clicked:
                    requested = total_companies if effective_count is None else effective_count
                    with st.spinner(f"Pulling live data from {TENANTS[t]['label']}..."):
                        try:
                            bundles, skipped = pull_employee_bundles(t, result, count=effective_count)
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
                                st.error(f"Could not pull live data: {exc}")
                        else:
                            st.session_state.sample_employees[t] = bundles
                            st.session_state.active_source[t] = "live"
                            _invalidate_downstream(t)
                            if skipped:
                                st.success(
                                    f"Pulled {len(bundles)} of {requested} requested employee bundle(s) "
                                    f"({len(skipped)} compan{'y' if len(skipped) == 1 else 'ies'} skipped)."
                                )
                                for cid, reason in skipped:
                                    st.caption(f"Skipped `{cid}`: {reason}")
                            else:
                                st.success(f"Pulled {len(bundles)} employee bundle(s).")

                if t in st.session_state.sample_employees:
                    bundles = st.session_state.sample_employees[t]
                    with st.expander(f"Raw bundles ({len(bundles)})"):
                        st.caption(
                            "Each entry is a valid input to "
                            f"ADAPTERS[\"{TENANTS[t]['provider_key']}\"].normalize(\"employee\", ..., reference)."
                        )
                        st.json(bundles)

        # --- synthetic data ----------------------------------------------
        with col_synth:
            with st.container(border=True):
                st.markdown(
                    "**Generate synthetic data**",
                    help=(
                        "**Function:** `synthetic_client.generate_synthetic_employees()` "
                        "(a thin wrapper around `scripts/generate_fixtures.py`'s `generate()`)\n\n"
                        "**What this does:** fabricates fake employee data locally, in the "
                        "exact same shape a live pull produces - no live API call, no "
                        "credentials used, nothing sent over the network. Every click "
                        "produces the same six scripted scenarios, each designed to "
                        "exercise a specific normalization edge case:\n\n"
                        "1. **active_simple** - the happy path\n"
                        "2. **terminated** - termination date/reason populated\n"
                        "3. **on_leave_or_undocumented** - an on-leave / undocumented "
                        "status never observed in this project's live sample\n"
                        "4. **no_deposits_no_deductions** - exercises the empty-list "
                        "defaults\n"
                        "5. **multiple_deposits** - exercises every direct-deposit "
                        "allocation-method branch\n"
                        "6. **unknown_status_code** - a deliberately made-up status code, "
                        "to prove the adapter's OTHER/UNKNOWN fallback never raises"
                    ),
                )
                st.caption("Optional - fake data, no live API involved.")

                generate_clicked = st.button(
                    "Generate Synthetic Data", key=f"synth_{t}", use_container_width=True,
                    help="Produces all six scripted-variant fake employees for this provider "
                         "via scripts/generate_fixtures.py - all six are shown below and all "
                         "six are used in Step 3.",
                )
                if generate_clicked:
                    with st.spinner(f"Generating 6 synthetic {TENANTS[t]['label']} employees..."):
                        variants = dict(generate_synthetic_employees(TENANTS[t]["provider_key"]))
                    st.session_state.synthetic_employee[t] = variants
                    st.session_state.active_source[t] = "synthetic"
                    _invalidate_downstream(t)
                    st.success(f"Generated {len(variants)} synthetic employees.")

                if t in st.session_state.synthetic_employee:
                    variants = st.session_state.synthetic_employee[t]
                    with st.expander(f"Synthetic bundles ({len(variants)})"):
                        for variant_name, bundle in variants.items():
                            st.markdown(f"**{variant_name}**")
                            st.json(bundle)

        # --- active-source toggle (only meaningful once both exist) ------
        has_live = bool(st.session_state.sample_employees.get(t))
        has_synthetic = t in st.session_state.synthetic_employee
        if has_live and has_synthetic:
            current = st.session_state.active_source.get(t, "live")
            live_n = len(st.session_state.sample_employees[t])
            synthetic_n = len(st.session_state.synthetic_employee[t])
            choice = st.radio(
                f"Use for {TENANTS[t]['label']} in Step 3:",
                options=["live", "synthetic"],
                index=0 if current == "live" else 1,
                format_func=lambda s, live_n=live_n, synthetic_n=synthetic_n: (
                    f"Live data ({live_n} employee{'s' if live_n != 1 else ''})" if s == "live"
                    else f"Synthetic data ({synthetic_n} employees)"
                ),
                key=f"active_source_radio_{t}", horizontal=True,
            )
            if choice != current:
                st.session_state.active_source[t] = choice
                _invalidate_downstream(t)
        elif has_live:
            st.caption(f"Will convert in Step 3: **live data** ({len(st.session_state.sample_employees[t])} employee(s))")
        elif has_synthetic:
            st.caption(f"Will convert in Step 3: **synthetic data** ({len(st.session_state.synthetic_employee[t])} employees)")
        else:
            st.caption("Pull live data or generate synthetic data above to continue with this tenant.")

        st.divider()

    ready_tenants = [t for t in st.session_state.signed_in if _effective_source(t)]
    live_tenants = [t for t in ready_tenants if _effective_source(t) == "live"]
    synthetic_tenants = [t for t in ready_tenants if _effective_source(t) == "synthetic"]

    if live_tenants and synthetic_tenants:
        next_label = f"Next: Convert {len(live_tenants)} live + {len(synthetic_tenants)} synthetic →"
    elif live_tenants:
        next_label = "Next: Convert live data →"
    elif synthetic_tenants:
        next_label = "Next: Convert synthetic data →"
    else:
        next_label = "Next: Convert to normalization form →"

    col_back, col_next = st.columns(2)
    with col_back:
        st.button("← Back", use_container_width=True, on_click=_goto, args=(1,))
    with col_next:
        st.button(
            next_label, type="primary", use_container_width=True,
            disabled=not ready_tenants,
            on_click=_goto, args=(3,),
        )
    if not ready_tenants:
        st.caption("Pull live data or generate synthetic data for at least one tenant to continue.")

# ---------------------------------------------------------------------------
# Step 3 - data normalization
# ---------------------------------------------------------------------------
elif st.session_state.wizard_step == 3:
    st.header("Step 3 · Data normalization")
    st.caption("Runs each tenant's active bundle(s) (live or synthetic) through the real adapter in src/normalization/adapters/.")

    tenants_ready = [t for t in st.session_state.signed_in if _active_bundles(t)]
    for t in tenants_ready:
        source = _effective_source(t)
        bundles = _active_bundles(t)
        with st.container(border=True):
            st.markdown(f"**{TENANTS[t]['label']}** · converting {len(bundles)} *{source}* record(s)")
            convert_clicked = st.button(
                "Convert to Normalization Form", key=f"convert_{t}", use_container_width=True,
                help="Runs each active bundle from Step 2 through the real adapter in "
                     "src/normalization/adapters/ to produce a normalization Employee record.",
            )
            if convert_clicked:
                canonical_list, errors = [], []
                with st.spinner(f"Converting {len(bundles)} {TENANTS[t]['label']} bundle(s) to normalization form..."):
                    for bundle in bundles:
                        try:
                            canonical_list.append(canonicalize_employee(TENANTS[t]["provider_key"], bundle))
                        except CanonicalizeError as exc:
                            errors.append(str(exc))
                if canonical_list:
                    st.session_state.canonical_employees[t] = canonical_list
                    st.session_state.saved_to_db.pop(t, None)  # stale - belongs to the old conversion
                    st.success(f"Converted {len(canonical_list)} employee(s) to normalization form.")
                for err in errors:
                    st.error(f"Could not convert one bundle: {err}")

            if t in st.session_state.canonical_employees:
                canonical_list = st.session_state.canonical_employees[t]
                with st.expander(f"Normalization employees ({len(canonical_list)})"):
                    st.caption("Provider-agnostic Employee records - same shape regardless of source.")
                    st.json(canonical_list)

    st.divider()
    col_back, col_next = st.columns(2)
    with col_back:
        st.button("← Back", use_container_width=True, on_click=_goto, args=(2,))
    with col_next:
        st.button(
            "Next: Save to database →", type="primary", use_container_width=True,
            disabled=not st.session_state.canonical_employees,
            on_click=_goto, args=(4,),
        )
    if not st.session_state.canonical_employees:
        st.caption("Convert at least one employee to continue.")

# ---------------------------------------------------------------------------
# Step 4 - save to database
# ---------------------------------------------------------------------------
elif st.session_state.wizard_step == 4:
    st.header("Step 4 · Save to database")

    for t, canonical_list in st.session_state.canonical_employees.items():
        with st.container(border=True):
            st.markdown(f"**{TENANTS[t]['label']}** · {len(canonical_list)} record(s) ready")
            save_clicked = st.button(
                "Save to Database", key=f"save_{t}", use_container_width=True,
                help="Writes every normalization record from Step 3 into canonical.db - updates the "
                     "existing row for any employee already saved, never duplicates it.",
            )
            if save_clicked:
                with st.spinner(f"Saving {len(canonical_list)} {TENANTS[t]['label']} employee(s) to the database..."):
                    for canonical in canonical_list:
                        save_employee(canonical)
                        st.session_state.saved_employee_ids.add(canonical["id"])
                    st.session_state.saved_to_db[t] = len(canonical_list)
                st.success(f"Saved {len(canonical_list)} employee(s).")

            if st.session_state.saved_to_db.get(t):
                st.success(f"{st.session_state.saved_to_db[t]} {TENANTS[t]['label']} employee(s) saved to the database.")

    st.divider()
    st.subheader("Normalization database")

    # Everything below is deliberately scoped to st.session_state.saved_employee_ids
    # - the canonical employee ids THIS session has actually saved - not a
    # whole-file query. canonical.db is a single shared, persistent file
    # (every run, past and future, writes into the same one), so an
    # unfiltered SELECT * would mix in rows from every other run too (e.g.
    # leftover isolved/UKG Ready rows from earlier testing even if this run
    # only touched PrismHR). Filtering by this session's own saved ids is
    # what keeps the count, the download, and the browse table all showing
    # only what THIS run actually did.
    session_counts = {
        TENANTS[t]["provider_key"]: n for t, n in st.session_state.saved_to_db.items() if n
    }
    st.caption(
        "Saved this run: "
        + " · ".join(f"{TENANTS[t]['label']}: {session_counts.get(TENANTS[t]['provider_key'], 0)}" for t in TENANTS)
    )

    saved_ids = st.session_state.saved_employee_ids
    if not saved_ids:
        st.info("Nothing saved yet this run - click **Save to Database** above.")
    else:
        st.download_button(
            "Download canonical_export.sql",
            data=export_sql(employee_ids=saved_ids),
            file_name="canonical_export.sql",
            mime="text/plain",
            use_container_width=True,
            help="A plain SQL script - CREATE TABLE plus INSERT statements - for only the "
                 f"{len(saved_ids)} employee(s) THIS session saved (across all four tables: "
                 "employees, pay_rates, direct_deposits, deduction_setups), not canonical.db's "
                 "full history. Paste/run it in any browser-based SQLite tool (e.g. "
                 "sqliteonline.com, sqlite.org/fiddle) to rebuild and browse it there - nothing "
                 "is shown inside this app.",
        )

        st.divider()
        st.markdown(
            "**Browse normalization data**",
            help=(
                "Runs `SELECT * FROM <table>` for whichever table you pick below, filtered "
                "down to just the employee(s) THIS session saved - not canonical.db's full "
                "history, even though that file also holds rows from other runs."
            ),
        )
        selected_table = st.selectbox("Table", options=TABLE_NAMES, key="browse_table_select")
        columns, rows = fetch_table(selected_table, employee_ids=saved_ids)
        st.caption(f"{len(rows)} row(s) · {len(columns)} column(s) · this run only")
        _render_sql_table(columns, rows)

    st.divider()
    st.button("← Back", use_container_width=True, on_click=_goto, args=(3,))
