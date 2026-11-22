"""The client's own example transactions (UAT report, section 5).

TEST DATA ONLY. These are UX examples taken from another application's
video; they must never be used as seed, demo or migration data. Amounts are
minor units (19,208.11 -> 1_920_811). The expected month results below were
calculated from this list, not copied from the client's reference-app
summaries (which cover more items than the visible list and were never
reconciled).
"""

from __future__ import annotations

# (name, amount_minor, direction, recurrence, start_date, end_date)
CLIENT_EXAMPLES: list[tuple[str, int, str, str, str, str | None]] = [
    ("Driver Salary", 220_000, "expense", "monthly", "2026-11-26", None),
    ("Gitex Kay", 1_800_000, "income", "one_time", "2026-11-26", None),
    ("SEC", 145_000, "expense", "monthly", "2026-11-26", None),
    ("Telco", 200_000, "expense", "monthly", "2026-11-26", None),
    ("Veridos Salary", 5_761_250, "income", "monthly", "2026-11-26", None),
    ("Kaytus Salary", 3_850_000, "income", "monthly", "2026-11-22", None),
    ("Binghatti", 5_591_560, "expense", "one_time", "2026-12-25", None),
    ("BMW", 31_100_000, "expense", "one_time", "2026-12-24", None),
    ("Stock 2", 482_800, "income", "one_time", "2026-12-09", None),
    ("Personal Loan", 1_920_811, "expense", "monthly", "2026-11-19", "2027-03-29"),
    ("Maid Salary", 150_000, "expense", "monthly", "2026-11-18", None),
]

# month -> (income_minor, expense_minor, net_minor)
EXPECTED_MONTHS: dict[str, tuple[int, int, int]] = {
    "2026-11": (11_411_250, 2_635_811, 8_775_439),
    "2026-12": (10_094_050, 39_327_371, -29_233_321),
    "2027-01": (9_611_250, 2_635_811, 6_975_439),
    "2027-02": (9_611_250, 2_635_811, 6_975_439),
    "2027-03": (9_611_250, 2_635_811, 6_975_439),
    "2027-04": (9_611_250, 715_000, 8_896_250),  # the loan ended on 29 Mar
}

# month -> {name: due date} for the recurring items the client listed.
EXPECTED_DUE_DATES: dict[str, dict[str, str]] = {
    "2026-11": {
        "Kaytus Salary": "2026-11-22",
        "Driver Salary": "2026-11-26",
        "Personal Loan": "2026-11-19",
        "SEC": "2026-11-26",
        "Telco": "2026-11-26",
        "Maid Salary": "2026-11-18",
    },
    "2026-12": {
        "Kaytus Salary": "2026-12-22",
        "Driver Salary": "2026-12-26",
        "Personal Loan": "2026-12-19",
        "SEC": "2026-12-26",
        "Telco": "2026-12-26",
        "Maid Salary": "2026-12-18",
    },
    "2027-01": {
        "Kaytus Salary": "2027-01-22",
        "Driver Salary": "2027-01-26",
        "Personal Loan": "2027-01-19",
        "SEC": "2027-01-26",
        "Telco": "2027-01-26",
        "Maid Salary": "2027-01-18",
    },
}
