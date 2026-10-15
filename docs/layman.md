# How we designed the canonical schema (layman's terms)

Think of it like this: we had three different foreign HR departments
(PrismHR, isolved, UKG Ready) each describing the same kind of thing — a
company, an employee, a paycheck — but each one speaking its own dialect.
One says an employee's status is `"A"`, another says `"Active"`, the third
also says `"Active"` but means something slightly different by it. Before we
could translate anything, we needed to design **one common form** that all
three dialects get poured into — that's the canonical schema.

Here's how we actually got started on designing that form:

## 1. First, we checked what "buckets" we were even allowed to have

The project's starter code had already decided there'd be exactly three
buckets: Company, Employee, Payroll — not four, even though the README
talks about four kinds of data (employee info, direct deposits, deductions,
payroll). So before designing anything, we had to figure out: where do
"direct deposits" and "deductions" go if there's no bucket for them?
Answer: they live *inside* the Employee bucket, like a sub-folder, not as
their own filing cabinet. That was decision #1, made before writing a
single field.

## 2. Then we asked: what does every single company/employee/paycheck need, no matter which system it came from?

A company always has a name and a status. An employee always has a name, a
hire date, maybe a termination date. A paycheck always has a gross amount
and a net amount. We wrote down the *universal* version of these — the
stuff that's true regardless of dialect.

## 3. For anything that's a "code" rather than free text, we had a problem

Each system invents its own short codes, and nobody hands you a dictionary.
PrismHR says `"A"` for active. isolved says `"Active"`. We can't just pick
one and throw the others away — so we invented our own small set of
standard labels (like `ACTIVE`, `TERMINATED`, `ON_LEAVE`) that every
system's version gets translated into. But — and this mattered a lot — **we
always kept the original code sitting right next to our translation.** Why?
Because the project's own reference files told us flat out: "we haven't
discovered every code yet, and some are unverified." If we only kept our
translation and threw away the original, we'd be guessing with no way to
check or fix it later. Keeping both means: best guess up front, nothing
ever lost.

## 4. We set a few "house rules" that apply to every form, not just one field

- Money is never allowed to get rounding errors — three different payroll
  systems round differently internally, so we picked a number format that
  keeps exact cents.
- Every record always carries a tag saying "I came from PrismHR" (or
  isolved, or UKG) plus its original ID — so you can always trace a
  canonical record back to exactly where it came from.
- Sensitive stuff — bank account numbers, SSNs — gets partially blanked out
  by design, even in our own internal form, because this is meant to be
  something that could end up in a shared project.
- IDs are built so an employee automatically "points at" its company
  without needing a separate lookup table — a bit like giving everyone a
  name tag that already has their department written on it.

## 5. We picked a tool that acts like a strict intake form, not a suggestion box

We used a library (Pydantic) that actively rejects data that doesn't fit
the form — so if a future mapping script accidentally tries to stuff in a
field we never defined, it errors out loudly immediately, instead of
quietly accepting junk that causes a mystery bug three steps later.

## 6. Only after all of that did we actually draw the forms

Enums (the standard code lists) first, then the forms themselves — Company,
Employee (with the direct-deposit and deduction sub-forms tucked inside),
and Payroll/Paycheck (with earnings/taxes/deductions as its own sub-forms).

## 7. We proved the form actually works before calling it done

We filled out a fake sample Company/Employee/Paycheck by hand and checked
that it could be "printed" into a plain JSON file correctly — because
that's literally what the rest of the project needs at the end.

## 8. Last, we wrote down the *why* behind every rule

In `docs/CANONICAL_SCHEMA.md` — so the reasoning isn't locked in anyone's
head, it's on paper.

---

So in short: we didn't start by writing code — we started by arguing out
loud (on paper) about what shape the data *should* take, grounded in real
codes we'd already seen from all three systems, before ever touching a
class definition.
