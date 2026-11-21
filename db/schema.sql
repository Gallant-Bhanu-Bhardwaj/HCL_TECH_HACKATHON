-- Ujjwal Rail — canonical SQLite schema (docs/architecture.md §6, §9/§10;
-- docs/api-contracts.md §9, §10). SHARED-FROZEN (architecture §8).
--
-- Mandatory tables/columns are exactly the guide's §4.2 names; every
-- addition here is called out as "additive" and was approved in
-- docs/architecture.md §3.1/§3.2 (D2, D4, D6, O4).
--
-- NOTE: PRAGMA foreign_keys=ON is a per-connection setting in SQLite —
-- it is set here for whatever client runs this script, but the real
-- application's db layer (app/db/, Phase 1) MUST also set it on every
-- connection it opens; this file alone cannot make it durable.
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Domain tables (guide §4.2)
-- ---------------------------------------------------------------------

CREATE TABLE stations (
    station_code   TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    other_names     TEXT,              -- e.g. comma/JSON list of aliases ("Bombay", "CST")
    city            TEXT NOT NULL
);

CREATE TABLE trains (
    train_no        TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    runs_on         TEXT NOT NULL,      -- days of the week, e.g. "MON,WED,FRI"
    classes         TEXT NOT NULL       -- e.g. "SL,3AC,2AC"
);

CREATE TABLE train_stops (
    train_no        TEXT NOT NULL REFERENCES trains(train_no),
    station_code    TEXT NOT NULL REFERENCES stations(station_code),
    stop_order      INTEGER NOT NULL,
    arrival         TEXT,               -- "HH:MM"; NULL at the origin stop
    departure       TEXT,               -- "HH:MM"; NULL at the terminus stop
    day_offset      INTEGER NOT NULL DEFAULT 0,  -- days after origin departure (after-midnight trains)
    PRIMARY KEY (train_no, stop_order)
);

CREATE TABLE fares (
    train_no        TEXT NOT NULL REFERENCES trains(train_no),
    class           TEXT NOT NULL,
    from_code       TEXT NOT NULL REFERENCES stations(station_code),
    to_code         TEXT NOT NULL REFERENCES stations(station_code),
    fare            INTEGER NOT NULL,   -- INR, integer (api-contracts §2)
    PRIMARY KEY (train_no, class, from_code, to_code)
);

CREATE TABLE seats (
    train_no        TEXT NOT NULL REFERENCES trains(train_no),
    journey_date    TEXT NOT NULL,      -- "YYYY-MM-DD"
    class           TEXT NOT NULL,
    available       INTEGER NOT NULL,
    rac             INTEGER NOT NULL,
    waitlist        INTEGER NOT NULL,
    capacity        INTEGER NOT NULL,       -- additive (O4): total CNF seats in this class
    rac_capacity    INTEGER NOT NULL DEFAULT 0,  -- additive (O4)
    PRIMARY KEY (train_no, journey_date, class),
    CHECK (available >= 0 AND available <= capacity),
    CHECK (rac >= 0 AND rac <= rac_capacity),
    CHECK (waitlist >= 0)
);

CREATE TABLE passengers (
    passenger_id        TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    phone_last4         TEXT,           -- never the full number (R8/§12 masking)
    preferred_language  TEXT NOT NULL DEFAULT 'en' CHECK (preferred_language IN ('en', 'hi', 'hinglish'))
);

CREATE TABLE bookings (
    booking_id      TEXT PRIMARY KEY,
    passenger_id    TEXT NOT NULL REFERENCES passengers(passenger_id),
    train_no        TEXT NOT NULL REFERENCES trains(train_no),
    journey_date    TEXT NOT NULL,
    from_code       TEXT NOT NULL REFERENCES stations(station_code),
    to_code         TEXT NOT NULL REFERENCES stations(station_code),
    class           TEXT NOT NULL,
    amount_paid     INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (
                        status IN ('confirmed', 'rac', 'waitlisted', 'cancelled', 'train_cancelled_by_operator')
                    ),
    booked_at       TEXT NOT NULL
);
CREATE INDEX idx_bookings_passenger ON bookings(passenger_id);

CREATE TABLE booking_travellers (
    booking_id      TEXT NOT NULL REFERENCES bookings(booking_id),
    traveller_name  TEXT NOT NULL,
    age             INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('CNF', 'RAC', 'WL')),
    coach           TEXT,
    berth           TEXT,
    PRIMARY KEY (booking_id, traveller_name)
);

CREATE TABLE actions (
    action_id       TEXT PRIMARY KEY,
    passenger_id    TEXT NOT NULL REFERENCES passengers(passenger_id),
    booking_id      TEXT REFERENCES bookings(booking_id),  -- NULL for a new booking proposal
    action_type     TEXT NOT NULL CHECK (action_type IN ('book_ticket', 'cancel_booking', 'change_boarding_station')),
    status          TEXT NOT NULL CHECK (status IN ('proposed', 'executing', 'done', 'failed', 'cancelled', 'expired')),
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL,      -- real UTC timestamp, OPERATIONAL clock (D6, v1.2)
    result          TEXT,               -- JSON; NULL until done/failed
    as_of           TEXT NOT NULL,      -- additive, required (D6): BUSINESS clock saved at proposal
    params_json     TEXT,               -- additive: propose_* arguments
    preview_json    TEXT,               -- additive: the previewed amounts shown to the passenger
    trace_id        TEXT                -- additive: the trace that created this action
);
CREATE INDEX idx_actions_passenger ON actions(passenger_id);

