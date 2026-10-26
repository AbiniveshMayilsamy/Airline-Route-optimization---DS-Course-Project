"""
Seed script: loads OpenFlights airports + routes into PostgreSQL.
Also seeds airspace constraints (Pakistan, Russia) and wind corridors (North Atlantic jet stream).
"""
import csv, io, urllib.request, json, psycopg2, os

DB = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/airline_opt")

AIRPORTS_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
ROUTES_URL   = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat"

# Airspace constraint polygons (simplified bounding boxes)
AIRSPACE_CONSTRAINTS = [
    {
        "name": "Pakistan Airspace",
        "reason": "India-Pakistan tensions / Middle East crisis detour for Air India",
        "active": True,
        # Rough bounding box over Pakistan airspace
        "wkt": "POLYGON((60 23, 77 23, 77 37, 60 37, 60 23))"
    },
    {
        "name": "Russian Airspace",
        "reason": "Ukraine conflict sanctions — EU/US carriers banned",
        "active": True,
        "wkt": "POLYGON((20 50, 180 50, 180 82, 20 82, 20 50))"
    },
    {
        "name": "Yemeni/Red Sea Corridor",
        "reason": "Houthi conflict — carriers avoiding Red Sea overflights",
        "active": True,
        "wkt": "POLYGON((32 10, 55 10, 55 25, 32 25, 32 10))"
    }
]

# North Atlantic jet stream corridors (simplified)
WIND_CORRIDORS = [
    {
        "name": "North Atlantic Jet Stream — Eastbound (tailwind)",
        "direction": "eastbound",
        "season": "winter",
        "tailwind_factor": 0.82,   # 18% fuel saving westbound jet stream helps eastbound
        "wkt": "POLYGON((-70 45, -10 45, -10 60, -70 60, -70 45))"
    },
    {
        "name": "North Atlantic Jet Stream — Westbound (headwind)",
        "direction": "westbound",
        "season": "winter",
        "tailwind_factor": 1.18,   # 18% more fuel burn flying into jet stream
        "wkt": "POLYGON((-70 45, -10 45, -10 60, -70 60, -70 45))"
    },
    {
        "name": "North Atlantic Summer Track — Eastbound",
        "direction": "eastbound",
        "season": "summer",
        "tailwind_factor": 0.93,
        "wkt": "POLYGON((-70 40, -10 40, -10 55, -70 55, -70 40))"
    },
    {
        "name": "North Atlantic Summer Track — Westbound",
        "direction": "westbound",
        "season": "summer",
        "tailwind_factor": 1.07,
        "wkt": "POLYGON((-70 40, -10 40, -10 55, -70 55, -70 40))"
    },
    {
        "name": "South Atlantic Trade Winds — Northbound",
        "direction": "northbound",
        "season": "all",
        "tailwind_factor": 0.95,
        "wkt": "POLYGON((-50 -35, 15 -35, 15 5, -50 5, -50 -35))"
    }
]

def connect():
    return psycopg2.connect(DB)

def seed_airports(cur):
    print("Seeding airports...")
    data = urllib.request.urlopen(AIRPORTS_URL).read().decode("utf-8")
    reader = csv.reader(io.StringIO(data))
    count = 0
    for row in reader:
        # OpenFlights format: id,name,city,country,iata,icao,lat,lon,alt,tz,...
        if len(row) < 8: continue
        iata = row[4].strip().strip('"')
        if not iata or iata == r'\N' or len(iata) != 3: continue
        try:
            lat, lon = float(row[6]), float(row[7])
        except ValueError:
            continue
        cur.execute("""
            INSERT INTO airports (iata, name, city, country, lat, lon)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (iata) DO NOTHING
        """, (iata, row[1], row[2], row[3], lat, lon))
        count += 1
    print(f"  {count} airports inserted")

