---
doc_id: RUL-RAC-01
doc_type: rule
title: RAC and waitlist rules
version: "1.0"
effective_from: 2026-01-01
effective_to:
supersedes: []
language: en
status: active
related_docs: [RUL-BOOK-01, RUL-CAN-01, RUL-REF-01]
---
## 1. Scope

This rule explains what RAC and waitlisted (WL) mean on Ujjwal Rail,
and what happens to each as the journey date approaches.

## 2. RAC (Reservation Against Cancellation)

An RAC ticket shares a berth with another RAC traveller (both get a
seat, not a full berth, until the chart is finalised). An RAC traveller
may be allotted their own berth automatically if one frees up before
the chart is prepared; this is ordinary processing, not something the
passenger requests.

## 3. Waitlisted (WL) tickets and chart preparation

A waitlisted traveller has no seat at all yet. At chart preparation
(4 hours before departure from the train's origin station,
`chart_prepared_hours_before`, RUL-BOOK-01 §4), Ujjwal Rail finalises
every booking for that train/date/class:

- A waitlisted traveller who reaches a confirmed or RAC position by
  chart time is updated to that status.
- A waitlisted traveller who is still on the waitlist at chart time
  does not travel on that booking, and is **refunded in full**
  automatically (`refund_pct` = 100% for an unconfirmed waitlisted
  ticket) — no cancellation charge, because no seat was ever used.

## 4. No promotion triggered by someone else's cancellation

Ujjwal Rail does **not** automatically move an RAC or waitlisted
traveller into a seat that a *different* traveller just cancelled
through the passenger-facing cancel flow. Seat inventory is simply
returned to `available` (RUL-CAN-01, architecture decision D5). Any
waitlist movement before chart time happens only through Ujjwal Rail's
own internal allocation run, not as an instant reaction to one
passenger's cancellation. The assistant must never tell a passenger
that cancelling a ticket will move someone else up the waitlist — this
is a Level 3 action (never performed, never implied).

## 5. Cancelling an RAC or waitlisted ticket yourself

See RUL-CAN-01 §4 for the charge: Rs 50 flat for RAC, nothing for
waitlisted, regardless of how close to departure the cancellation is.
