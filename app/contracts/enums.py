"""Shared enums (docs/api-contracts.md §3). SHARED-FROZEN."""
from __future__ import annotations

from enum import Enum


class AnswerType(str, Enum):
    ANSWER = "answer"
    CLARIFICATION = "clarification"
    CONFIRM_NEEDED = "confirm_needed"
    ACTION_DONE = "action_done"
    HANDED_TO_HUMAN = "handed_to_human"
    NOT_FOUND = "not_found"
    REFUSAL = "refusal"


class ActionType(str, Enum):
    BOOK_TICKET = "book_ticket"
    CANCEL_BOOKING = "cancel_booking"
    CHANGE_BOARDING_STATION = "change_boarding_station"


class ActionStatus(str, Enum):
    PROPOSED = "proposed"
    EXECUTING = "executing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TravellerStatus(str, Enum):
    CNF = "CNF"
    RAC = "RAC"
    WL = "WL"


class BookingStatus(str, Enum):
    CONFIRMED = "confirmed"
    RAC = "rac"
    WAITLISTED = "waitlisted"
    CANCELLED = "cancelled"
    TRAIN_CANCELLED_BY_OPERATOR = "train_cancelled_by_operator"


class ChangeLevel(int, Enum):
    LOOKUP = 0
    OWN_BOOKING_CHANGE = 1
    STAFF_DECIDES = 2
    NEVER = 3


class Intent(str, Enum):
    FIND_TRAIN = "find_train"
    CHECK_SEAT = "check_seat"
    GET_FARE = "get_fare"
    BOOKING_STATUS = "booking_status"
    REFUND_QUOTE = "refund_quote"
    CAN_CANCEL = "can_cancel"
    RULES_QUESTION = "rules_question"
    BOOK_TICKET = "book_ticket"
    CANCEL_BOOKING = "cancel_booking"
    CHANGE_BOARDING_STATION = "change_boarding_station"
    COMPLAINT_OR_DISPUTE = "complaint_or_dispute"
    SAFETY_REPORT = "safety_report"
    HUMAN_REQUEST = "human_request"
    OTHER_BOOKING_OR_PERSON = "other_booking_or_person"
    OUT_OF_SCOPE = "out_of_scope"
    SMALLTALK = "smalltalk"
    UNCLEAR = "unclear"


class Desk(str, Enum):
    COMPLAINTS = "complaints"
    REFUNDS = "refunds"
    SAFETY = "safety"
    CONCESSIONS = "concessions"
    GENERAL = "general"


class Language(str, Enum):
    EN = "en"
    HI = "hi"
    HINGLISH = "hinglish"


class DocType(str, Enum):
    RULE = "rule"
    CIRCULAR = "circular"
    FAQ = "faq"


class BookingOutcome(str, Enum):
    """Result of a new booking attempt (architecture.md O4): CNF if a seat
    is free, else RAC if RAC space remains, else WL. No other outcome.
    """

    CNF = "CNF"
    RAC = "RAC"
    WL = "WL"
    FULL = "FULL"


# D3: at most two consecutive clarification answers per session.
MAX_CLARIFICATIONS = 2