def seed_routes(cur):
    print("Seeding routes...")
    data = urllib.request.urlopen(ROUTES_URL).read().decode("utf-8")
    reader = csv.reader(io.StringIO(data))
    count = 0
    for row in reader:
        if len(row) < 5: continue
        origin, dest = row[2].strip(), row[4].strip()
        if len(origin) != 3 or len(dest) != 3: continue
        cur.execute("""
            INSERT INTO routes (origin, destination)
            SELECT %s, %s
            WHERE EXISTS (SELECT 1 FROM airports WHERE iata=%s)
              AND EXISTS (SELECT 1 FROM airports WHERE iata=%s)
            ON CONFLICT DO NOTHING
        """, (origin, dest, origin, dest))
        count += 1

    # Compute distances using PostGIS
    cur.execute("""
        UPDATE routes r
        SET distance_km = ST_Distance(a1.geom, a2.geom) / 1000.0
        FROM airports a1, airports a2
        WHERE a1.iata = r.origin AND a2.iata = r.destination
          AND r.distance_km IS NULL
    """)

    # Populate demand & fare based on distance:
    # Short-haul (<2000km): high demand, low fare
    # Medium-haul (2000-6000km): medium demand, medium fare
    # Long-haul (>6000km): lower demand, high fare
    cur.execute("""
        UPDATE routes
        SET
            base_demand = CASE
                WHEN distance_km < 2000  THEN (120 + (distance_km / 2000.0 * 60))::int
                WHEN distance_km < 6000  THEN (100 + (distance_km / 6000.0 * 50))::int
                ELSE                          (80  + (distance_km / 15000.0 * 40))::int
            END,
            base_fare_usd = CASE
                WHEN distance_km < 2000  THEN 80  + distance_km * 0.06
                WHEN distance_km < 6000  THEN 150 + distance_km * 0.05
                ELSE                          300 + distance_km * 0.04
            END
        WHERE distance_km IS NOT NULL AND base_demand IS NULL
    """)
    print(f"  {count} routes inserted")

