-- Ujjwal Rail database. Table and column names follow the brief (Section 4.2).
-- Extra columns we added: settings.effective_from, actions.params.

CREATE TABLE stations (
    station_code TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    other_names  TEXT,              -- comma separated, e.g. 'Bombay,CST'
    city         TEXT
);

CREATE TABLE trains (
    train_no TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    runs_on  TEXT NOT NULL,         -- 'Daily' or 'Mon,Wed,Fri'
    classes  TEXT NOT NULL          -- 'SL,3AC,2AC'
);

CREATE TABLE train_stops (
    train_no     TEXT NOT NULL,
    station_code TEXT NOT NULL,
    stop_order   INTEGER NOT NULL,
    arrival      TEXT,              -- 'HH:MM', empty at the first stop
    departure    TEXT,              -- 'HH:MM', empty at the last stop
    day_offset   INTEGER NOT NULL DEFAULT 0   -- days after the train left its first station
);

CREATE TABLE fares (
    train_no  TEXT NOT NULL,
    class     TEXT NOT NULL,
    from_code TEXT NOT NULL,
    to_code   TEXT NOT NULL,
    fare      INTEGER NOT NULL      -- whole rupees
);

CREATE TABLE seats (
    train_no     TEXT NOT NULL,
    journey_date TEXT NOT NULL,     -- 'YYYY-MM-DD', the day the train leaves its first station
    class        TEXT NOT NULL,
    available    INTEGER NOT NULL,
    rac          INTEGER NOT NULL,
    waitlist     INTEGER NOT NULL
);

CREATE TABLE passengers (
    passenger_id       TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    phone_last4        TEXT,
    preferred_language TEXT
);

CREATE TABLE bookings (
    booking_id   TEXT PRIMARY KEY,
    passenger_id TEXT NOT NULL,
    train_no     TEXT NOT NULL,
    journey_date TEXT NOT NULL,     -- same meaning as seats.journey_date
    from_code    TEXT NOT NULL,
    to_code      TEXT NOT NULL,
    class        TEXT NOT NULL,
    amount_paid  INTEGER NOT NULL,
    status       TEXT NOT NULL,     -- CNF, RAC, WL, CANCELLED, TRAIN_CANCELLED
    booked_at    TEXT NOT NULL
);

CREATE TABLE booking_travellers (
    booking_id     TEXT NOT NULL,
    traveller_name TEXT NOT NULL,
    age            INTEGER,
    status         TEXT NOT NULL,   -- CNF, RAC or WL
    coach          TEXT,
    berth          TEXT
);

CREATE TABLE actions (
    action_id    TEXT PRIMARY KEY,
    passenger_id TEXT NOT NULL,
    booking_id   TEXT,
    action_type  TEXT NOT NULL,     -- cancel_booking, book, change_boarding
    status       TEXT NOT NULL,     -- proposed, done, cancelled, expired
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    params       TEXT,              -- JSON: what the preview promised
    result       TEXT               -- JSON: what actually happened
);

CREATE TABLE settings (
    name           TEXT NOT NULL,
    value          REAL NOT NULL,
    source_doc     TEXT NOT NULL,
    effective_from TEXT NOT NULL    -- 'YYYY-MM-DD'; a circular adds a new row
);

CREATE TABLE handovers (
    ref          TEXT PRIMARY KEY,
    passenger_id TEXT NOT NULL,
    desk         TEXT NOT NULL,
    summary      TEXT NOT NULL,
    booking_id   TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE traces (
    trace_id TEXT PRIMARY KEY,
    data     TEXT NOT NULL          -- the whole trace as JSON
);
