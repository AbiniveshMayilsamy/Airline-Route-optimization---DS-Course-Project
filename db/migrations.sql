-- Drop and recreate for clean slate
DROP TABLE IF EXISTS live_flights CASCADE;
DROP TABLE IF EXISTS flight_history CASCADE;
DROP TABLE IF EXISTS model_metrics CASCADE;

-- Live flight snapshot (refreshed every 15s from OpenSky)
CREATE TABLE IF NOT EXISTS live_flights (
    icao24          TEXT PRIMARY KEY,
    callsign        TEXT,
    origin_country  TEXT,
    lon             DOUBLE PRECISION,
    lat             DOUBLE PRECISION,
    altitude_m      DOUBLE PRECISION,
    on_ground       BOOLEAN DEFAULT FALSE,
    speed_ms        DOUBLE PRECISION,
    heading         DOUBLE PRECISION,
    vert_rate       DOUBLE PRECISION,
    last_seen       TIMESTAMPTZ DEFAULT NOW(),
    geom            GEOGRAPHY(Point,4326)
);

-- Historical flight snapshots for trail rendering
CREATE TABLE IF NOT EXISTS flight_history (
    id          BIGSERIAL PRIMARY KEY,
    icao24      TEXT,
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION,
    altitude_m  DOUBLE PRECISION,
    heading     DOUBLE PRECISION,
    speed_ms    DOUBLE PRECISION,
    ts          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fh_icao ON flight_history(icao24, ts DESC);

-- ML model training metrics
CREATE TABLE IF NOT EXISTS model_metrics (
    id          SERIAL PRIMARY KEY,
    model_name  TEXT,
    metric_name TEXT,
    value       DOUBLE PRECISION,
    epoch       INTEGER,
    trained_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Extend airports table with OurAirports fields if not present
ALTER TABLE airports ADD COLUMN IF NOT EXISTS type        TEXT;
ALTER TABLE airports ADD COLUMN IF NOT EXISTS elevation_ft INTEGER;
ALTER TABLE airports ADD COLUMN IF NOT EXISTS continent   TEXT;
ALTER TABLE airports ADD COLUMN IF NOT EXISTS wikipedia   TEXT;
ALTER TABLE airports ADD COLUMN IF NOT EXISTS scheduled_service BOOLEAN DEFAULT FALSE;