def seed_extra_airports_and_routes(cur):
    """
    Ensure key airports (CJB, major hubs) exist and have real international routes.
    Data sourced from OpenFlights route database cross-referenced with real schedules.
    """
    print("Seeding extra airports and international routes...")

    # Key airports with real coordinates — ensure they exist
    EXTRA_AIRPORTS = [
        # IATA, name, city, country, lat, lon
        ("CJB", "Coimbatore International Airport", "Coimbatore", "India", 11.0300, 77.0434),
        ("DEL", "Indira Gandhi International Airport", "Delhi", "India", 28.5665, 77.1031),
        ("BOM", "Chhatrapati Shivaji Maharaj International", "Mumbai", "India", 19.0896, 72.8656),
        ("MAA", "Chennai International Airport", "Chennai", "India", 12.9900, 80.1693),
        ("BLR", "Kempegowda International Airport", "Bangalore", "India", 13.1979, 77.7063),
        ("HYD", "Rajiv Gandhi International Airport", "Hyderabad", "India", 17.2313, 78.4298),
        ("COK", "Cochin International Airport", "Kochi", "India", 10.1520, 76.4019),
        ("LHR", "Heathrow Airport", "London", "United Kingdom", 51.4775, -0.4614),
        ("CDG", "Charles de Gaulle Airport", "Paris", "France", 49.0097, 2.5479),
        ("FRA", "Frankfurt Airport", "Frankfurt", "Germany", 50.0379, 8.5622),
        ("DXB", "Dubai International Airport", "Dubai", "United Arab Emirates", 25.2532, 55.3657),
        ("AUH", "Abu Dhabi International Airport", "Abu Dhabi", "United Arab Emirates", 24.4330, 54.6511),
        ("DOH", "Hamad International Airport", "Doha", "Qatar", 25.2731, 51.6080),
        ("KWI", "Kuwait International Airport", "Kuwait City", "Kuwait", 29.2267, 47.9689),
        ("BAH", "Bahrain International Airport", "Manama", "Bahrain", 26.2708, 50.6336),
        ("MCT", "Muscat International Airport", "Muscat", "Oman", 23.5933, 58.2844),
        ("SIN", "Singapore Changi Airport", "Singapore", "Singapore", 1.3644, 103.9915),
        ("KUL", "Kuala Lumpur International Airport", "Kuala Lumpur", "Malaysia", 2.7456, 101.7099),
        ("BKK", "Suvarnabhumi Airport", "Bangkok", "Thailand", 13.6811, 100.7472),
        ("CMB", "Bandaranaike International Airport", "Colombo", "Sri Lanka", 7.1808, 79.8841),
        ("JFK", "John F Kennedy International Airport", "New York", "United States", 40.6413, -73.7781),
        ("ORD", "O'Hare International Airport", "Chicago", "United States", 41.9742, -87.9073),
        ("LAX", "Los Angeles International Airport", "Los Angeles", "United States", 33.9425, -118.4081),
        ("YYZ", "Toronto Pearson International Airport", "Toronto", "Canada", 43.6777, -79.6248),
        ("SYD", "Sydney Kingsford Smith Airport", "Sydney", "Australia", -33.9399, 151.1753),
        ("MEL", "Melbourne Airport", "Melbourne", "Australia", -37.6690, 144.8410),
        ("NRT", "Narita International Airport", "Tokyo", "Japan", 35.7720, 140.3929),
        ("ICN", "Incheon International Airport", "Seoul", "South Korea", 37.4602, 126.4407),
        ("PEK", "Beijing Capital International Airport", "Beijing", "China", 40.0799, 116.6031),
        ("PVG", "Shanghai Pudong International Airport", "Shanghai", "China", 31.1443, 121.8083),
        ("HKG", "Hong Kong International Airport", "Hong Kong", "Hong Kong", 22.3080, 113.9185),
        ("GRU", "Guarulhos International Airport", "Sao Paulo", "Brazil", -23.4356, -46.4731),
        ("JNB", "O.R. Tambo International Airport", "Johannesburg", "South Africa", -26.1392, 28.2460),
        ("CAI", "Cairo International Airport", "Cairo", "Egypt", 30.1219, 31.4056),
        ("IST", "Istanbul Airport", "Istanbul", "Turkey", 41.2608, 28.7418),
        ("AMS", "Amsterdam Airport Schiphol", "Amsterdam", "Netherlands", 52.3086, 4.7639),
        ("ZRH", "Zurich Airport", "Zurich", "Switzerland", 47.4647, 8.5492),
        ("MUC", "Munich Airport", "Munich", "Germany", 48.3538, 11.7861),
        ("FCO", "Leonardo da Vinci International Airport", "Rome", "Italy", 41.8003, 12.2389),
        ("MAD", "Adolfo Suarez Madrid-Barajas Airport", "Madrid", "Spain", 40.4936, -3.5668),
    ]

    for iata, name, city, country, lat, lon in EXTRA_AIRPORTS:
        cur.execute("""
            INSERT INTO airports (iata, name, city, country, lat, lon)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (iata) DO UPDATE SET name=EXCLUDED.name, city=EXCLUDED.city,
                country=EXCLUDED.country, lat=EXCLUDED.lat, lon=EXCLUDED.lon
        """, (iata, name, city, country, lat, lon))

    # Real international routes — (origin, destination)
    # Sourced from OpenFlights + real airline schedules
    INTL_ROUTES = [
        # CJB international routes (Air India Express, IndiGo, Air Arabia)
        ("CJB", "DXB"), ("CJB", "AUH"), ("CJB", "DOH"), ("CJB", "KWI"),
        ("CJB", "BAH"), ("CJB", "MCT"), ("CJB", "SIN"), ("CJB", "KUL"),
        ("CJB", "CMB"),
        # DEL international
        ("DEL", "LHR"), ("DEL", "CDG"), ("DEL", "FRA"), ("DEL", "AMS"),
        ("DEL", "JFK"), ("DEL", "ORD"), ("DEL", "YYZ"),
        ("DEL", "DXB"), ("DEL", "DOH"), ("DEL", "AUH"),
        ("DEL", "SIN"), ("DEL", "BKK"), ("DEL", "KUL"),
        ("DEL", "NRT"), ("DEL", "ICN"), ("DEL", "PEK"),
        ("DEL", "IST"), ("DEL", "CAI"),
        # BOM international
        ("BOM", "LHR"), ("BOM", "CDG"), ("BOM", "FRA"),
        ("BOM", "JFK"), ("BOM", "LAX"),
        ("BOM", "DXB"), ("BOM", "DOH"), ("BOM", "AUH"), ("BOM", "KWI"),
        ("BOM", "SIN"), ("BOM", "BKK"), ("BOM", "HKG"),
        ("BOM", "NRT"), ("BOM", "SYD"),
        # MAA international
        ("MAA", "DXB"), ("MAA", "AUH"), ("MAA", "DOH"), ("MAA", "KWI"),
        ("MAA", "SIN"), ("MAA", "KUL"), ("MAA", "CMB"),
        ("MAA", "LHR"), ("MAA", "CDG"),
        # BLR international
        ("BLR", "DXB"), ("BLR", "AUH"), ("BLR", "DOH"), ("BLR", "SIN"),
        ("BLR", "LHR"), ("BLR", "FRA"), ("BLR", "JFK"),
        ("BLR", "KUL"), ("BLR", "BKK"),
        # COK international
        ("COK", "DXB"), ("COK", "AUH"), ("COK", "DOH"), ("COK", "KWI"),
        ("COK", "BAH"), ("COK", "MCT"), ("COK", "SIN"), ("COK", "CMB"),
        # Major hub interconnects
        ("LHR", "JFK"), ("LHR", "LAX"), ("LHR", "ORD"), ("LHR", "YYZ"),
        ("LHR", "DXB"), ("LHR", "SIN"), ("LHR", "HKG"), ("LHR", "NRT"),
        ("LHR", "SYD"), ("LHR", "GRU"), ("LHR", "JNB"),
        ("CDG", "JFK"), ("CDG", "LAX"), ("CDG", "DXB"), ("CDG", "SIN"),
        ("FRA", "JFK"), ("FRA", "LAX"), ("FRA", "DXB"), ("FRA", "SIN"),
        ("DXB", "JFK"), ("DXB", "LAX"), ("DXB", "SIN"), ("DXB", "SYD"),
        ("DXB", "LHR"), ("DXB", "CDG"), ("DXB", "FRA"),
        ("JFK", "LAX"), ("JFK", "SIN"), ("JFK", "NRT"), ("JFK", "HKG"),
        ("SIN", "SYD"), ("SIN", "NRT"), ("SIN", "HKG"), ("SIN", "ICN"),
        ("IST", "JFK"), ("IST", "LAX"), ("IST", "DXB"), ("IST", "SIN"),
    ]

    route_count = 0
    for origin, dest in INTL_ROUTES:
        # Insert both directions
        for o, d in [(origin, dest), (dest, origin)]:
            cur.execute("""
                INSERT INTO routes (origin, destination)
                SELECT %s, %s
                WHERE EXISTS (SELECT 1 FROM airports WHERE iata=%s)
                  AND EXISTS (SELECT 1 FROM airports WHERE iata=%s)
                ON CONFLICT DO NOTHING
            """, (o, d, o, d))
            route_count += 1

    # Recompute distances for new routes
    cur.execute("""
        UPDATE routes r
        SET distance_km = ST_Distance(a1.geom, a2.geom) / 1000.0
        FROM airports a1, airports a2
        WHERE a1.iata = r.origin AND a2.iata = r.destination
          AND r.distance_km IS NULL
    """)

    # Fill demand/fare for any new routes
    cur.execute("""
        UPDATE routes
        SET
            base_demand = CASE
                WHEN distance_km < 2000  THEN (120 + (distance_km / 2000.0 * 60))::int
                WHEN distance_km < 6000  THEN (100 + (distance_km / 6000.0 * 50))::int
                ELSE                          (80  + (distance_km / 15000.0 * 40))::int
            END,
            base_fare_usd = CASE
                WHEN distance_km < 2000  THEN 80  + distance_km * 0.06
                WHEN distance_km < 6000  THEN 150 + distance_km * 0.05
                ELSE                          300 + distance_km * 0.04
            END
        WHERE distance_km IS NOT NULL AND base_demand IS NULL
    """)
    print(f"  {route_count} extra international routes ensured")


def seed_airspace_constraints(cur):
    print("Seeding airspace constraints...")
    for c in AIRSPACE_CONSTRAINTS:
        cur.execute("""
            INSERT INTO airspace_constraints (name, reason, active, zone)
            VALUES (%s, %s, %s, ST_GeogFromText(%s))
            ON CONFLICT DO NOTHING
        """, (c["name"], c["reason"], c["active"], c["wkt"]))

def seed_wind_corridors(cur):
    print("Seeding wind corridors...")
    for w in WIND_CORRIDORS:
        cur.execute("""
            INSERT INTO wind_corridors (name, direction, season, tailwind_factor, corridor)
            VALUES (%s, %s, %s, %s, ST_GeogFromText(%s))
            ON CONFLICT DO NOTHING
        """, (w["name"], w["direction"], w["season"], w["tailwind_factor"], w["wkt"]))

if __name__ == "__main__":
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()
    try:
        seed_airports(cur)
        seed_routes(cur)
        seed_extra_airports_and_routes(cur)
        seed_airspace_constraints(cur)
        seed_wind_corridors(cur)
        conn.commit()
        print("Seed complete.")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()
