---
doc_id: RUL-ID-01
doc_type: rule
title: Passenger ID requirements
version: "1.0"
effective_from: 2026-01-01
effective_to:
supersedes: []
language: en
status: active
related_docs: [RUL-BOOK-01, RUL-CON-01]
---
## 1. Scope

This rule lists which identity documents are accepted for travel on
Ujjwal Rail, and when they must be shown.

## 2. Accepted ID proofs

At least one original (not a photocopy) of the following, bearing the
traveller's name and photograph, must be available on request during
the journey for any CNF or RAC traveller aged 18 or over:

- Passport
- Aadhaar card
- Voter ID card
- Driving licence
- PAN card (photo variant only)
- A photo ID card issued by a Central or State Government department

A valid student ID card is accepted only when combined with a
concession claim under RUL-CON-01.

## 3. Children

A traveller below 5 years of age does not need to show ID. A traveller
aged 5–17 may show either their own photo ID (where they hold one) or
a parent/guardian's ID travelling on the same booking.

## 4. Who must match the name on the ticket

The name shown must match `booking_travellers.traveller_name` for that
seat. ID does not need to be shown at the time of booking; it is
checked on board by Ujjwal Rail staff.

## 5. Waitlisted tickets

ID is not required for a waitlisted ticket, since a waitlisted
traveller does not board.

## 6. Privacy note

The assistant never asks for or stores a full ID number. Ujjwal Rail's
own passenger records hold only the last 4 digits of a phone number
for contact purposes (`phone_last4`); no ID number is stored in the
booking system at all.
