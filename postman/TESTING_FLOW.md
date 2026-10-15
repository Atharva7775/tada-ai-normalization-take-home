# Testing the provider APIs with Postman

This folder has two files to import into Postman:

- `Tada AI Normalization - Provider APIs.postman_collection.json` — the requests
- `Tada AI Normalization - Demo.postman_environment.json` — the variables the requests use

Both are generated from the reference specs in `contracts/` (PrismHR's OpenAPI
file, isolved's primary swagger snapshot, and UKG Ready's cached reference
docs), not guessed. They cover the four data types from the README: company +
full employee data, direct deposits, deductions, and payroll/paycheck data,
for all three providers.

## What "is it working" means here

Every request's **Tests** tab checks four layers, in order, so a failure
always points at the right one instead of a bare "test failed":

1. **HTTP status is 200.**
2. **The body actually parses as JSON.** This catches the class of bug where
   a request 200s (or 404s) with an HTML error page instead of the API's
   JSON body — e.g. the "Bad Robot" page UKG's web-app routing serves when a
   URL is built wrong. If this layer fails, every later layer is skipped
   automatically (no misleading cascade of unrelated failures) and the test
   output prints the first 300 characters of the raw body so you can see
   what you actually got back.
3. **(PrismHR only) No business error embedded in the 200.** PrismHR wraps
   every response in `{errorCode, errorMessage, ...}` and returns HTTP 200
   even when `errorCode` is non-zero — so HTTP status alone can lie about
   whether the call actually worked. This layer fails loudly with the real
   `errorCode`/`errorMessage` if PrismHR rejected the call.
4. **The documented response field contains the right shape of data** — an
   array where the spec says array (or a required field for sign-in), and an
   object with its identifying field for single-record lookups. Discovery
   endpoints that the rest of the collection depends on (client/company
   lists, employee lists, isolved's pay-group discovery, UKG's payroll list)
   additionally require at least one item, since an empty list there would
   stall every downstream request. Per-employee detail endpoints (deductions,
   direct deposits, checks, payroll vouchers) only check the shape, not
   non-emptiness — the demo employee may legitimately have zero of any of
   these configured, and that isn't a bug.

## 1. Import

1. Postman → **Import** → select both JSON files (or drag them in together).
2. Top-right environment dropdown → select **Tada AI Normalization - Demo**.

## 2. Set the one secret you need

Open the environment, set `demo_signin_api_key` to the key the organizer gave
you privately. Never commit this value — the environment file ships with it
blank, and `postman/*.postman_environment.json` holding a real key should
stay out of git (check `.gitignore` before committing if you save it back).

## 3. Run the sign-in requests (once per session)

Open folder **`0 - Sign In (run these first)`** and run, in order:

1. **Sign In - PrismHR (tenant=prism)**
2. **Sign In - isolved (tenant=isol)**
3. **Sign In - UKG Ready (tenant=ukg)**

Each is `POST {{signin_base_url}}/signin` with `X-API-Key` and
`{"tenant": "..."}`. Each request's **Tests** script reads the JSON response
and auto-fills the environment:

| Request | Variables it sets |
| --- | --- |
| Sign In - PrismHR | `prismhr_session_id`, `prismhr_base_url`, `prismhr_client_id` |
| Sign In - isolved | `isolved_access_token`, `isolved_refresh_token`, `isolved_base_url`, `isolved_client_id`, `isolved_legal_id` |
| Sign In - UKG Ready | `ukg_access_token`, `ukg_base_url`, `ukg_company_id` |

You don't need to copy anything by hand — if a sign-in request returns 200,
the next folder's requests already have what they need. Check the response
body once to confirm the shape matches what the Tests script expects (see
Troubleshooting below if a variable comes back empty).

## 4. Walk each provider folder top to bottom

Each folder is ordered so that earlier requests discover the ids later
requests need, saving them into the environment automatically:

### PrismHR (header auth: `sessionId`)

1. **Get Client List** — confirms `prismhr_client_id` from sign-in is valid.
2. **Get Employee List** — saves the first `employeeId` into `prismhr_employee_id`.
3. **Get Employee** (with `options=DirectDeposit`) — full profile + the
   `achVoucher`/`directDepositChecksum` you'd need to call `updateDirectDeposit`.
4. **Get ACH Deductions**, **Get Deductions**, **Get Voluntary Recurring
   Deductions**, **Get Scheduled Deductions** — the four deduction/direct-deposit
   read endpoints PrismHR splits this across.
5. **Get Employee Payroll Vouchers**, **Get Employee Payroll Summary**, **Get
   Payroll Vouchers** — paycheck and payroll-run data. The two voucher
   requests have a pre-request script that defaults the date range to the
   trailing 12 months if you haven't set `prismhr_pay_date_start`/`_end`
   yourself.

### isolved (header auth: `Authorization: Bearer {{isolved_access_token}}`)

Uses the **primary** swagger snapshot only
(`contracts/isolved/openapi/isolved-v6.swagger.json`) — the alternate snapshot
in that folder is for comparison, not for building requests against.

1. **Get Clients**, **Get Legals for Client** — confirms/fills
   `isolved_client_id` / `isolved_legal_id` (sign-in already provides both for
   the demo tenant, so this mostly double-checks them).
2. **Get Employees** — saves the first employee id into `isolved_employee_id`.
3. **Get Employee by Id**, **Get Employee Direct Deposits**, **Get Employee
   Pay Items**, **Get Employee Deductions (corestream)**, **Get Employee
   Checks** — profile, direct deposit, deduction, and paycheck data for that
   employee.
