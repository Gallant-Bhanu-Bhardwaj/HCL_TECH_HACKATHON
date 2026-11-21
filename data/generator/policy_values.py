"""Canonical Ujjwal Rail policy VALUES — the single source of truth.

Every number quoted in data/documents/**/*.md (rules/circulars/FAQs) was
copied from this file by hand when those documents were written, and
generate_data.py imports this file directly when building the
`settings` / `settings_history` rows. This is what "keep values
consistent across rules, circulars and FAQs" (master data-generation
prompt, Phase 3) is enforced by — one file, not three independent
copies that can drift.

Boundary convention (architecture.md D4, api-contracts.md §10): every
bracket's lower bound is inclusive. `over_48h` = "48h or more".
Fictional values only — Ujjwal Rail is not a real operator.
"""
from __future__ import annotations

from datetime import date

# Anchor "today" for the whole data kit — matches the worked examples
# already published in docs/api-contracts.md (2026-12-03 / 2026-12-05).
# Overridable via generate_data.py --base-date.
BASE_DATE: date = date(2026, 12, 3)

# Seat availability horizon (guide §4.2: "next 14 days").
SEAT_HORIZON_DAYS: int = 14

CLASSES: tuple[str, ...] = ("SL", "3AC", "2AC", "1AC", "CC", "EC", "2S")
TATKAL_CLASSES: tuple[str, ...] = ("SL", "3AC", "2AC", "CC")  # 1AC/EC/2S: no Tatkal on Ujjwal Rail
BRACKETS: tuple[str, ...] = ("over_48h", "12h_to_48h", "4h_to_12h", "under_4h")

# ---------------------------------------------------------------------
# RUL-CAN-01 (original rule, effective from the start of the data kit)
# ---------------------------------------------------------------------
# Confirmed (CNF) traveller cancellation charge, INR, by class and bracket.
CANCEL_CHARGE_CNF_RUL_CAN_01: dict[str, dict[str, int]] = {
    "SL":  {"over_48h": 60,  "12h_to_48h": 120, "4h_to_12h": 180, "under_4h": 300},
    "3AC": {"over_48h": 90,  "12h_to_48h": 180, "4h_to_12h": 270, "under_4h": 450},
    "2AC": {"over_48h": 150, "12h_to_48h": 240, "4h_to_12h": 360, "under_4h": 600},
    "1AC": {"over_48h": 260, "12h_to_48h": 400, "4h_to_12h": 600, "under_4h": 1000},
    "CC":  {"over_48h": 70,  "12h_to_48h": 140, "4h_to_12h": 210, "under_4h": 350},
    "EC":  {"over_48h": 160, "12h_to_48h": 260, "4h_to_12h": 390, "under_4h": 650},
    "2S":  {"over_48h": 30,  "12h_to_48h": 60,  "4h_to_12h": 90,  "under_4h": 150},
}

# RAC / WL traveller cancellation charge, INR, by bracket (class-independent).
CANCEL_CHARGE_RAC_RUL_CAN_01: dict[str, int] = {
    "over_48h": 50, "12h_to_48h": 50, "4h_to_12h": 50, "under_4h": 50,
}
CANCEL_CHARGE_WL_RUL_CAN_01: dict[str, int] = {
    "over_48h": 0, "12h_to_48h": 0, "4h_to_12h": 0, "under_4h": 0,
}

CANCEL_CUTOFF_HOURS_BEFORE_DEPARTURE: int = 0  # cancellation allowed any time before departure (0h cutoff)

REFUND_PCT_TRAIN_CANCELLED: float = 100.0   # operator cancels the train -> full refund
REFUND_PCT_LATE_OVER_3H: float = 100.0      # >3h late at boarding station and passenger does not travel -> full refund

# ---------------------------------------------------------------------
# CIR-2026-07 (past-effective circular, supersedes RUL-CAN-01's 2AC rate)
# ---------------------------------------------------------------------
CIR_2026_07_EFFECTIVE_FROM = date(2026, 11, 15)
CANCEL_CHARGE_2AC_OVER_48H_CIR_2026_07: int = 200   # 150 -> 200 (matches the §6.1/§11 worked examples)

# ---------------------------------------------------------------------
# CIR-2026-11 (FUTURE-effective circular; supersedes CIR-2026-07 further)
# ---------------------------------------------------------------------
CIR_2026_11_EFFECTIVE_FROM = date(2026, 12, 10)   # within the 14-day seat/demo window, after BASE_DATE
CANCEL_CHARGE_2AC_OVER_48H_CIR_2026_11: int = 250  # 200 -> 250

# ---------------------------------------------------------------------
# CIR-2026-01 (past-effective, Tatkal charge revision)
# ---------------------------------------------------------------------
CIR_2026_01_EFFECTIVE_FROM = date(2026, 10, 1)

TATKAL_CHARGE_RUL_TAT_01: dict[str, int] = {"SL": 100, "3AC": 300, "2AC": 400, "CC": 150}
TATKAL_CHARGE_CIR_2026_01: dict[str, int] = {"SL": 120, "3AC": 350, "2AC": 450, "CC": 180}
TATKAL_OPEN_HOURS_BEFORE: int = 24

# ---------------------------------------------------------------------
# Other settings (unchanged by any circular in this data kit)
# ---------------------------------------------------------------------
BOARDING_CHANGE_CUTOFF_HOURS: int = 24
ACTION_EXPIRY_MINUTES: int = 15
MAX_PAX_PER_BOOKING: int = 6
CHART_PREPARED_HOURS_BEFORE: int = 4


def current_cancel_charge_cnf(as_of: date) -> dict[str, dict[str, int]]:
    """2AC/over_48h value as of `as_of`, honouring the two circulars
    above (D4/D6: a pure function of the policy value tables and the
    as_of date, no clock, no I/O)."""
    table = {cls: dict(brackets) for cls, brackets in CANCEL_CHARGE_CNF_RUL_CAN_01.items()}
    if as_of >= CIR_2026_07_EFFECTIVE_FROM:
        table["2AC"]["over_48h"] = CANCEL_CHARGE_2AC_OVER_48H_CIR_2026_07
    if as_of >= CIR_2026_11_EFFECTIVE_FROM:
        table["2AC"]["over_48h"] = CANCEL_CHARGE_2AC_OVER_48H_CIR_2026_11
    return table


def current_tatkal_charge(as_of: date) -> dict[str, int]:
    if as_of >= CIR_2026_01_EFFECTIVE_FROM:
        return dict(TATKAL_CHARGE_CIR_2026_01)
    return dict(TATKAL_CHARGE_RUL_TAT_01)
