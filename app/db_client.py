"""Step 4: write a canonical Employee record (app/canonicalize_client.py's
output) into one shared SQLite database, so employees pulled from any of
the three providers live under the same roof, in the same shape. Kept
Streamlit-free, same reasoning as the other app/*_client.py modules.

Schema mirrors src/normalization/canonical/models.py directly: one table
per canonical entity (employees, pay_rates, direct_deposits,
deduction_setups), rather than one big JSON blob column, so the data is
actually queryable - "show me every direct deposit account type across
all three providers" is a real SQL query against this schema, not a
Python loop over blobs.

Employee.id (the provider-prefixed canonical_id, e.g.
"prismhr:employee:A00576") is the employees table's primary key. Because
that id is already globally unique across all three providers by
construction, saving the same employee twice - even from re-running a
live pull - updates the existing row (INSERT OR REPLACE) instead of
creating a duplicate. DirectDeposit.id / DeductionSetup.id are likewise
already globally unique (see each adapter's module docstring), so the
same approach works for the child tables: delete this employee's old
child rows, then insert the current set, which also naturally drops any
deposit/deduction that disappeared from a later pull.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

DB_PATH = Path(__file__).resolve().parents[1] / "canonical.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id TEXT PRIMARY KEY,
    source_provider TEXT NOT NULL,
    source_raw_id TEXT NOT NULL,
    company_id TEXT,
    employee_number TEXT,
    first_name TEXT,
    last_name TEXT,
    middle_name TEXT,
    preferred_name TEXT,
    date_of_birth TEXT,
    gender TEXT,
    marital_status TEXT,
    ssn_last4 TEXT,
    contact_email TEXT,
    contact_mobile_phone TEXT,
    contact_home_phone TEXT,
    contact_work_phone TEXT,
    address_line1 TEXT,
    address_line2 TEXT,
    address_city TEXT,
    address_state TEXT,
    address_postal_code TEXT,
    address_country TEXT,
    employment_status TEXT NOT NULL,
    worker_type TEXT,
    job_title TEXT,
    department TEXT,
    manager_employee_id TEXT,
    hire_date TEXT,
    rehire_date TEXT,
    termination_date TEXT,
    termination_reason TEXT,
    pay_frequency TEXT,
    saved_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pay_rates (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    basis TEXT NOT NULL,
    amount TEXT NOT NULL,
    effective_date TEXT
);

CREATE TABLE IF NOT EXISTS direct_deposits (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    source_provider TEXT NOT NULL,
    source_raw_id TEXT NOT NULL,
    account_type TEXT NOT NULL,
    bank_name TEXT,
    routing_number_last4 TEXT,
    account_number_last4 TEXT,
    allocation_method TEXT NOT NULL,
    amount TEXT,
    percent TEXT,
    priority INTEGER,
    status TEXT NOT NULL,
    effective_from TEXT,
    effective_to TEXT
);

CREATE TABLE IF NOT EXISTS deduction_setups (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    source_provider TEXT NOT NULL,
    source_raw_id TEXT NOT NULL,
    code TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    calc_method TEXT NOT NULL,
    amount TEXT,
    percent TEXT,
    start_date TEXT,
    stop_date TEXT,
    is_active INTEGER
);

CREATE INDEX IF NOT EXISTS idx_pay_rates_employee ON pay_rates(employee_id);
CREATE INDEX IF NOT EXISTS idx_direct_deposits_employee ON direct_deposits(employee_id);
CREATE INDEX IF NOT EXISTS idx_deduction_setups_employee ON deduction_setups(employee_id);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn


def save_employee(employee: Dict[str, Any]) -> None:
    """Upserts one canonical Employee dict (as returned by
    canonicalize_client.canonicalize_employee) - the employee row plus its
    pay_rates/direct_deposits/deduction_setups child rows."""
    source = employee.get("source") or {}
    contact = employee.get("contact") or {}
    address = employee.get("address") or {}
    employee_id = employee["id"]

    conn = _connect()
    try:
        with conn:
            conn.execute("DELETE FROM pay_rates WHERE employee_id = ?", (employee_id,))
            conn.execute("DELETE FROM direct_deposits WHERE employee_id = ?", (employee_id,))
            conn.execute("DELETE FROM deduction_setups WHERE employee_id = ?", (employee_id,))

            conn.execute(
                """
                INSERT OR REPLACE INTO employees (
                    id, source_provider, source_raw_id, company_id, employee_number,
                    first_name, last_name, middle_name, preferred_name, date_of_birth,
                    gender, marital_status, ssn_last4,
                    contact_email, contact_mobile_phone, contact_home_phone, contact_work_phone,
                    address_line1, address_line2, address_city, address_state,
                    address_postal_code, address_country,
                    employment_status, worker_type,
                    job_title, department, manager_employee_id,
                    hire_date, rehire_date, termination_date, termination_reason,
                    pay_frequency, saved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    employee_id, source.get("provider"), source.get("raw_id"),
                    employee.get("company_id"), employee.get("employee_number"),
                    employee.get("first_name"), employee.get("last_name"),
                    employee.get("middle_name"), employee.get("preferred_name"),
                    employee.get("date_of_birth"),
                    employee.get("gender"),
                    employee.get("marital_status"),
                    employee.get("ssn_last4"),
                    contact.get("email"), contact.get("mobile_phone"),
                    contact.get("home_phone"), contact.get("work_phone"),
                    address.get("line1"), address.get("line2"), address.get("city"),
                    address.get("state"), address.get("postal_code"), address.get("country"),
                    employee.get("employment_status"),
                    employee.get("worker_type"),
                    employee.get("job_title"), employee.get("department"),
                    employee.get("manager_employee_id"),
                    employee.get("hire_date"), employee.get("rehire_date"),
                    employee.get("termination_date"), employee.get("termination_reason"),
                    employee.get("pay_frequency"),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            for rate in employee.get("pay_rates") or []:
                conn.execute(
                    "INSERT INTO pay_rates (employee_id, basis, amount, effective_date) "
                    "VALUES (?, ?, ?, ?)",
                    (employee_id, rate.get("basis"), rate.get("amount"), rate.get("effective_date")),
                )

            for dd in employee.get("direct_deposits") or []:
                dd_source = dd.get("source") or {}
                conn.execute(
                    """
                    INSERT INTO direct_deposits (
                        id, employee_id, source_provider, source_raw_id,
                        account_type, bank_name,
                        routing_number_last4, account_number_last4,
                        allocation_method, amount, percent,
                        priority, status, effective_from, effective_to
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dd["id"], employee_id, dd_source.get("provider"), dd_source.get("raw_id"),
                        dd.get("account_type"), dd.get("bank_name"),
                        dd.get("routing_number_last4"), dd.get("account_number_last4"),
                        dd.get("allocation_method"),
                        dd.get("amount"), dd.get("percent"),
                        dd.get("priority"), dd.get("status"),
                        dd.get("effective_from"), dd.get("effective_to"),
                    ),
                )

            for ded in employee.get("deductions") or []:
                ded_source = ded.get("source") or {}
                conn.execute(
                    """
                    INSERT INTO deduction_setups (
                        id, employee_id, source_provider, source_raw_id,
                        code, description, category,
                        calc_method, amount, percent,
                        start_date, stop_date, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ded["id"], employee_id, ded_source.get("provider"), ded_source.get("raw_id"),
                        ded.get("code"), ded.get("description"),
                        ded.get("category"),
                        ded.get("calc_method"),
                        ded.get("amount"), ded.get("percent"),
                        ded.get("start_date"), ded.get("stop_date"),
                        ded.get("is_active"),
                    ),
                )
    finally:
        conn.close()


def provider_counts() -> Dict[str, int]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT source_provider, COUNT(*) AS n FROM employees GROUP BY source_provider"
        ).fetchall()
        return {row["source_provider"]: row["n"] for row in rows}
    finally:
        conn.close()


def export_sql() -> str:
    """A complete, runnable SQL script - CREATE TABLE plus INSERT
    statements for everything currently saved - via sqlite3's own
    iterdump(). Viewing the database happens outside this app: paste/run
    this script in any browser-based SQLite tool (e.g. sqliteonline.com,
    sqlite.org/fiddle) to rebuild and browse the exact same database
    there."""
    conn = _connect()
    try:
        return "\n".join(conn.iterdump())
    finally:
        conn.close()
