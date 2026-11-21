"""Deterministic, regex/keyword-based intent + entity extraction (R1/R4).

No LLM call here — this IS the "understand the query" step for this
MVP. It is deterministic by construction, so it behaves identically
whether MOCK_LLM is true or false; MOCK_LLM's actual effect (api-
contracts §13) is one layer down, in app/rag/retrieve.py's embedding
fallback, already built. Extraction never guesses a station, train,
class or date it can't actually find in the message — missing
entities simply mean that intent's tool isn't called (R4: "never the
thing doing the arithmetic or reading the timetable from memory" — nor
inventing an entity to make a tool call succeed).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, time, timedelta

CLASS_TOKENS = ("1AC", "2AC", "3AC", "SL", "CC", "EC", "2S")

_BOOKING_ID_RE = re.compile(r"\bUR-\d+\b", re.IGNORECASE)
_TRAIN_NO_RE = re.compile(r"\b\d{5}\b")
_CLASS_RE = re.compile(r"\b(" + "|".join(CLASS_TOKENS) + r")\b", re.IGNORECASE)
_FROM_TO_RE = re.compile(
    r"\bfrom\s+([A-Za-z][A-Za-z .]*?)\s+to\s+([A-Za-z][A-Za-z .]*?)"
    r"(?=\s+(?:on|this|tomorrow|today|after|before|at)\b|[?.!,]|$)",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_AFTER_TIME_RE = re.compile(r"\bafter\s+(\d{1,2})\s*(am|pm)\b", re.IGNORECASE)
_BEFORE_TIME_RE = re.compile(r"\bbefore\s+(\d{1,2})\s*(am|pm)\b", re.IGNORECASE)

_CANCEL_IMPERATIVE_RE = re.compile(r"\bcancel\s+(my\s+)?(ticket|booking)\b", re.IGNORECASE)
# "If I cancel my booking, how much..." is a conditional/informational
# refund question, not an instruction to actually cancel anything —
# despite also matching _CANCEL_IMPERATIVE_RE above (it contains the
# same "cancel my booking" phrase). Checked explicitly so the two are
# never confused (R5: /chat only ever proposes after a genuine request).
_CONDITIONAL_CANCEL_RE = re.compile(r"\bif\s+i\s+cancel\b", re.IGNORECASE)
_REFUND_RE = re.compile(r"\brefund\b|\bget\s+back\b|\bif\s+i\s+cancel\b|\bhow\s+much.*back\b", re.IGNORECASE)
_AVAILABILITY_RE = re.compile(r"\bseat\b|\bavailab", re.IGNORECASE)
_FARE_RE = re.compile(r"\bfare\b|\bcost\b|\bprice\b|\bhow\s+much\b", re.IGNORECASE)
_SEARCH_RE = re.compile(r"\btrain(s)?\b", re.IGNORECASE)
_HUMAN_RE = re.compile(
    r"\b(talk to|speak to|connect me to)\s+(a\s+)?(person|human|agent)\b|\bcomplain(t|ts|ing)?\b|"
    r"\bharass|\bsafety\b.*\b(issue|problem|concern)\b",
    re.IGNORECASE,
)
_PRIVACY_OTHER_PERSON_RE = re.compile(r"\b(my\s+)?friend'?s?\b|\bsomeone\s+else'?s?\b", re.IGNORECASE)

# Policy-ish subjects: when present, always worth a retrieve_context()
# pass, whether or not another tool intent also matched (RAG and the
# tool-routed answer can legitimately both apply to one message).
_POLICY_KEYWORDS_RE = re.compile(
    r"\bpet\b|\bluggage\b|\bid\s+proof\b|\bconcession\b|\btatkal\b|\bwaitlist\b|"
    r"\bboarding station\b|\brule\b|\bpolicy\b|\ballowed\b|\bcomplaint\b",
    re.IGNORECASE,
)
# A broader travel-relatedness gate, used only to distinguish "not_found"
# (travel-related, nothing matched) from "refusal" (plainly off-topic).
_TRAVEL_RELATED_RE = re.compile(
    r"\btrain\b|\bticket\b|\bbooking\b|\bfare\b|\bseat\b|\brefund\b|\bstation\b|\bjourney\b|\btravel\b|\brailway\b",
    re.IGNORECASE,
)


@dataclass
class ExtractedEntities:
    booking_id: str | None = None
    train_no: str | None = None
    cls: str | None = None
    from_text: str | None = None
    to_text: str | None = None
    journey_date: date | None = None
    after: time | None = None
    before: time | None = None


@dataclass
class ParsedMessage:
    entities: ExtractedEntities
    wants_cancel: bool
    wants_refund_info: bool
    wants_availability: bool
    wants_fare: bool
    wants_search: bool
    wants_policy: bool
    wants_human: bool
    mentions_other_person: bool
    is_travel_related: bool


def _parse_time(hour: str, meridiem: str) -> time:
    h = int(hour) % 12
    if meridiem.lower() == "pm":
        h += 12
    return time(h, 0)


def extract_entities(message: str, today: date) -> ExtractedEntities:
    entities = ExtractedEntities()

    booking_match = _BOOKING_ID_RE.search(message)
    if booking_match:
        entities.booking_id = booking_match.group(0).upper()

    train_match = _TRAIN_NO_RE.search(message)
    if train_match:
        entities.train_no = train_match.group(0)

    class_match = _CLASS_RE.search(message)
    if class_match:
        entities.cls = class_match.group(1).upper()

    from_to_match = _FROM_TO_RE.search(message)
    if from_to_match:
        entities.from_text = from_to_match.group(1).strip()
        entities.to_text = from_to_match.group(2).strip()

    iso_match = _ISO_DATE_RE.search(message)
    if iso_match:
        entities.journey_date = date.fromisoformat(iso_match.group(1))
    elif re.search(r"\btomorrow\b", message, re.IGNORECASE):
        entities.journey_date = today + timedelta(days=1)
    elif re.search(r"\btoday\b", message, re.IGNORECASE):
        entities.journey_date = today

    after_match = _AFTER_TIME_RE.search(message)
    if after_match:
        entities.after = _parse_time(*after_match.groups())
    before_match = _BEFORE_TIME_RE.search(message)
    if before_match:
        entities.before = _parse_time(*before_match.groups())

    return entities


def parse_message(message: str, today: date) -> ParsedMessage:
    entities = extract_entities(message, today)
    is_conditional_cancel = bool(_CONDITIONAL_CANCEL_RE.search(message))
    wants_cancel = bool(_CANCEL_IMPERATIVE_RE.search(message)) and not is_conditional_cancel
    return ParsedMessage(
        entities=entities,
        wants_cancel=wants_cancel,
        wants_refund_info=bool(_REFUND_RE.search(message)) and not wants_cancel,
        wants_availability=bool(_AVAILABILITY_RE.search(message)),
        wants_fare=bool(_FARE_RE.search(message)),
        wants_search=bool(_SEARCH_RE.search(message)) or bool(entities.from_text and entities.to_text),
        wants_policy=bool(_POLICY_KEYWORDS_RE.search(message)),
        wants_human=bool(_HUMAN_RE.search(message)),
        mentions_other_person=bool(_PRIVACY_OTHER_PERSON_RE.search(message)),
        is_travel_related=bool(_TRAVEL_RELATED_RE.search(message)),
    )
