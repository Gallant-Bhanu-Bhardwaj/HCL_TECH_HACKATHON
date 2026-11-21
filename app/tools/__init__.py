"""Deterministic tools, SQLite-backed. No LLM calls anywhere here. [Backend]

Implemented (real, DB-backed): stations.resolve_station,
timetable.search_trains, availability.check_availability,
fares.get_fare, refund.refund_quote.

Not yet implemented: deadlines (can_cancel), booking_status
(get_booking_status, list_my_bookings) — out of scope for this task;
the live app still uses tests/fakes/tool_registry.py for those (and,
for now, for everything, since this module isn't wired into
app.main.py yet — see docs/architecture.md and the task notes on why).
"""
