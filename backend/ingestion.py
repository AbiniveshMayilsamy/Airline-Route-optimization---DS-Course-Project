"""
Background service: polls OpenSky Network every 15s,
writes live positions to live_flights table,
appends trail points to flight_history.
Runs as an asyncio task inside FastAPI lifespan.
"""
import asyncio, time, os
import httpx
import psycopg2
from psycopg2.extras import execute_values

DB = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/airline_opt")
OPENSKY_URL = "https://opensky-network.org/api/states/all"
POLL_INTERVAL = 15  # seconds

# In-memory snapshot for WebSocket broadcast
_snapshot: list = []
_snapshot_ts: float = 0


def get_snapshot():
    return _snapshot, _snapshot_ts


def _parse_states(states: list) -> list:
    flights = []
    for s in states:
        if s[5] is None or s[6] is None: continue
        if s[8]: continue  # on_ground
        flights.append({
            "icao24":      s[0],
            "callsign":    (s[1] or "").strip() or s[0],
            "country":     s[2] or "",
            "lon":         round(s[5], 4),
            "lat":         round(s[6], 4),
            "altitude":    round(s[7] or 0, 0),
            "altitude_ft": round((s[7] or 0) * 3.28084),
            "speed_ms":    round(s[9] or 0, 1),
            "speed_kmh":   round((s[9] or 0) * 3.6),
            "speed_kts":   round((s[9] or 0) * 1.944),
            "heading":     round(s[10] or 0),
            "vert_rate":   round(s[11] or 0, 1),
            "on_ground":   False,
        })
    # cap at 8000 — enough for global coverage, keeps WS payload ~1.5MB
    return flights[:8000]


async def _fetch() -> list:
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(OPENSKY_URL)
            if r.status_code == 200:
                return _parse_states(r.json().get("states") or [])
    except Exception:
        pass
    return []


def _write_to_db(flights: list):
    if not flights:
        return
    try:
        conn = psycopg2.connect(DB)
        cur  = conn.cursor()

        # Upsert live_flights
        rows = [(
            f["icao24"], f["callsign"], f["country"],
            f["lon"], f["lat"], f["altitude"],
            False, f["speed_ms"], f["heading"], f["vert_rate"],
            f"POINT({f['lon']} {f['lat']})"
        ) for f in flights]

        execute_values(cur, """
            INSERT INTO live_flights
              (icao24, callsign, origin_country, lon, lat, altitude_m,
               on_ground, speed_ms, heading, vert_rate, geom)
            VALUES %s
            ON CONFLICT (icao24) DO UPDATE SET
              callsign=EXCLUDED.callsign, lon=EXCLUDED.lon, lat=EXCLUDED.lat,
              altitude_m=EXCLUDED.altitude_m, speed_ms=EXCLUDED.speed_ms,
              heading=EXCLUDED.heading, vert_rate=EXCLUDED.vert_rate,
              geom=ST_GeogFromText('POINT(' || EXCLUDED.lon || ' ' || EXCLUDED.lat || ')'),
              last_seen=NOW()
        """, rows)

        # Append trail points (sample 1 in 3 to keep table manageable)
        trail_rows = [(f["icao24"], f["lat"], f["lon"], f["altitude"], f["heading"], f["speed_ms"])
                      for i, f in enumerate(flights) if i % 3 == 0]
        if trail_rows:
            execute_values(cur, """
                INSERT INTO flight_history (icao24, lat, lon, altitude_m, heading, speed_ms)
                VALUES %s
            """, trail_rows)

        # Prune old trail points (keep last 2 hours)
        cur.execute("DELETE FROM flight_history WHERE ts < NOW() - INTERVAL '2 hours'")

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[ingestion] DB write error: {e}")


async def run_ingestion():
    """Main ingestion loop — runs forever as asyncio task."""
    global _snapshot, _snapshot_ts
    print("[ingestion] Starting OpenSky poller...")
    while True:
        flights = await _fetch()
        if flights:
            _snapshot    = flights
            _snapshot_ts = time.time()
            # Write to DB in thread pool to not block event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _write_to_db, flights)
            print(f"[ingestion] {len(flights)} flights @ {time.strftime('%H:%M:%S')}")
        await asyncio.sleep(POLL_INTERVAL)
