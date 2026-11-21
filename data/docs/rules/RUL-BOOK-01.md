---
doc_id: RUL-BOOK-01
doc_type: rule
title: Booking rules and booking lifecycle
version: "1.0"
effective_from: 2026-01-01
effective_to:
supersedes: []
language: en
status: active
related_docs: [RUL-CLS-01, RUL-RAC-01, RUL-ID-01]
---
## 1. Scope

This rule describes how a booking is made on Ujjwal Rail, what status
it can be in, and the limits that apply to every booking.

## 2. Booking lifecycle

A booking moves through these statuses only: `confirmed`, `rac`,
`waitlisted`, `cancelled`, `train_cancelled_by_operator`. A new booking
is allotted a confirmed (CNF) seat if one is available in the chosen
class at the time of booking; otherwise it is placed in RAC if RAC
capacity remains, otherwise on the waitlist. Ujjwal Rail does not
automatically move a waitlisted or RAC traveller up when another
traveller on the same train cancels — see RUL-RAC-01 §4.

## 3. Passengers per booking

A single booking may include up to **6** travellers
(`max_pax_per_booking` = 6). Each traveller on a booking is recorded
individually (name, age, their own status, and their coach/berth once
allotted) under `booking_travellers`, because travellers on the same
booking can end up in different statuses (for example one confirmed,
one waitlisted).

## 4. Chart preparation

The reservation chart for a train/date/class is prepared **4 hours**
before scheduled departure from the train's origin station
(`chart_prepared_hours_before` = 4). Before the chart is prepared, a
waitlisted traveller may still move up as seats free up from other
cancellations on that train (ordinary waitlist processing, not the
"promotion on your own cancellation" case covered in RUL-RAC-01 §4).
After the chart is prepared, the waitlist for that train/date/class is
final.

## 5. Changing a booking after it is made

Only two kinds of change are offered directly to the passenger, both
requiring the passenger's confirmation before anything happens
(R5): cancelling the booking (RUL-CAN-01) and changing the boarding
station (RUL-BRD-01). A fare class change, a date change, or adding a
traveller to an existing booking is not offered; the passenger is asked
to cancel and book again, or (if it depends on circumstances staff must
judge) the request is handed to the booking desk.

## 6. How long a proposed change stays open

Once the assistant shows a passenger a preview of a change (a
cancellation refund, for example) and asks them to confirm, that
proposal stays open for **15 minutes** (`action_expiry_minutes` = 15).
If it is not confirmed within that time, it expires and nothing
happens; the passenger must ask again to get a fresh preview.

## 7. Confirming twice

Confirming the same proposed change a second time does not cancel or
book anything a second time. The second confirmation simply reports
the same outcome as the first (idempotent).
