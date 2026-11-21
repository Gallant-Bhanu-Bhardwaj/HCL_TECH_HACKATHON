---
doc_id: RUL-CON-01
doc_type: rule
title: Concessions
version: "1.0"
effective_from: 2026-01-01
effective_to:
supersedes: []
language: en
status: active
related_docs: [RUL-ID-01, RUL-BOOK-01]
---
## 1. Scope

This rule lists the fare concessions Ujjwal Rail offers and how a
passenger claims one.

## 2. Who qualifies

| Concession | Discount | Proof required |
|---|---|---|
| Senior citizen (60+)         | 40% off base fare | Government photo ID showing date of birth |
| Student (recognised course)  | 25% off base fare, SL/3AC only | Valid institution-issued student ID, renewed each academic year |
| Person with disability + 1 attendant | 50% off base fare for both | Government-issued disability certificate |

Concession fares are pre-loaded into the `fares` table for the
qualifying class/route combinations; the assistant looks the
concession fare up like any other fare, it does not calculate the
percentage itself.

## 3. Claiming a concession

A concession must be claimed, with proof, **at the time of booking** —
it cannot be added to an existing booking afterwards, and the chat
assistant does not decide eligibility on its own. A request to apply a
concession to an existing booking, or a concession the assistant cannot
verify eligibility for from the booking record, is handed to the
concessions desk (Level 2) with the booking details; the assistant
never promises the concession will be approved.

## 4. Combining concessions

Only one concession applies per traveller per booking; concessions are
not stacked (for example, a senior citizen who is also a student gets
the senior citizen rate only, whichever single fare is pre-loaded).

## 5. Cancellation of a concession ticket

A concession ticket is cancelled under the same RUL-CAN-01 rules as any
other ticket of that class; the cancellation charge is not discounted.
