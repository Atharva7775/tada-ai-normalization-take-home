# Running this project

Two parts: setting up and running everything from the terminal, and running the
Streamlit app. (For the approach/architecture write-up, see [README.md](README.md);
for the original assignment brief, see [ASSIGNMENT.md](ASSIGNMENT.md).)

## Part 1 · Setup and terminal usage

Clone and install dependencies:

```sh
git clone https://github.com/Atharva7775/tada-ai-normalization-take-home.git
cd tada-ai-normalization-take-home
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the adapter test suite (23 tests, against the deterministic synthetic
fixtures already committed under `tests/fixtures/` - no credentials needed):

```sh
PYTHONPATH=src python3 -m pytest tests/ -q
```

Regenerate the synthetic fixtures (optional - deterministic, no credentials,
no network calls):

```sh
python3 scripts/generate_fixtures.py          # all three providers
python3 scripts/generate_fixtures.py prismhr  # one provider only
```

Run a single adapter conversion directly from the command line, no Streamlit:

```sh
cd src
python3 -m normalization list-providers
python3 -m normalization normalize --provider prismhr --entity company \
  --input ../tests/fixtures/prismhr/company_input.json \
  --output /tmp/prismhr_company_canonical.json
cat /tmp/prismhr_company_canonical.json
cd ..
```

`--input` must be a single provider-shaped response (a plain JSON object).
`tests/fixtures/<provider>/company_input.json` and `payroll_input.json` are
single objects; `employees_input.json` is a list of six scripted employee
bundles - pick one entry (e.g. with `jq '.[0]'`) before passing it in.

To pull real live demo data instead of synthetic fixtures, set the API key
the organizer provided. See this repo's [ASSIGNMENT.md](ASSIGNMENT.md#access-live-demo-data)
for the sign-in endpoint details, and `postman/` for a ready-to-import Postman
collection covering all three provider APIs:

```sh
export DEMO_SIGNIN_API_KEY=<key the organizer gave you>
```

## Part 2 · Streamlit UI

Needs `DEMO_SIGNIN_API_KEY` set (see above) to sign in to the three live demo
tenants - the synthetic-data step works without it.

```sh
streamlit run app/streamlit_app.py
```

Opens at `http://localhost:8501`. The app is a 4-step wizard - each step is
its own screen, with Back/Next buttons to move through it. Every section
with a small **ⓘ** icon next to its heading has a hover tooltip explaining
exactly which function it calls and what it does.

1. **Sign in** - enter the API key, then sign in to one tenant or all three
   (PrismHR, isolved, UKG Ready).
2. **Pull or generate data** - per signed-in tenant, two options side by
   side:
   - **Pull live data** - choose how many of the tenant's companies to pull
     from (1 up to "all N"), then pulls one real employee's full bundle
     (profile, direct deposits, deductions) per company. A company with
     zero employees is skipped and reported as skipped (e.g. "Pulled 2 of 4
     requested employee bundle(s) (2 companies skipped)"), not treated as
     an error.
   - **Generate synthetic data** - produces all six scripted scenarios at
     once (see Part 1's "Regenerate the synthetic fixtures"), shown
     together in one expander, no live API involved.

   If a tenant has both live and synthetic data, a radio toggle picks which
   one Step 3 converts; the "Next" button's label updates dynamically to
   say what it's about to convert (e.g. "Next: Convert 2 live + 1 synthetic
   →").
3. **Data normalization** - runs each tenant's active bundle(s) (live or
   synthetic, however many employees that is) through the real adapter in
   `src/normalization/adapters/`, producing canonical `Employee` records.
4. **Save to database** - writes the canonical records into `canonical.db`
   (SQLite, gitignored - never committed). The "Normalization database"
   section below the save buttons is scoped to **this session only** (not
   the whole file, which persists across every run) and offers:
   - **Download canonical_export.sql** - a plain SQL script (`CREATE TABLE`
     + `INSERT` statements) for just the employee(s) *this session* saved,
     across all four tables (`employees`, `pay_rates`, `direct_deposits`,
     `deduction_setups`). Paste/run it in any browser-based SQLite tool
     (e.g. sqliteonline.com, sqlite.org/fiddle) to rebuild and browse it
     there.
   - **Browse normalization data** - a dropdown to pick any of the same
     four tables; runs `SELECT * FROM <table>` (filtered to this session's
     saved employees) and renders every row and column in a scrollable
     table, right inside the app.

To stop the app, press `Ctrl+C` in the terminal it's running in.
