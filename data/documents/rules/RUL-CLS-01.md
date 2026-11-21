---
doc_id: RUL-CLS-01
doc_type: rule
title: Train classes
version: "1.0"
effective_from: 2026-01-01
effective_to:
supersedes: []
language: en
status: active
related_docs: [RUL-BOOK-01, RUL-CAN-01]
---
## 1. Scope

This rule lists the travel classes Ujjwal Rail sells, and how fares are
set for each.

## 2. Classes offered

Not every train offers every class; `trains.classes` lists which
classes run on a given train.

| Code | Class name | Seating |
|---|---|---|
| SL  | Sleeper              | Open berths, no air conditioning |
| 3AC | AC 3-Tier            | 3 berths per bay, air-conditioned |
| 2AC | AC 2-Tier            | 2 berths per bay, air-conditioned |
| 1AC | AC First Class       | Private/semi-private cabins |
| CC  | AC Chair Car         | Airline-style seating, day trains |
| EC  | Executive Chair Car  | Wider airline-style seating, day trains |
| 2S  | Second Sitting       | Open seating, no air conditioning |

## 3. How a fare is set

A fare is a fixed amount in INR for a given train, class, and
origin–destination station pair, held in the `fares` table
(`train_no, class, from_code, to_code, fare`). Fares do not change by
time of booking, demand, or how full the train is — Ujjwal Rail does
not use dynamic pricing. The assistant never computes a fare itself; it
always reads it from this table.

## 4. Fare for part of a journey

If a passenger boards or leaves a train partway along its route, the
fare is still looked up directly for that `from_code`/`to_code` pair in
the `fares` table — it is not derived by subtracting two end-to-end
fares.

## 5. Multiple travellers

The total fare for a booking is the per-traveller fare for the chosen
class and route, multiplied by the number of travellers. Different
travellers on the same booking are always in the same class (Ujjwal
Rail does not support mixed-class bookings on a single booking ID).
