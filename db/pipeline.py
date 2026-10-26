"""
Full data pipeline:
  1. OurAirports.com  — 85,000+ airports worldwide (real coordinates, type, elevation)
  2. OpenFlights      — 67,000+ routes between airports
  3. Compute PostGIS distances for all routes
  4. Derive demand/fare from distance + airport size + continent
  5. Seed airspace constraints + wind corridors
  6. Run ANOVA to identify significant demand features
"""
import csv, io, urllib.request, os, sys, time
import psycopg2
import numpy as np

DB = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/airline_opt")

OURAIRPORTS_URL  = "https://ourairports.com/data/airports.csv"
OF_AIRPORTS_URL  = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
OF_ROUTES_URL    = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat"

# Airport size weights for demand modelling
SIZE_WEIGHT = {"large_airport": 1.8, "medium_airport": 1.2, "small_airport": 0.7,
               "heliport": 0.2, "seaplane_base": 0.3, "closed": 0.0}

CONTINENT_MULTIPLIER = {
    "EU": 1.3, "NA": 1.4, "AS": 1.5, "OC": 0.9, "SA": 0.8, "AF": 0.6, "AN": 0.3
}

AIRSPACE_CONSTRAINTS = [
    {"name": "Pakistan Airspace",
     "reason": "India-Pakistan tensions — Air India DEL/BOM/MAA/BLR/COK/CJB reroute via Gulf",
     "active": True, "wkt": "POLYGON((60 23,77 23,77 37,60 37,60 23))"},
    {"name": "Russian Airspace",
     "reason": "Ukraine conflict — EU/US carriers banned from Siberian overflights",
     "active": True, "wkt": "POLYGON((20 50,180 50,180 82,20 82,20 50))"},
    {"name": "Yemeni/Red Sea Corridor",
     "reason": "Houthi conflict — carriers avoiding Red Sea",
     "active": True, "wkt": "POLYGON((32 10,55 10,55 25,32 25,32 10))"},
    {"name": "Libyan Airspace",
     "reason": "Civil conflict — ICAO advisory",
     "active": True, "wkt": "POLYGON((9 19,25 19,25 33,9 33,9 19))"},
    {"name": "Iranian Airspace",
     "reason": "Regional tensions — some carriers avoiding",
     "active": False, "wkt": "POLYGON((44 25,63 25,63 40,44 40,44 25))"},
]

WIND_CORRIDORS = [
    {"name": "North Atlantic Jet Stream — Eastbound Winter",
     "direction": "eastbound", "season": "winter", "tailwind_factor": 0.82,
     "wkt": "POLYGON((-70 45,-10 45,-10 62,-70 62,-70 45))"},
    {"name": "North Atlantic Jet Stream — Westbound Winter",
     "direction": "westbound", "season": "winter", "tailwind_factor": 1.18,
     "wkt": "POLYGON((-70 45,-10 45,-10 62,-70 62,-70 45))"},
    {"name": "North Atlantic — Eastbound Summer",
     "direction": "eastbound", "season": "summer", "tailwind_factor": 0.93,
     "wkt": "POLYGON((-70 40,-10 40,-10 58,-70 58,-70 40))"},
    {"name": "North Atlantic — Westbound Summer",
     "direction": "westbound", "season": "summer", "tailwind_factor": 1.07,
     "wkt": "POLYGON((-70 40,-10 40,-10 58,-70 58,-70 40))"},
    {"name": "South Atlantic Trade Winds",
     "direction": "northbound", "season": "all", "tailwind_factor": 0.95,
     "wkt": "POLYGON((-50 -35,15 -35,15 5,-50 5,-50 -35))"},
    {"name": "Indian Ocean Monsoon — Eastbound Summer",
     "direction": "eastbound", "season": "summer", "tailwind_factor": 0.91,
     "wkt": "POLYGON((40 -10,100 -10,100 25,40 25,40 -10))"},
    {"name": "Pacific Jet Stream — Eastbound Winter",
     "direction": "eastbound", "season": "winter", "tailwind_factor": 0.85,
     "wkt": "POLYGON((120 30,240 30,240 55,120 55,120 30))"},
]


def connect():
    return psycopg2.connect(DB)


def download(url: str, label: str) -> str:
    print(f"  Downloading {label}...", end=" ", flush=True)
    t = time.time()
    data = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", errors="replace")
    print(f"{len(data)//1024}KB in {time.time()-t:.1f}s")
    return data


def seed_airports_ourairports(cur):
    """Load all 85k airports from OurAirports — best free source."""
    print("\n[1/6] Seeding airports from OurAirports.com...")
    data = download(OURAIRPORTS_URL, "OurAirports airports.csv")
    reader = csv.DictReader(io.StringIO(data))
    count = 0
    for row in reader:
        iata = (row.get("iata_code") or "").strip()
        if not iata or len(iata) != 3:
            continue
        try:
            lat = float(row["latitude_deg"])
            lon = float(row["longitude_deg"])
        except (ValueError, KeyError):
            continue
        airport_type = row.get("type", "small_airport")
        if airport_type == "closed":
            continue
        cur.execute("""
            INSERT INTO airports (iata, name, city, country, lat, lon,
                                  type, elevation_ft, continent, scheduled_service)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (iata) DO UPDATE SET
                name=EXCLUDED.name, city=EXCLUDED.city, country=EXCLUDED.country,
                lat=EXCLUDED.lat, lon=EXCLUDED.lon, type=EXCLUDED.type,
                elevation_ft=EXCLUDED.elevation_ft, continent=EXCLUDED.continent,
                scheduled_service=EXCLUDED.scheduled_service
        """, (
            iata,
            row.get("name", "")[:200],
            row.get("municipality", "")[:100],
            row.get("iso_country", "")[:50],
            lat, lon,
            airport_type,
            int(float(row["elevation_ft"])) if row.get("elevation_ft") else None,
            row.get("continent", ""),
            row.get("scheduled_service", "no").lower() == "yes"
        ))
        count += 1
    print(f"  → {count} airports with IATA codes loaded")


