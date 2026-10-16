# Running this project

Setup once, then run it two ways: from the terminal (Part 1), or through the
Streamlit app (Part 2). For the approach/architecture write-up, see
[README.md](README.md); for the original assignment brief, see
[ASSIGNMENT.md](ASSIGNMENT.md).

## Part 1 · Terminal

### Setup

```sh
git clone https://github.com/Atharva7775/tada-ai-normalization-take-home.git
cd tada-ai-normalization-take-home
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the test suite (23 tests, synthetic data only, no credentials needed):

```sh
PYTHONPATH=src python3 -m pytest tests/ -q
```

### 1. Run live data

Pulls one real employee from a provider's live demo tenant and converts it
to canonical form - no Streamlit needed.

Set your API key first:

```sh
export DEMO_SIGNIN_API_KEY=<key the organizer gave you>
```

Open `scripts/pull_live_and_normalize.py` and edit these three lines near
the top:

```python
TENANT = "prism"          # "prism" (PrismHR) | "isol" (isolved) | "ukg" (UKG Ready)
PROVIDER_KEY = "prismhr"  # "prismhr" | "isolved" | "ukg-ready" - must match TENANT above
COUNT = 1                 # how many companies to pull one employee from; None = all companies
```

Then run it:

```sh
python3 scripts/pull_live_and_normalize.py
```

Change the tenant and re-run any time - no need to retype anything in the
terminal.

**What it does:** signs in (`sign_in()`), pulls one employee per company
(`pull_employee_bundles()`), then converts each one through the real
adapter (`canonicalize_employee()`, which calls
`ADAPTERS[provider_key].normalize(...)`). Output lands in
`adapter_demo_run/<provider_key>/employee_<i>_canonical.json` (gitignored,
never committed).

**Why use this script instead of the `normalize` CLI below for live data?**
isolved and UKG Ready are blocked by that CLI's built-in licensing check
(details in `ASSUMPTIONS_AND_DECISIONS.md`). This script calls the adapter
directly, so it works for all three providers.

### 2. Synthetic data

Generates fake-but-realistic test data locally - no credentials, no
network calls, same output every time you run it.

Generate it:

```sh
python3 scripts/generate_fixtures.py             # all three providers
python3 scripts/generate_fixtures.py prismhr      # one provider only
```

Writes `company_input.json`, `employees_input.json` (6 test scenarios -
active, terminated, on leave, no deposits, multiple deposits, and an
unrecognized status), and `payroll_input.json` into
`tests/fixtures/<provider>/`.

Convert one of these files to canonical form:

```sh
cd src
python3 -m normalization list-providers
python3 -m normalization normalize --provider prismhr --entity company \
  --input ../tests/fixtures/prismhr/company_input.json \
  --output /tmp/prismhr_company_canonical.json
cat /tmp/prismhr_company_canonical.json
cd ..
```

`--input` needs one plain JSON object. `company_input.json` and
`payroll_input.json` are already single objects; `employees_input.json` is
a list of 6 - pull one entry out first, e.g.
`jq '.[0]' tests/fixtures/prismhr/employees_input.json > /tmp/one_employee.json`.

## Part 2 · Streamlit app

Set your API key (same as Part 1) to use live data - synthetic data works
without it.

```sh
streamlit run app/streamlit_app.py
```

Opens at `http://localhost:8501`. It's a 4-step wizard; every **ⓘ** icon has
a tooltip explaining what that section does and which function it calls.

1. **Sign in** - pick a tenant (PrismHR, isolved, or UKG Ready) and sign in,
   or sign in to all three at once.
2. **Pull or generate data** - for each signed-in tenant:
   - **Pull live data** - choose how many companies to pull from, then
     pulls one real employee per company.
   - **Generate synthetic data** - makes all 6 test scenarios at once, no
     live API involved.

   If a tenant has both, pick which one to convert next.
3. **Data normalization** - converts the chosen data through the real
   adapter (`src/normalization/adapters/`).
4. **Save to database** - saves to `canonical.db` (gitignored). From here
   you can download a SQL export or browse the saved tables, both scoped to
   just this session's saves.

**Per tenant:** repeat Step 1 for PrismHR, isolved, and UKG Ready (or sign
in to all three at once), then use each tenant's own card in Step 2. A
company with zero employees is skipped automatically; UKG Ready's demo
tenant only has 1 company. Steps 3-4 work the same for every tenant.

To stop the app, press `Ctrl+C`.
