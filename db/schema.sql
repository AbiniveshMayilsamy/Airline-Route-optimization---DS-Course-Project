-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE airports (
    iata        CHAR(3) PRIMARY KEY,
    name        TEXT NOT NULL,
    city        TEXT,
    country     TEXT,
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    geom        GEOGRAPHY(Point, 4326) GENERATED ALWAYS AS (ST_MakePoint(lon, lat)::geography) STORED
);

CREATE TABLE routes (
    id              SERIAL PRIMARY KEY,
    origin          CHAR(3) REFERENCES airports(iata),
    destination     CHAR(3) REFERENCES airports(iata),
    distance_km     DOUBLE PRECISION,
    base_demand     INTEGER,
    base_fare_usd   DOUBLE PRECISION
);

-- Airspace constraints: closed/restricted zones that force detours
-- e.g. Pakistan airspace (for Air India), Russian airspace, conflict zones
CREATE TABLE airspace_constraints (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,           -- e.g. 'Pakistan Airspace', 'Russian Airspace'
    reason      TEXT,                    -- e.g. 'Middle East Crisis', 'Sanctions'
    active      BOOLEAN DEFAULT TRUE,
    zone        GEOGRAPHY(Polygon, 4326) NOT NULL
);

-- Wind corridors: jet streams affecting transatlantic fuel burn
-- positive tailwind_factor = fuel saving, negative = headwind penalty
CREATE TABLE wind_corridors (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,      -- e.g. 'North Atlantic Jet Stream Westbound'
    direction           TEXT,               -- 'westbound' | 'eastbound'
    season              TEXT,               -- 'winter' | 'summer' | 'all'
    tailwind_factor     DOUBLE PRECISION,   -- multiplier on fuel burn: 0.85 = 15% saving
    corridor            GEOGRAPHY(Polygon, 4326)
);

CREATE TABLE predictions (
    id              SERIAL PRIMARY KEY,
    route_id        INTEGER REFERENCES routes(id),
    predicted_demand INTEGER,
    predicted_fare  DOUBLE PRECISION,
    model_version   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE optimized_routes (
    id                  SERIAL PRIMARY KEY,
    route_id            INTEGER REFERENCES routes(id),
    frequency_per_week  INTEGER,
    profit_usd          DOUBLE PRECISION,
    fuel_cost_usd       DOUBLE PRECISION,
    detour_km           DOUBLE PRECISION DEFAULT 0,   -- extra km due to airspace avoidance
    wind_saving_usd     DOUBLE PRECISION DEFAULT 0,   -- fuel saving from tailwind
    active_constraints  TEXT[],                       -- which airspace constraints applied
    run_at              TIMESTAMPTZ DEFAULT NOW()
);

-- Live flight data tables
CREATE TABLE live_flights (
    icao24          CHAR(6) PRIMARY KEY,
    callsign        TEXT,
    origin_country  TEXT,
    lon             DOUBLE PRECISION,
    lat             DOUBLE PRECISION,
    altitude_m      DOUBLE PRECISION,
    on_ground       BOOLEAN,
    speed_ms        DOUBLE PRECISION,
    heading         INTEGER,
    vert_rate       DOUBLE PRECISION,
    geom            GEOGRAPHY(POINT, 4326) GENERATED ALWAYS AS (ST_MakePoint(lon, lat)::geography) STORED,
    last_seen       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE flight_history (
    id          SERIAL PRIMARY KEY,
    icao24      CHAR(6) REFERENCES live_flights(icao24),
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION,
    altitude_m  DOUBLE PRECISION,
    heading     INTEGER,
    speed_ms    DOUBLE PRECISION,
    ts          TIMESTAMPTZ DEFAULT NOW()
);
