"""Registry of valid `settings` key *names* (docs/api-contracts.md §10).

SHARED-FROZEN (architecture §8) for the family patterns and types; the
concrete *values* come with the rules documents in Phase 1 — this file
holds no values, by design (phase0-tasks.md T6).

Used by `/ingest`'s `settings_changes` validation (D2): a change is
rejected with 400 unless `name` matches a registered key/family and
`value`'s type matches what that key declares.

Boundary convention (D4, v1.2): cancellation brackets are inclusive on
their lower bound — `over_48h` means "48h or more", `12h_to_48h` means
"12h up to (but not including) 48h", and so on. The same four brackets
are used consistently in the rules documents, this registry, and
`refund_quote`. A specific policy document may override this for one
key explicitly; if so, the override is noted in that key's `note` field.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ValueType = Literal["int_inr", "int_hours", "int_minutes", "float_pct", "int_count"]

# D4: four inclusive-lower-bound brackets, used by every per-class/per-status
# cancellation charge family below.
CANCEL_BRACKETS: tuple[str, ...] = ("over_48h", "12h_to_48h", "4h_to_12h", "under_4h")


@dataclass(frozen=True)
class SettingKeyFamily:
    """One registrable family of setting names.

    `pattern` is a regex (fullmatch) over the setting name. `example` is
    one concrete name from this family, used in docs and tests.
    """

    pattern: str
    value_type: ValueType
    unit: str
    description: str
    owner_doc_hint: str  # which doc family normally carries this (informational only)
    example: str


# Travel class codes are finalised by Data & Testing with the rules
# documents in Phase 1 (e.g. SL, 3AC, 2AC, 1AC, CC) — the family pattern
# below accepts any upper-case alnum class code so Phase 0 does not have
# to pre-guess the exact set (phase0-tasks.md "Over-modelling" risk).
_CLASS = r"[A-Z0-9]+"
_BRACKET = "|".join(CANCEL_BRACKETS)

FAMILIES: tuple[SettingKeyFamily, ...] = (
    SettingKeyFamily(
        pattern=rf"^cancel_charge_{_CLASS}_(?:{_BRACKET})$",
        value_type="int_inr",
        unit="INR",
        description="Cancellation charge for a confirmed traveller in this class and bracket.",
        owner_doc_hint="RUL-CAN-01 (rule), revised by CIR-* (circular)",
        example="cancel_charge_2AC_over_48h",
    ),
    SettingKeyFamily(
        pattern=rf"^cancel_charge_wl_(?:{_BRACKET})$",
        value_type="int_inr",
        unit="INR",
        description="Cancellation charge for a waitlisted traveller, by bracket.",
        owner_doc_hint="RUL-CAN-01",
        example="cancel_charge_wl_over_48h",
    ),
    SettingKeyFamily(
        pattern=rf"^cancel_charge_rac_(?:{_BRACKET})$",
        value_type="int_inr",
        unit="INR",
        description="Cancellation charge for an RAC traveller, by bracket.",
        owner_doc_hint="RUL-CAN-01",
        example="cancel_charge_rac_over_48h",
    ),
    SettingKeyFamily(
        pattern=r"^refund_pct_train_cancelled$",
        value_type="float_pct",
        unit="%",
        description="Refund percentage when the operator cancels the train (O7).",
        owner_doc_hint="RUL-CAN-01",
        example="refund_pct_train_cancelled",
    ),
    SettingKeyFamily(
        pattern=r"^refund_pct_late_over_\d+h$",
        value_type="float_pct",
        unit="%",
        description="Refund percentage for a train running more than N hours late.",
        owner_doc_hint="RUL-CAN-01",
        example="refund_pct_late_over_3h",
    ),
    SettingKeyFamily(
        pattern=r"^cancel_cutoff_hours_before_departure$",
        value_type="int_hours",
        unit="hours",
        description="Latest point before departure at which a cancellation is still allowed.",
        owner_doc_hint="RUL-CAN-01",
        example="cancel_cutoff_hours_before_departure",
    ),
    SettingKeyFamily(
        pattern=rf"^tatkal_charge_{_CLASS}$",
        value_type="int_inr",
        unit="INR",
        description="Tatkal surcharge for this class.",
        owner_doc_hint="RUL-TAT-01",
        example="tatkal_charge_3AC",
    ),
    SettingKeyFamily(
        pattern=r"^tatkal_open_hours_before$",
        value_type="int_hours",
        unit="hours",
        description="Hours before departure that the Tatkal window opens.",
        owner_doc_hint="RUL-TAT-01",
        example="tatkal_open_hours_before",
    ),
    SettingKeyFamily(
        pattern=r"^boarding_change_cutoff_hours$",
        value_type="int_hours",
        unit="hours",
        description="Latest point before departure at which the boarding station may be changed (O6).",
        owner_doc_hint="RUL-BRD-01",
        example="boarding_change_cutoff_hours",
    ),
    SettingKeyFamily(
        pattern=r"^action_expiry_minutes$",
        value_type="int_minutes",
        unit="minutes",
        description=(
            "How long a proposed change (pending action) stays open before it "
            "expires on the operational clock (D6) — never the business as_of."
        ),
        owner_doc_hint="RUL-BOOK-01",
        example="action_expiry_minutes",
    ),
    SettingKeyFamily(
        pattern=r"^max_pax_per_booking$",
        value_type="int_count",
        unit="passengers",
        description="Maximum travellers allowed on one booking.",
        owner_doc_hint="RUL-BOOK-01",
        example="max_pax_per_booking",
    ),
    SettingKeyFamily(
        pattern=r"^chart_prepared_hours_before$",
        value_type="int_hours",
        unit="hours",
        description="Hours before departure the reservation chart is prepared.",
        owner_doc_hint="RUL-BOOK-01",
        example="chart_prepared_hours_before",
    ),
)

_PYTHON_TYPES: dict[ValueType, tuple[type, ...]] = {
    "int_inr": (int,),
    "int_hours": (int,),
    "int_minutes": (int,),
    "int_count": (int,),
    "float_pct": (int, float),
}


def find_family(name: str) -> SettingKeyFamily | None:
    """Return the family `name` belongs to, or None if unregistered."""
    for family in FAMILIES:
        if re.fullmatch(family.pattern, name):
            return family
    return None


def is_registered(name: str) -> bool:
    return find_family(name) is not None


def value_matches_type(name: str, value: int | float) -> bool:
    """True iff `value`'s Python type matches the registered family's
    declared type for `name`. Unregistered names are handled by the
    caller via `is_registered` first (api-contracts §5.2)."""
    family = find_family(name)
    if family is None:
        return False
    return isinstance(value, _PYTHON_TYPES[family.value_type]) and not isinstance(value, bool)
