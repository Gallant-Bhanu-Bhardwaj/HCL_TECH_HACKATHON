---
doc_id: RUL-BRD-01
doc_type: rule
title: Changing the boarding station
version: "1.0"
effective_from: 2026-01-01
effective_to:
supersedes: []
language: en
status: active
related_docs: [RUL-BOOK-01, RUL-CLS-01]
---
## 1. Scope

This rule covers changing which station a passenger boards at, for an
existing confirmed or RAC booking.

## 2. What may be changed

A passenger may move their boarding station to any **later** stop on
the same train, on the same journey date, that is still before the
booking's destination station (`train_stops`, ordered by
`stop_order`). Moving the boarding station **earlier** than the
original (for example, to catch the train sooner) is not supported
through this flow — that is a new booking.

## 3. Cutoff

A boarding-station change must be requested and confirmed at least
**24 hours** before the train's scheduled departure from the
**original** boarding station (`boarding_change_cutoff_hours` = 24).
After that cutoff, the request is refused; the passenger is told they
may cancel and rebook instead, subject to RUL-CAN-01.

## 4. Fare effect

Changing the boarding station to a later stop does **not** change the
fare already paid, even if the fare for the new, shorter leg would
normally be lower. Ujjwal Rail treats this as a convenience for the
passenger, not a partial cancellation; no partial refund is issued for
the unused portion of the original leg.

## 5. Confirmation and check

Like any Level 1 change, a boarding-station change is only made after
the passenger confirms a preview showing the new boarding station and
train/date/class; the booking record is updated and then re-read back
to the passenger to confirm the new boarding station was recorded.
