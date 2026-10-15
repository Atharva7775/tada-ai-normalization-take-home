"""Deterministic synthetic fixture generation for PrismHR, isolved, and UKG
Ready - no credentials, no network calls, no live demo data.

**What this module does and does not do** (see docs/CANONICAL_SCHEMA.md and
the project README's "deterministic... without credentials" requirement):
`generate()` fabricates RAW, provider-native-shaped fake data (the same
shapes this project reverse-engineered from the real OpenAPI specs and a
live demo crawl - see each adapter's module docstring in
src/normalization/adapters/) and writes it to tests/fixtures/<provider>/.
It never imports or calls an adapter. Turning that raw fixture data into
canonical output is a separate concern, done later by whatever consumes
these files (a pytest test that calls ADAPTERS[provider].normalize(...)
directly, or the project's own CLI). Keeping these two jobs apart means a
fixture never silently goes stale against a changed adapter - there is no
pre-baked "expected output" file to forget to regenerate.

Each provider's employee fixtures deliberately include six scenarios
chosen to exercise specific gaps or risks already discovered during this
project's real-data verification (see docs/CANONICAL_SCHEMA.md):
  1. active_simple           - the happy path
  2. terminated               - termination date/reason populated
  3. on_leave_or_undocumented - PrismHR "L" (on leave), never observed in
                                 this project's live sample; isolved/UKG use
                                 an undocumented status instead, since they
                                 have no on-leave concept observed live
  4. no_deposits_no_deductions - exercises the empty-list defaults
  5. multiple_deposits        - exercises every AllocationMethod branch
  6. unknown_status_code      - a deliberately made-up status code, to
                                 prove the OTHER/UNKNOWN fallback never raises
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "tests" / "fixtures"
DEFAULT_SEED = 20251014

PROVIDERS = ("prismhr", "isolved", "ukg-ready")
VARIANTS = (
    "active_simple",
    "terminated",
    "on_leave_or_undocumented",
    "no_deposits_no_deductions",
    "multiple_deposits",
    "unknown_status_code",
)

FIRST_NAMES = ["Jordan", "Priya", "Marcus", "Elena", "Kofi", "Hannah"]
LAST_NAMES = ["Alvarez", "Nakamura", "Johnson", "Okafor", "Petrov", "Lindqvist"]
CITIES = [
    ("Austin", "TX", "78701"),
    ("Tampa", "FL", "33602"),
    ("Columbus", "OH", "43215"),
    ("Spokane", "WA", "99201"),
    ("Charlotte", "NC", "28202"),
    ("Boise", "ID", "83702"),
]
STREETS = ["Maple St", "Cedar Ave", "River Rd", "Birch Ln", "Harbor Dr", "Union Way"]


def _person(rng: random.Random, idx: int):
    first = FIRST_NAMES[idx % len(FIRST_NAMES)]
    last = LAST_NAMES[(idx * 3) % len(LAST_NAMES)]
    city, state, zip_code = CITIES[idx % len(CITIES)]
    street_num = 100 + rng.randint(0, 899)
    street = STREETS[idx % len(STREETS)]
    dob = f"19{60 + idx % 35}-0{1 + idx % 9}-{10 + idx % 18}"
    return {
        "first": first, "last": last, "city": city, "state": state, "zip": zip_code,
        "address": f"{street_num} {street}", "dob": dob,
    }


def _ssn_fake(idx: int) -> str:
    return f"{100 + idx:03d}-{20 + idx:02d}-{1000 + idx:04d}"


def _write(output_dir: Path, provider: str, filename: str, data: Any) -> str:
    provider_dir = output_dir / provider
    provider_dir.mkdir(parents=True, exist_ok=True)
    path = provider_dir / filename
    path.write_text(json.dumps(data, indent=2) + "\n")
    return str(path.relative_to(ROOT))


# ---------------------------------------------------------------------------
# PrismHR - raw shapes per src/normalization/adapters/prismhr.py's docstring
# ---------------------------------------------------------------------------

def _prismhr_company_input(rng: random.Random) -> Dict[str, Any]:
    clients = []
    for i, (status, client_id) in enumerate((("A", "900"), ("A", "901"))):
        p = _person(rng, i)
        clients.append({
            "clientId": client_id,
            "clientName": f"{p['last']} {('Logistics' if i else 'Manufacturing')}",
            "legalName": f"{p['last']} {('Logistics' if i else 'Manufacturing')} LLC",
            "status": status,
            "serviceType": None,
        })
    return {"clientListResult": {"clientList": clients}}


def _prismhr_ach_voucher(rng: random.Random, method: str, status: str, amount: Optional[float], limit: Optional[float]) -> Dict[str, Any]:
    return {
        "transitNum": f"0{rng.randint(10000000, 99999999)}",
        "accountNum": f"*{rng.randint(1000, 9999)}",
        "accountType": rng.choice(["C", "S"]),
        "method": method,
        "amount": amount,
        "limit": limit,
        "status": status,
        "bankName": rng.choice(["First Union Bank", "Lakeside Credit Union", "Harbor National"]),
        "voucherTypeOverride": "",
    }


def _prismhr_employee_bundle(rng: random.Random, idx: int, variant: str, client_id: str) -> Dict[str, Any]:
    p = _person(rng, idx)
    emp_id = f"E9{idx:04d}"
    status_class = {"active_simple": "A", "terminated": "T", "on_leave_or_undocumented": "L",
                     "no_deposits_no_deductions": "A", "multiple_deposits": "A",
                     "unknown_status_code": "Z"}[variant]  # "Z" is not a real PrismHR code - deliberate

    client_block = {
        "employeeStatus": status_class, "statusClass": status_class,
        "statusDate": "2024-01-01", "employeeType": "FT", "typeClass": "F", "typeDate": "2024-01-01",
        "jobCode": rng.choice(["OFFICE", "WAREHOUSE", "SALES"]),
        "jobStartDate": "2022-06-01", "firstHireDate": "2022-06-01", "lastHireDate": "2022-06-01",
        "flsaExempt": False, "termReasonCode": "", "termExplanation": "",
    }
    if variant == "terminated":
        client_block.update(termReasonCode="VOL", termExplanation="Resigned", termDate="2024-11-15")

    comp = {
        "ssn": "***-**-****", "payGroup": "WFRI", "payPeriod": "B", "payMethod": "H" if idx % 2 else "S",
        "standardHours": "40.00",
        "hourlyPayRate": f"{18 + idx}.5000", "annualPay": f"{48000 + idx * 1000}.00",
        "effectiveDate": "2024-01-01",
    }

    if variant == "no_deposits_no_deductions":
        direct_deposit = {"achStatus": "I", "voucherType": "RVS", "suppressAccountPrint": False, "achVoucher": [], "directDepositChecksum": "0"}
        ach_settings: List[Dict[str, Any]] = []
        deductions: List[Dict[str, Any]] = []
        voluntary: List[Dict[str, Any]] = []
        scheduled: List[Dict[str, Any]] = []
    elif variant == "multiple_deposits":
        vouchers = [
            _prismhr_ach_voucher(rng, "F", "D", 250.00, None),
            _prismhr_ach_voucher(rng, "P", "D", None, 15.0),
            _prismhr_ach_voucher(rng, "B", "D", None, None),
        ]
        direct_deposit = {"achStatus": "A", "voucherType": "RVS", "suppressAccountPrint": False, "achVoucher": vouchers, "directDepositChecksum": "123"}
        ach_settings = []
        deductions = [{"deductionCode": "401k", "deductionType": "K", "deductionMethod": "K", "description": "401k",
                        "usePercent": True, "amount": 6.0, "period": "12345", "loanOrGarnishId": "", "benefitPlanId": "",
                        "startDate": "2023-01-01", "stopDate": ""}]
        voluntary = []
        scheduled = []
    else:
        direct_deposit = {"achStatus": "A", "voucherType": "RVS", "suppressAccountPrint": False,
                           "achVoucher": [_prismhr_ach_voucher(rng, "B", "D", None, None)], "directDepositChecksum": "456"}
        ach_settings = []
        deductions = [{"deductionCode": "401k", "deductionType": "K", "deductionMethod": "K", "description": "401k",
                        "usePercent": True, "amount": 4.0, "period": "12345", "loanOrGarnishId": "", "benefitPlanId": "",
                        "startDate": "2023-01-01", "stopDate": ""}]
        voluntary = [{"deductionCode": "MED", "deductionType": "C", "deductionMethod": "F", "description": "Medical",
                      "usePercent": False, "amount": 35.0, "period": "1234", "loanOrGarnishId": "", "benefitPlanId": "BCBS"}]
        scheduled = []

    bundle = {
        "profile": {
            "employee": [{
                "id": emp_id, "lastName": p["last"], "firstName": p["first"], "middleInitial": "",
                "preferredName": "",
                "person": {"birthDate": p["dob"], "gender": "F" if idx % 2 else "M",
                           "maritalStatus": "S" if idx % 2 else "M"},
                "contactInformation": {
                    "addressLine1": p["address"], "addressLine2": "", "city": p["city"], "state": p["state"],
                    "zipcode": p["zip"], "zipSuffix": "", "county": "", "schoolDistrict": "",
                    "homePhone": "", "mobilePhone": "", "emailAddress": f"{p['first'].lower()}.{p['last'].lower()}@example.com",
                },
                "client": client_block,
                "compensation": comp,
                "directDeposit": direct_deposit,
            }],
            "infoMessage": None, "updateMessage": None, "errorCode": "0", "errorMessage": "", "extension": None,
        },
        "ach_deductions": {"achDeductionSettings": ach_settings, "achChecksum": "0", "errorCode": "0", "errorMessage": "", "extension": None},
        "deductions": {"employeeDeductions": {"deduction": deductions}, "errorCode": "0", "errorMessage": "", "extension": None},
        "voluntary_deductions": {"voluntaryDeduction": {"deduction": voluntary}, "checksum": "0", "errorCode": "0", "errorMessage": "", "extension": None},
        "scheduled_deductions": {"sessionId": "", "clientId": client_id, "employeeId": emp_id, "checksum": "0",
                                  "scheduledDeduction": scheduled, "errorCode": "0", "errorMessage": "", "extension": None},
        "client_id": client_id,
    }
    return bundle, emp_id


def _prismhr_voucher(rng: random.Random, voucher_id: str, employee_id: str, status: str, pay_date: str) -> Dict[str, Any]:
    gross = round(1500 + rng.randint(0, 500) + rng.random(), 2)
    fit = round(gross * 0.12, 2)
    medi = round(gross * 0.0145, 2)
    ss = round(gross * 0.062, 2)
    net = round(gross - fit - medi - ss, 2)
    return {
        "voucherId": voucher_id, "status": status, "type": "R", "voidDate": "", "checkNumber": str(rng.randint(10000, 99999)),
        "payDate": pay_date, "employeeId": employee_id, "payPeriod": "B",
        "payPeriodStart": pay_date, "payPeriodEnd": pay_date, "payGroup": "WFRI",
        "dateProcessed": pay_date, "totalEarnings": gross, "netPay": net,
        "employeeTax": [
            {"empTaxDeductCode": "00-10", "empTaxDeductCodeDesc": "Federal Income Tax", "empTaxableAmount": gross, "empTaxAmount": fit, "empOverLimitAmount": 0.0},
            {"empTaxDeductCode": "00-11", "empTaxDeductCodeDesc": "Medicare - Employee", "empTaxableAmount": gross, "empTaxAmount": medi, "empOverLimitAmount": 0.0},
            {"empTaxDeductCode": "00-12", "empTaxDeductCodeDesc": "Soc Security - Employee", "empTaxableAmount": gross, "empTaxAmount": ss, "empOverLimitAmount": 0.0},
        ],
        "companyTax": [
            {"comTaxEntity": "P", "comTaxDeductCode": "00-15", "comTaxDeductCodeDesc": "Medicare - Employer", "comExemptAmount": 0.0,
             "comShelteredAmount": 0.0, "comTaxableAmount": gross, "comTaxType": "9F", "comTaxAmount": medi, "comOvrLimit": 0.0,
             "comTaxRate": 0.0145, "comClientSutaRpt": ""},
        ],
        "earning": [
            {"payCode": "REG", "payClassDescription": "Earnings", "chargeDate": pay_date, "hoursUnits": 80.0, "hoursWorked": 80.0,
             "unitRate": round(gross / 80.0, 4), "payAmount": gross, "division": "", "jobCode": "OFFICE", "shift": "",
             "department": "100", "location": "1", "glCode": "", "workComp": "", "projWork": "", "projPhase": ""},
        ],
        "otherEarningsDetail": [], "fsaMatch": [], "batchId": f"O{voucher_id}",
        "deduction": [{"deductCode": "401k", "deductDescription": "401k", "deductAmount": round(gross * 0.04, 2), "deductType": "K", "deductUnionId": "", "planId": ""}],
        "otherDeduction": [], "benefit": [],
    }


def _prismhr_payroll_input(rng: random.Random, employee_ids: List[str]) -> Dict[str, Any]:
    vouchers = []
    counter = 1
    for emp_id in employee_ids:
        for month in ("2024-09", "2024-10"):
            vouchers.append(_prismhr_voucher(rng, f"{counter:06d}", emp_id, "PRNT", f"{month}-15"))
            counter += 1
    # one deliberately unrecognized voucher status, to exercise the OTHER fallback
    vouchers.append(_prismhr_voucher(rng, f"{counter:06d}", employee_ids[0], "HELD", "2024-11-15"))
    return {"total": None, "startpage": None, "count": None, "errorCode": "0", "errorMessage": "", "extension": None,
            "payrollVoucher": vouchers}


# ---------------------------------------------------------------------------
# isolved - raw shapes per src/normalization/adapters/isolved.py's docstring
# ---------------------------------------------------------------------------

def _isolved_company_input(rng: random.Random) -> List[Dict[str, Any]]:
    legals = []
    for i, legal_id in enumerate((9000, 9001)):
        p = _person(rng, i)
        legals.append({
            "id": legal_id,
            "legalName": f"{p['last']} {('Freight' if i else 'Builders')} Inc",
            "dbaName": f"{p['last']} {('Freight' if i else 'Builders')}",
            "federalEIN": f"{500000000 + legal_id}",
            "status": "Active",
            "legalAddress": {"address1": p["address"], "city": p["city"], "state": p["state"], "zipCode": p["zip"]},
        })
    return legals


def _isolved_direct_deposit(rng: random.Random, dep_id: int, account_type: str, status: str,
                             amount: Optional[float], percent: Optional[float], seq: int) -> Dict[str, Any]:
    return {
        "id": dep_id, "accountNumber": f"{rng.randint(100000, 999999)}", "accountType": account_type,
        "amount": amount, "bankName": rng.choice(["Sunrise Bank", "Pioneer Trust", "Lakeshore Federal"]),
        "description": None, "frequency": "Every Pay", "percent": percent,
        "routingNumber": f"0{rng.randint(10000000, 99999999)}", "sequenceNumber": seq, "status": status,
    }


def _isolved_pay_item(rng: random.Random, item_id: int, employee_id: int, code: str, name: str, item_type: str) -> Dict[str, Any]:
    return {
        "id": item_id, "auditId": None, "calcParams": [{"paramType": "Rate", "paramValue": 0.0}],
        "employeeId": employee_id, "employeeNumber": str(employee_id), "firstName": "", "lastName": "",
        "payItemCode": code, "payItemId": item_id, "payItemName": name, "payItemType": item_type,
        "referenceNumber": None, "scheduleOverride": None, "startDate": "2023-01-01T00:00:00", "stopDate": None,
    }


def _isolved_employee_bundle(rng: random.Random, idx: int, variant: str, client_id: str, legal_id: str) -> Dict[str, Any]:
    p = _person(rng, idx)
    employee_id = 900100 + idx
    status = {"active_simple": "Active", "terminated": "Terminated", "on_leave_or_undocumented": "Inactive",
              "no_deposits_no_deductions": "Active", "multiple_deposits": "Active",
              "unknown_status_code": "Pending Review"}[variant]  # "Pending Review" is not a real observed isolved value - deliberate

    profile = {
        "id": employee_id, "employeeNumber": str(1000 + idx),
        "nameAddress": {"firstName": p["first"], "lastName": p["last"], "middleName": "", "preferredName": None,
                         "address1": p["address"], "city": p["city"], "state": p["state"], "zipCode": p["zip"]},
        "personal": {"mobilePhone": None, "homePhone": None, "officePhone": None, "personalEmailAddress": f"{p['first'].lower()}@example.com"},
        "birthDate": f"{p['dob']}T00:00:00", "gender": "Female" if idx % 2 else "Male",
        "maritalStatus": "Single" if idx % 2 else "Married", "ssn": _ssn_fake(idx),
        "emailAddress": f"{p['first'].lower()}.{p['last'].lower()}@example.com",
        "employmentStatus": status, "employmentCategoryCode": "FT",
        "jobTitle": rng.choice(["Dispatcher", "Accountant", "Technician"]),
        "hireDate": "2021-03-01T00:00:00", "rehireDate": None, "terminationDate": None, "terminationReason": None,
        "payType": "Hourly" if idx % 2 else "Salary", "hourlyRate": 22.5 + idx, "annualSalary": 55000.0 + idx * 1000,
        "perPaySalary": None, "salaryEffectiveDate": "2024-01-01T00:00:00", "payFrequency": 24,
    }
    if variant == "terminated":
        profile.update(terminationDate="2024-10-01T00:00:00", terminationReason="Resignation")

    if variant == "no_deposits_no_deductions":
        direct_deposits: List[Dict[str, Any]] = []
    elif variant == "multiple_deposits":
        direct_deposits = [
            _isolved_direct_deposit(rng, 700000 + idx, "Checking", "Active", 300.0, None, 0),
            _isolved_direct_deposit(rng, 700001 + idx, "Savings", "Active", None, 10.0, 1),
        ]
    else:
        direct_deposits = [_isolved_direct_deposit(rng, 700002 + idx, "Checking", "Active", None, None, 0)]

    pay_items = [] if variant == "no_deposits_no_deductions" else [
        _isolved_pay_item(rng, 800000 + idx, employee_id, "401K", "401k", "Deduction"),
        _isolved_pay_item(rng, 800001 + idx, employee_id, "DEN", "Dental Pre-tax", "Deduction"),
        _isolved_pay_item(rng, 800002 + idx, employee_id, "13", "Bonus", "Earning"),
    ]

    return {
        "profile": profile,
        "direct_deposits": direct_deposits,
        "pay_items": pay_items,
        "corestream_deductions": None,
        "client_id": client_id,
        "legal_id": legal_id,
    }


def _isolved_check(rng: random.Random, check_id: int, employee_id: int, check_type: str, check_date: str) -> Dict[str, Any]:
    gross = round(1800 + rng.randint(0, 400) + rng.random(), 2)
    net = round(gross * 0.76, 2)
    return {
        "id": check_id, "accruals": None, "benefits": None, "checkAmount": net,
        "checkDate": check_date, "checkNumber": rng.randint(5000, 9000), "checkSequence": 0,
        "checkTypeDescription": check_type,
        "deductions": [{"id": check_id * 10, "checkDollars": round(gross * 0.03, 2), "currentDollars": round(gross * 0.03, 2),
                         "itemCode": "401K", "itemDescription": "401k", "ytdDollars": round(gross * 0.03 * 6, 2)}],
        "directDepositAmount": net, "directDeposits": None,
        "earnings": [{"id": check_id * 10 + 1, "itemCode": "01", "itemDescription": "Regular",
                      "checkHours": 80.0, "checkDollars": gross, "ytdDollars": round(gross * 6, 2)}],
        "employeeId": employee_id, "grossPay": gross, "grossWages": gross, "netPay": net,
        "periodBeginDate": check_date, "periodEndDate": check_date, "taxes": None,
    }


def _isolved_payroll_input(rng: random.Random, employee_ids: List[int]) -> Dict[str, Any]:
    checks = []
    check_id = 1
    for emp_id in employee_ids:
        for check_date in ("2024-09-30", "2024-10-15"):
            checks.append(_isolved_check(rng, check_id, emp_id, "Regular", check_date))
            check_id += 1
    # one deliberately unrecognized check type, to exercise the OTHER fallback
    checks.append(_isolved_check(rng, check_id, employee_ids[0], "Off-Cycle Correction", "2024-11-01"))
    return {"nextPageUrl": None, "previousPageUrl": None, "results": checks,
            "totalItems": len(checks), "totalPages": 1.0}


# ---------------------------------------------------------------------------
# UKG Ready - raw shapes per src/normalization/adapters/ukg_ready.py's docstring
# ---------------------------------------------------------------------------

def _ukg_company_input(rng: random.Random) -> List[Dict[str, Any]]:
    # UKG has no company-detail endpoint at all (see adapter docstring) -
    # the only real input shape is the minimal id-only dict.
    return [{"company_id": "990001"}, {"company_id": "990002"}]


def _ukg_direct_deposit(rng: random.Random, dep_id: int, account_type: str, calc_type: str,
                         amount: Optional[float], percentage: Optional[float], active: bool, seq: int) -> Dict[str, Any]:
    dep: Dict[str, Any] = {
        "id": dep_id, "sequence": seq, "type": "DIRECT_DEPOSIT", "active_from": "2023-01-01", "active_to": "2099-12-31",
        "active": active, "calc_method": {"type": calc_type}, "account_type": account_type,
        "account_number": f"{rng.randint(100000, 999999)}", "routing_type": "ABA",
        "routing_number": f"0{rng.randint(10000000, 99999999)}",
    }
    if amount is not None:
        dep["amount"] = amount
    if percentage is not None:
        dep["percentage"] = percentage
    return dep


def _ukg_employee_bundle(rng: random.Random, idx: int, variant: str, company_id: str) -> Dict[str, Any]:
    p = _person(rng, idx)
    employee_id = 990100 + idx
    status = {"active_simple": "Active", "terminated": "Terminated", "on_leave_or_undocumented": "Leave of Absence",
              "no_deposits_no_deductions": "Active", "multiple_deposits": "Active",
              "unknown_status_code": "Furloughed"}[variant]  # "Leave of Absence"/"Furloughed" not confirmed live - deliberate

    profile = {
        "id": employee_id, "employee_id": str(100 + idx), "first_name": p["first"], "last_name": p["last"],
        "middle_name": None, "nickname": None, "primary_email": f"{p['first'].lower()}@example.com",
        "phones": {"cell_phone": None, "home_phone": None, "work_phone": None},
        "address": {"address_line_1": p["address"], "address_line_2": None, "city": p["city"],
                    "state": p["state"], "state_code": p["state"], "zip": p["zip"], "country": "USA"},
        "dates": {"birthday": p["dob"], "hired": "2020-05-01"},
        "social_security": _ssn_fake(idx), "status": status,
        "managers": [{"index": 1, "empl_ref": {"account_id": 990100}}] if idx else [],
    }
    if variant == "terminated":
        profile["dates"]["terminated"] = "2024-09-30"

    if variant == "no_deposits_no_deductions":
        deposits: List[Dict[str, Any]] = []
    elif variant == "multiple_deposits":
        deposits = [
            _ukg_direct_deposit(rng, 600000 + idx, "CHECKING", "FLAT_AMOUNT", 400.0, None, True, 1),
            _ukg_direct_deposit(rng, 600001 + idx, "SAVINGS", "NET_PAY", None, 10.0, True, 2),
            _ukg_direct_deposit(rng, 600002 + idx, "CHECKING", "FULL", None, None, True, 3),
        ]
    else:
        deposits = [_ukg_direct_deposit(rng, 600003 + idx, "CHECKING", "FULL", None, None, True, 1)]

    return {
        "profile": profile,
        "direct_deposits": {"deposits": deposits},
        "deductions": None,  # confirmed 404 live for every real employee - see adapter docstring
        "company_id": company_id,
    }


def _ukg_pay_statement(rng: random.Random, stmt_id: int, employee_account_id: int, status: str, pay_date: str) -> Dict[str, Any]:
    return {
        "id": stmt_id, "employee": {"account_id": employee_account_id}, "status": status,
        "pay_date": pay_date, "type": {"id": 1, "display_name": "Regular"},
        "pay_period_start": pay_date, "pay_period_end": pay_date,
    }


def _ukg_payroll_input(rng: random.Random, employee_account_ids: List[int]) -> Dict[str, Any]:
    statements = []
    stmt_id = 1
    for emp_id in employee_account_ids:
        for pay_date in ("2024-09-27", "2024-10-11"):
            statements.append(_ukg_pay_statement(rng, stmt_id, emp_id, "OPEN", pay_date))
            stmt_id += 1
    # one deliberately unrecognized status, to exercise the OTHER fallback
    statements.append(_ukg_pay_statement(rng, stmt_id, employee_account_ids[0], "PENDING_REVIEW", "2024-11-08"))
    return {"pay_statements": statements}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _generate_prismhr(rng: random.Random, output_dir: Path) -> Dict[str, Any]:
    company_input = _prismhr_company_input(rng)
    employees_input = []
    employee_ids = []
    for i, variant in enumerate(VARIANTS):
        bundle, emp_id = _prismhr_employee_bundle(rng, i, variant, "900")
        employees_input.append(bundle)
        employee_ids.append(emp_id)
    payroll_input = _prismhr_payroll_input(rng, employee_ids)

    files = {
        "company_input": _write(output_dir, "prismhr", "company_input.json", company_input),
        "employees_input": _write(output_dir, "prismhr", "employees_input.json", employees_input),
        "payroll_input": _write(output_dir, "prismhr", "payroll_input.json", payroll_input),
    }
    counts = {"companies": len(company_input["clientListResult"]["clientList"]),
              "employees": len(employees_input), "paychecks": len(payroll_input["payrollVoucher"])}
    return {"files": files, "counts": counts}


def _generate_isolved(rng: random.Random, output_dir: Path) -> Dict[str, Any]:
    company_input = _isolved_company_input(rng)
    employees_input = []
    employee_ids = []
    for i, variant in enumerate(VARIANTS):
        bundle = _isolved_employee_bundle(rng, i, variant, "9900", "9000")
        employees_input.append(bundle)
        employee_ids.append(bundle["profile"]["id"])
    payroll_input = _isolved_payroll_input(rng, employee_ids)

    files = {
        "company_input": _write(output_dir, "isolved", "company_input.json", company_input),
        "employees_input": _write(output_dir, "isolved", "employees_input.json", employees_input),
        "payroll_input": _write(output_dir, "isolved", "payroll_input.json", payroll_input),
    }
    counts = {"companies": len(company_input), "employees": len(employees_input),
              "paychecks": len(payroll_input["results"])}
    return {"files": files, "counts": counts}


def _generate_ukg(rng: random.Random, output_dir: Path) -> Dict[str, Any]:
    company_input = _ukg_company_input(rng)
    employees_input = []
    employee_ids = []
    for i, variant in enumerate(VARIANTS):
        bundle = _ukg_employee_bundle(rng, i, variant, "990001")
        employees_input.append(bundle)
        employee_ids.append(bundle["profile"]["id"])
    payroll_input = _ukg_payroll_input(rng, employee_ids)

    files = {
        "company_input": _write(output_dir, "ukg-ready", "company_input.json", company_input),
        "employees_input": _write(output_dir, "ukg-ready", "employees_input.json", employees_input),
        "payroll_input": _write(output_dir, "ukg-ready", "payroll_input.json", payroll_input),
    }
    counts = {"companies": len(company_input), "employees": len(employees_input),
              "paychecks": len(payroll_input["pay_statements"])}
    return {"files": files, "counts": counts}


_GENERATORS = {"prismhr": _generate_prismhr, "isolved": _generate_isolved, "ukg-ready": _generate_ukg}


def generate(provider: Optional[str] = None, seed: int = DEFAULT_SEED,
             output_dir: Path = FIXTURES_DIR) -> Dict[str, Any]:
    """Generate deterministic synthetic RAW fixtures for one provider, or all
    three if `provider` is omitted. Writes tests/fixtures/<provider>/
    {company,employees,payroll}_input.json and tests/fixtures/manifest.json;
    returns the manifest dict. Calling this twice with the same seed produces
    byte-identical files - no adapter is imported or called here (see module
    docstring for why that's a separate, later step).
    """
    if provider is not None and provider not in _GENERATORS:
        raise ValueError(f"Unknown provider {provider!r}; expected one of {sorted(_GENERATORS)}")

    providers_to_run = [provider] if provider else list(PROVIDERS)
    manifest: Dict[str, Any] = {"seed": seed, "providers": providers_to_run, "files": {}, "counts": {}}

    for i, p in enumerate(providers_to_run):
        rng = random.Random(seed + i)  # distinct but deterministic per-provider stream
        result = _GENERATORS[p](rng, output_dir)
        manifest["files"][p] = result["files"]
        manifest["counts"][p] = result["counts"]

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    import sys

    provider_arg = sys.argv[1] if len(sys.argv) > 1 else None
    result = generate(provider_arg)
    print(json.dumps(result, indent=2))