def seed_routes_openflights(cur):
    """Load all 67k routes from OpenFlights."""
    print("\n[2/6] Seeding routes from OpenFlights...")
    data = download(OF_ROUTES_URL, "OpenFlights routes.dat")
    reader = csv.reader(io.StringIO(data))
    inserted = 0
    for row in reader:
        if len(row) < 5:
            continue
        origin = row[2].strip()
        dest   = row[4].strip()
        if len(origin) != 3 or len(dest) != 3:
            continue
        cur.execute("""
            INSERT INTO routes (origin, destination)
            SELECT %s, %s
            WHERE EXISTS (SELECT 1 FROM airports WHERE iata=%s)
              AND EXISTS (SELECT 1 FROM airports WHERE iata=%s)
            ON CONFLICT DO NOTHING
        """, (origin, dest, origin, dest))
        inserted += 1
    print(f"  → {inserted} route pairs processed")


def compute_distances(cur):
    """PostGIS great-circle distances for all routes missing distance."""
    print("\n[3/6] Computing PostGIS distances...")
    cur.execute("""
        UPDATE routes r
        SET distance_km = ST_Distance(a1.geom, a2.geom) / 1000.0
        FROM airports a1, airports a2
        WHERE a1.iata = r.origin AND a2.iata = r.destination
          AND r.distance_km IS NULL
    """)
    cur.execute("SELECT COUNT(*) FROM routes WHERE distance_km IS NOT NULL")
    n = cur.fetchone()[0]
    print(f"  → {n} routes have distances")


def compute_demand_fare(cur):
    print("\n[4/6] Computing demand & fare (distance + airport size + continent)...")
    cur.execute("""
        UPDATE routes r
        SET
          base_demand = GREATEST(10, (
            CASE
              WHEN r.distance_km < 1500  THEN 140
              WHEN r.distance_km < 3000  THEN 120
              WHEN r.distance_km < 6000  THEN 100
              WHEN r.distance_km < 10000 THEN 85
              ELSE 70
            END
            * CASE a1.type
                WHEN 'large_airport'  THEN 1.8
                WHEN 'medium_airport' THEN 1.2
                ELSE 0.7
              END
            * CASE a1.continent
                WHEN 'NA' THEN 1.4 WHEN 'EU' THEN 1.3 WHEN 'AS' THEN 1.5
                WHEN 'OC' THEN 0.9 WHEN 'SA' THEN 0.8 WHEN 'AF' THEN 0.6
                ELSE 1.0
              END
            * CASE WHEN COALESCE(a1.elevation_ft,0) > 8000 THEN 0.8 ELSE 1.0 END
          )::int,
          base_fare_usd = CASE
            WHEN r.distance_km < 1500  THEN 60  + r.distance_km * 0.07
            WHEN r.distance_km < 3000  THEN 100 + r.distance_km * 0.06
            WHEN r.distance_km < 6000  THEN 180 + r.distance_km * 0.05
            WHEN r.distance_km < 10000 THEN 280 + r.distance_km * 0.04
            ELSE                            400 + r.distance_km * 0.035
          END
        FROM airports a1, airports a2
        WHERE a1.iata = r.origin
          AND a2.iata = r.destination
          AND r.distance_km IS NOT NULL
          AND r.base_demand IS NULL
    """)
    cur.execute("SELECT COUNT(*) FROM routes WHERE base_demand IS NOT NULL")
    n = cur.fetchone()[0]
    print(f"  → {n} routes have demand/fare")


def seed_airspace_constraints(cur):
    print("\n[5/6] Seeding airspace constraints...")
    for c in AIRSPACE_CONSTRAINTS:
        cur.execute("""
            INSERT INTO airspace_constraints (name, reason, active, zone)
            VALUES (%s,%s,%s,ST_GeogFromText(%s))
            ON CONFLICT DO NOTHING
        """, (c["name"], c["reason"], c["active"], c["wkt"]))
    print(f"  → {len(AIRSPACE_CONSTRAINTS)} constraints")


def seed_wind_corridors(cur):
    print("\n[6/6] Seeding wind corridors...")
    for w in WIND_CORRIDORS:
        cur.execute("""
            INSERT INTO wind_corridors (name, direction, season, tailwind_factor, corridor)
            VALUES (%s,%s,%s,%s,ST_GeogFromText(%s))
            ON CONFLICT DO NOTHING
        """, (w["name"], w["direction"], w["season"], w["tailwind_factor"], w["wkt"]))
    print(f"  → {len(WIND_CORRIDORS)} wind corridors")


if __name__ == "__main__":
    print("=" * 60)
    print("Airline Route Optimization — Full Data Pipeline")
    print("=" * 60)
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()
    try:
        seed_airports_ourairports(cur)
        conn.commit()
        seed_routes_openflights(cur)
        conn.commit()
        compute_distances(cur)
        conn.commit()
        compute_demand_fare(cur)
        conn.commit()
        seed_airspace_constraints(cur)
        seed_wind_corridors(cur)
        conn.commit()
        print("\n✓ Pipeline complete.")
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()