-- ---------------------------------------------------------------------
-- Settings (guide §4.2 + D2/D4 additive columns)
-- ---------------------------------------------------------------------

CREATE TABLE settings (
    name            TEXT NOT NULL,
    value           REAL NOT NULL,      -- INR/hours/minutes as integers in practice; REAL also covers refund_pct_*
    source_doc      TEXT NOT NULL,
    effective_from  TEXT NOT NULL,      -- additive (D2/D4)
    effective_to    TEXT,               -- additive; NULL = open-ended
    unit            TEXT,               -- additive: "INR" | "hours" | "minutes" | "%" | ... ; also carries a
                                         -- boundary-convention override note when a key deviates from D4
    PRIMARY KEY (name, effective_from)
);

-- Append-only settings audit trail (D2, v1.2). No application code may
-- UPDATE or DELETE a row here — enforced below with triggers, not just
-- convention, since this is the audit evidence for a disqualifying
-- condition (guide §10: "made-up results" / unaudited changes).
CREATE TABLE settings_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    old_value       REAL,
    new_value       REAL NOT NULL,
    effective_from  TEXT NOT NULL,
    source_doc      TEXT NOT NULL,
    changed_at      TEXT NOT NULL,
    trace_id        TEXT,
    changed_by      TEXT NOT NULL DEFAULT 'ingest'
);

CREATE TRIGGER trg_settings_history_no_update
BEFORE UPDATE ON settings_history
BEGIN
    SELECT RAISE(ABORT, 'settings_history is append-only: UPDATE is not allowed');
END;

CREATE TRIGGER trg_settings_history_no_delete
BEFORE DELETE ON settings_history
BEGIN
    SELECT RAISE(ABORT, 'settings_history is append-only: DELETE is not allowed');
END;

-- ---------------------------------------------------------------------
-- RAG: documents, chunks, FTS5 index, vectors (architecture §5.2) [RAG]
-- ---------------------------------------------------------------------

CREATE TABLE documents (
    doc_id          TEXT PRIMARY KEY,
    doc_type        TEXT NOT NULL CHECK (doc_type IN ('rule', 'circular', 'faq')),
    title           TEXT NOT NULL,
    effective_from  TEXT NOT NULL,
    effective_to    TEXT,
    supersedes_json TEXT,               -- JSON list of doc_ids
    language        TEXT NOT NULL CHECK (language IN ('en', 'hi', 'hinglish')),
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'withdrawn'))
);

CREATE TABLE chunks (
    id              INTEGER PRIMARY KEY,   -- FTS5 external-content rowid
    chunk_id        TEXT UNIQUE NOT NULL,
    doc_id          TEXT NOT NULL REFERENCES documents(doc_id),
    section         TEXT NOT NULL,
    text            TEXT NOT NULL,
    language        TEXT NOT NULL CHECK (language IN ('en', 'hi', 'hinglish'))
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    text, section,
    content='chunks', content_rowid='id'
);

CREATE TRIGGER trg_chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text, section) VALUES (new.id, new.text, new.section);
END;
CREATE TRIGGER trg_chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, section) VALUES ('delete', old.id, old.text, old.section);
END;
CREATE TRIGGER trg_chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, section) VALUES ('delete', old.id, old.text, old.section);
    INSERT INTO chunks_fts(rowid, text, section) VALUES (new.id, new.text, new.section);
END;

CREATE TABLE chunk_vectors (
    chunk_id        TEXT PRIMARY KEY REFERENCES chunks(chunk_id),
    embedding       BLOB NOT NULL,      -- packed floats; dim implied by EMBED_MODEL (app/config.py)
    dim             INTEGER NOT NULL
);

-- ---------------------------------------------------------------------
-- Audit, sessions, hand-overs (api-contracts §11; R7; §8 SessionStore)
-- ---------------------------------------------------------------------

CREATE TABLE traces (
    trace_id        TEXT PRIMARY KEY,
    passenger_id    TEXT,               -- 'system' for /ingest (O8); otherwise a real passenger
    endpoint        TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    record_json     TEXT NOT NULL       -- the full TraceRecord (api-contracts §11), JSON-encoded
);

CREATE TABLE sessions (
    session_id      TEXT PRIMARY KEY,
    passenger_id    TEXT NOT NULL REFERENCES passengers(passenger_id),
    state_json      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE handoffs (
    handoff_id      TEXT PRIMARY KEY,
    passenger_id    TEXT NOT NULL REFERENCES passengers(passenger_id),
    desk            TEXT NOT NULL CHECK (desk IN ('complaints', 'refunds', 'safety', 'concessions', 'general')),
    summary         TEXT NOT NULL,
    booking_id      TEXT REFERENCES bookings(booking_id),
    session_id      TEXT,
    created_at      TEXT NOT NULL
);
