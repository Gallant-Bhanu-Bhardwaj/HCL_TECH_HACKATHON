---
doc_id: RUL-OPC-01
doc_type: rule
title: Refunds when Ujjwal Rail cancels or delays a train
version: "1.0"
effective_from: 2026-01-01
effective_to:
supersedes: []
language: en
status: active
related_docs: [RUL-CAN-01, RUL-REF-01, RUL-GRV-01]
---
## 1. Scope

This rule covers refunds when the disruption is caused by Ujjwal Rail
(the train is cancelled or badly delayed), not by the passenger's own
decision to cancel. For a passenger-initiated cancellation, see
RUL-CAN-01.

## 2. Train cancelled by the operator

If Ujjwal Rail cancels a train before departure, every confirmed, RAC
and waitlisted booking on it is marked
`train_cancelled_by_operator` and refunded automatically and in full
(`refund_pct_train_cancelled` = 100%) — no cancellation charge is
deducted. The passenger does not need to ask; the refund is processed
against the booking once the cancellation is recorded. If a passenger
asks about such a booking before the automatic refund has posted, the
assistant explains the full-refund entitlement and that it is already
in progress; it does not create a new refund request.

## 3. Train more than 3 hours late

If a train is running more than 3 hours late at the passenger's
boarding station, and the passenger states — before the train actually
arrives — that they will not be travelling, the booking is treated as
a full refund case (`refund_pct_late_over_3h` = 100%), with no
cancellation charge. This requires an explicit statement from the
passenger; Ujjwal Rail does not assume a late passenger is not coming.
Ujjwal Rail's systems in this data kit do not track live running delay
figures, so a passenger reporting a delay is directed to the refunds
desk (Level 2) with the booking details; the assistant does not invent
a delay figure or approve the refund itself.

## 4. What is not covered here

A dispute about whether a refund under this rule was correctly paid, or
a claim that a delay happened but was not recorded, goes to the
refunds desk under RUL-GRV-01. The assistant never promises an outcome
on a disputed case.