4. **Get Legal + Pay Groups + Payroll Schedules** — saves a `payGroupId` into
   `isolved_paygroup_id` (there's no plain "list pay groups" endpoint, so this
   corestream endpoint is how you discover one).
5. **Get Payroll Run History** — payroll runs for that pay group.

### UKG Ready (header auth: `Authorization: Bearer {{ukg_access_token}}`)

No official OpenAPI contract exists for UKG Ready — every endpoint here was
read out of the cached pages in `contracts/ukg-ready/reference-docs/res/`.
There's also no companies-list endpoint in the docs, so `ukg_company_id`
comes only from the sign-in response.

**Known gotcha:** the demo sign-in's `base_url` for UKG comes back as
`https://<pod>.saashr.com/ta` — one path segment short of UKG's documented
API root, `https://<pod>.saashr.com/ta/rest` (see `Foundations.html` /
`Quickstart.html`). Every UKG request in this collection therefore builds its
URL as `{{ukg_base_url}}/rest/v2/companies/...`, not `{{ukg_base_url}}/v2/companies/...`.
If you ever see a 404 that renders as a branded HTML error page (not UKG's
documented JSON error body, `{"errors":[...]}`) instead of a normal API
response, you've hit this: the request landed on the SaaS web app's routing
instead of the REST API. UKG's own status-code reference confirms a real
404 only happens for `/{id}` lookups, never for a plain collection `GET` like
`/employees` — so an HTML 404 on a list endpoint is always a URL-construction
bug, not "no data."

1. **Get Employees** — saves the first employee id into `ukg_employee_id`.
2. **Get Employee by Id** — full employee record.
3. **Get Employee Direct Deposits** — UKG marked this endpoint deprecated in
   April 2023, but it's documented as still functional under their
   deprecation policy, which is why the request sends the required
   `X-End-of-Support-Timeline: 2026-01-29` header.
4. **Get Employee Deductions** — scheduled deduction setup.
5. **Get Payrolls** — saves the first payroll id into `ukg_payroll_id`.
6. **Get Pay Statements for Payroll** — individual paycheck records for that
   payroll run.

## 5. Re-authenticate when a request starts 401'ing

- PrismHR's `sessionId` and UKG/isolved's `access_token` are short-lived.
  Re-run the matching **Sign In** request — it overwrites the stale token in
  place, no need to touch anything else.
- isolved may also return a refresh token (`isolved_refresh_token`); the
  demo-provider-signin service itself doesn't expose a refresh call, so if a
  token expires, just sign in again rather than trying to use the refresh
  token against isolved directly.

## 6. Run everything at once with Collection Runner

Once sign-in has populated the environment, you don't have to click through
all 29 requests by hand to check "are all three providers working":

1. Hover the collection name → **Run** (or **Runner** in the bottom bar).
2. Select the whole collection (or just one provider folder), keep the
   **Tada AI Normalization - Demo** environment selected, and make sure
   requests run in collection order (top to bottom) since later requests
   depend on ids earlier ones save.
3. Click **Run**. The results view lists every test from every request with
   a pass/fail icon — a 29-request collection with ~3-4 tests each gives you
   roughly 100 individual checks on one screen. A fully green run means all
   three providers are reachable, authenticating, and returning the
   documented shape of real data.
4. On a run with the Sign In folder included, do it in two passes: run just
   `0 - Sign In` first, then run the three provider folders — Collection
   Runner executes top-to-bottom within one run, so it does work in a single
   pass too, but splitting it makes a sign-in failure obvious before you
   waste time reading 26 downstream failures that all trace back to it.

If you'd rather run this from a terminal/CI (e.g. to re-check after editing
the collection), install the Postman CLI companion, Newman, and run:

```sh
npm install -g newman
newman run "postman/Tada AI Normalization - Provider APIs.postman_collection.json" \
  -e "postman/Tada AI Normalization - Demo.postman_environment.json" \
  --env-var demo_signin_api_key=$DEMO_SIGNIN_API_KEY
```

Newman prints a pass/fail summary per request and exits non-zero if any test
failed, which is what you'd wire into a script if you wanted "is everything
up" as a one-command check.

## Troubleshooting

- **A Sign In request 200s but a variable stays empty** — open the response
  body and compare its shape to what the Tests script reads (e.g. it expects
  `context.companies[0].client_id`). The demo service's response shape is
  described in the main README under "Access live demo data"; if the live
  response differs, fix the Tests script in that one request rather than
  editing values by hand each run.
- **A data request 404s** — the demo tenant may not have seeded data for that
  sub-resource (e.g. no direct deposits on file for the first employee
  returned). Try the next employee/company id from the list response.
- **A PrismHR request returns 200 but fails the "no PrismHR business error"
  test** — read the test's failure message, it includes the real
  `errorCode`/`errorMessage` from the body (e.g. an unknown `employeeId` or
  `clientId`). Fix the id in the environment rather than assuming the
  endpoint itself is broken.
- **A "result is an array" test fails on a discovery endpoint** (client/company
  list, employee list, isolved pay-group discovery, UKG payroll list) — this
  means the demo tenant genuinely has zero records there, which stalls every
  downstream request in that folder. This is the one case where an empty
  result is itself the bug report: there's nothing further to debug on your
  side, flag it as a demo-data gap.
- **UKG direct-deposits request fails without the deprecation header** — that
  endpoint requires `X-End-of-Support-Timeline`; it's already set in the
  request, but if UKG changes the expected date value, update it there.
- **Don't treat response samples as exhaustive** — per the main README, the
  documented sample payloads (and the ones you'll see here) are illustrative,
  not a full contract. Use live responses to validate your own canonical
  schema, not as the schema itself.
