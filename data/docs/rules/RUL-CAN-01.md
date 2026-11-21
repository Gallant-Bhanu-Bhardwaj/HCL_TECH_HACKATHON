---
doc_id: RUL-CAN-01
doc_type: rule
title: Cancellation rules and charges
version: "1.0"
effective_from: 2026-01-01
effective_to:
supersedes: []
language: en
status: active
related_docs: [RUL-REF-01, RUL-RAC-01, RUL-BOOK-01]
---
## 1. Scope

This rule sets out when a passenger may cancel a confirmed (CNF), RAC or
waitlisted (WL) booking on Ujjwal Rail, and the cancellation charge that
applies. It does not cover cancellations caused by Ujjwal Rail itself
(train cancelled or very late) — see RUL-OPC-01 for those.

## 2. Who may cancel, and when

A passenger may cancel their own booking at any time before the train's
actual departure from the passenger's boarding station (cancellation
cutoff: 0 hours before departure — there is no "too close to departure"
bar on cancelling, only on the refund amount). A cancellation after the
train has departed is not accepted through this flow and is treated as
a "did not travel" claim under RUL-OPC-01 §3.

## 3. Refund table (confirmed travellers)

The cancellation charge for a confirmed (CNF) traveller is a flat
amount in INR, fixed by the traveller's class and by how many hours
remain before the train's scheduled departure from the passenger's
boarding station at the moment of cancellation. The refund is
`amount_paid − charge`.

Bracket boundaries are **inclusive on the lower bound**: a cancellation
made with exactly 48.0 hours remaining falls in "48h or more", not in
"12h to 48h". A cancellation with 47 hours 59 minutes remaining falls in
"12h to 48h".

| Class | 48h or more | 12h to 48h | 4h to 12h | Under 4h |
|---|---|---|---|---|
| SL  | Rs 60  | Rs 120 | Rs 180 | Rs 300  |
| 3AC | Rs 90  | Rs 180 | Rs 270 | Rs 450  |
| 2AC | Rs 150 | Rs 240 | Rs 360 | Rs 600  |
| 1AC | Rs 260 | Rs 400 | Rs 600 | Rs 1000 |
| CC  | Rs 70  | Rs 140 | Rs 210 | Rs 350  |
| EC  | Rs 160 | Rs 260 | Rs 390 | Rs 650  |
| 2S  | Rs 30  | Rs 60  | Rs 90  | Rs 150  |

These are the `cancel_charge_<CLASS>_<bracket>` settings (for example
`cancel_charge_2AC_over_48h`). CIR-2026-07 and CIR-2026-11 later revise
the 2AC/48h-or-more value — see §6.

## 4. Refund table (RAC and waitlisted travellers)

An RAC traveller is charged a flat Rs 50 regardless of class or
bracket (`cancel_charge_rac_<bracket>`). A waitlisted traveller who
cancels before the chart is prepared is charged **nothing**
(`cancel_charge_wl_<bracket>` = Rs 0) — a waitlisted ticket never
confirmed a seat, so there is no service to charge for.

## 5. Mixed-status bookings

If a booking has more than one traveller and they are not all in the
same status (for example one CNF and one WL), Ujjwal Rail only supports
cancelling the **whole booking** in one action. The refund is the sum
of each traveller's own refund, computed from their own status and the
same cutoff time.

## 6. How a revision takes effect

The cancellation-charge table above is the rule as it stood from
2026-01-01. A circular may revise one or more values in this table from
a stated effective date; from that date, the circular's value applies
and this rule's original value no longer does (R6: newer official
source wins). CIR-2026-07 (effective 2026-11-15) revised the 2AC/48h-
or-more charge from Rs 150 to Rs 200. CIR-2026-11 (effective
2026-12-10) revises it further, from Rs 200 to Rs 250. Both circulars
are cited alongside this rule whenever the 2AC/48h-or-more bracket is
quoted on or after their effective date.

## 7. What this rule does not decide

This rule does not decide whether a waitlisted traveller gets promoted
when another traveller cancels — Ujjwal Rail does not promote waitlists
automatically (see RUL-RAC-01 §4). It also does not cover a refund
dispute (wrong amount credited) — that goes to the refunds desk under
RUL-GRV-01.
