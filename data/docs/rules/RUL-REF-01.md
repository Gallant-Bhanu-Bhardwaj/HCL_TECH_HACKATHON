---
doc_id: RUL-REF-01
doc_type: rule
title: Refund eligibility and calculation
version: "1.0"
effective_from: 2026-01-01
effective_to:
supersedes: []
language: en
status: active
related_docs: [RUL-CAN-01, RUL-RAC-01, RUL-OPC-01]
---
## 1. Scope

This rule explains how a refund amount is worked out once a
cancellation is accepted under RUL-CAN-01, and lists the few cases
where no refund, or a different refund, applies.

## 2. The refund formula

For a self-initiated cancellation of a confirmed traveller:

```
refund = amount_paid − cancellation_charge
```

`amount_paid` is the fare actually paid for that traveller (see
RUL-CLS-01 for how fares are set). `cancellation_charge` comes from the
table in RUL-CAN-01 §3, using the class of that traveller and the
number of hours between the moment of cancellation and the train's
scheduled departure from the passenger's boarding station.

This is always computed by code from the `settings` table, never
estimated by the assistant and never read off a cached number — a
rule or circular changing after a ticket was booked still applies if it
is in effect at the moment of cancellation (R6).

## 3. Rounding

Refunds are whole rupees. If a calculation under a future rule ever
produces a fraction of a rupee, it is rounded down (the passenger is
never charged the rounding difference).

## 4. Hours-before-departure: the exact cutoff moment

"Hours before departure" is measured from the instant the cancellation
request is accepted to the scheduled departure instant at the
passenger's **boarding** station for that journey (not the train's
origin station, if the passenger boards further down the line). The
bracket is chosen using the **inclusive-lower-bound** rule stated in
RUL-CAN-01 §3: exactly 48h, 12h or 4h remaining belongs to the bracket
that starts at that value.

## 5. No refund at all

No refund is paid for:
- A no-show (passenger did not travel and did not cancel in advance) —
  the full cancellation charge for "under 4h" effectively applies, as
  there is no later cancellation to accept.
- A waitlisted ticket that never got a seat at the time the chart was
  prepared, where the passenger did not cancel beforehand — RUL-RAC-01
  §3 explains the automatic handling in that case, which is a full
  refund, not a penalty; this bullet covers only a *confirmed* no-show.

## 6. Full refund cases

A full refund (no cancellation charge) is paid when:
- Ujjwal Rail cancels the train (RUL-OPC-01 §2): `refund_pct_train_cancelled`
  = 100%.
- The train runs more than 3 hours late at the passenger's boarding
  station and the passenger chooses not to travel and says so before
  the train actually arrives (RUL-OPC-01 §3): `refund_pct_late_over_3h`
  = 100%.
- A waitlisted traveller whose ticket never got a seat (RUL-RAC-01 §3).

## 7. Who this refund formula does not cover

A refund that depends on a judgement call — for example "the train was
on time but I missed it because of a Ujjwal Rail staff error" — is not
decided by this formula. It is filed with the refunds desk (RUL-GRV-01)
and no amount is promised by the assistant.
