---
doc_id: RUL-TAT-01
doc_type: rule
title: Tatkal booking rules
version: "1.0"
effective_from: 2026-01-01
effective_to:
supersedes: []
language: en
status: active
related_docs: [RUL-BOOK-01, RUL-CLS-01, RUL-CAN-01]
---
## 1. Scope

This rule covers Tatkal (last-minute, premium) booking on Ujjwal Rail.

## 2. When the Tatkal window opens

Tatkal booking for a given train/date/class opens **24 hours** before
that train's scheduled departure from its origin station
(`tatkal_open_hours_before` = 24). Before that, only ordinary booking
is available for that journey.

## 3. Which classes offer Tatkal

Tatkal is offered only in SL, 3AC, 2AC and CC. It is not offered in
1AC, EC or 2S on Ujjwal Rail.

## 4. Tatkal surcharge

A Tatkal booking carries a surcharge on top of the ordinary fare for
that class and route, in addition to the ordinary fare from RUL-CLS-01.
The current surcharges are:

| Class | Tatkal surcharge |
|---|---|
| SL  | Rs 120 |
| 3AC | Rs 350 |
| 2AC | Rs 450 |
| CC  | Rs 180 |

These are the `tatkal_charge_<CLASS>` settings. They were revised
upward from an earlier, lower schedule by CIR-2026-01 (see that
circular for the superseded values and the effective date).

## 5. Cancelling a Tatkal ticket

A Tatkal ticket is cancelled under the same RUL-CAN-01 rules as any
other confirmed ticket, by class and hours-before-departure bracket.
The Tatkal surcharge is treated as part of `amount_paid` and is not
separately refundable or separately charged for.

## 6. What the assistant does not do

The assistant can quote the Tatkal surcharge and explain the opening
time; it does not book a Tatkal ticket on the passenger's behalf
outside the ordinary propose → confirm flow, and never promises a
Tatkal seat before availability is actually checked.
