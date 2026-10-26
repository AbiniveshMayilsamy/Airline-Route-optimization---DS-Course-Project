"""
Route optimizer — fixed to return more routes with airline + aircraft type data.
"""
import os, sys, psycopg2
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ortools.sat.python import cp_model
from ml.demand_model import route_profit

DB = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/airline_opt")

AIRSPACE_DETOURS = {
    ("IN","EU"): (1200,"Pakistan Airspace"), ("EU","IN"): (1200,"Pakistan Airspace"),
    ("IN","NA"): (2800,"Pakistan Airspace + Russian Airspace"), ("NA","IN"): (2800,"Pakistan Airspace + Russian Airspace"),
    ("EU","NA"): (0,None), ("NA","EU"): (0,None),
    ("EU","ME"): (600,"Red Sea / Houthi Zone"), ("ME","EU"): (600,"Red Sea / Houthi Zone"),
    ("IN","ME"): (0,None), ("ME","IN"): (0,None),
}

WIND_FACTORS = {
    (True,"eastbound","winter"):0.82, (True,"westbound","winter"):1.18,
    (True,"eastbound","summer"):0.93, (True,"westbound","summer"):1.07,
}

# Aircraft type by distance
def aircraft_type(dist_km: float) -> dict:
    if dist_km < 1500:
        return {"type":"Airbus A320","seats":180,"range_km":6150,"engine":"CFM56","category":"Narrowbody"}
    elif dist_km < 3500:
        return {"type":"Boeing 737-800","seats":162,"range_km":5765,"engine":"CFM56-7B","category":"Narrowbody"}
    elif dist_km < 6000:
        return {"type":"Airbus A321XLR","seats":220,"range_km":8700,"engine":"CFM LEAP-1A","category":"Narrowbody LR"}
    elif dist_km < 9000:
        return {"type":"Boeing 787-9","seats":296,"range_km":14140,"engine":"GEnx-1B","category":"Widebody"}
    else:
        return {"type":"Airbus A350-900","seats":369,"range_km":15000,"engine":"Trent XWB","category":"Widebody ULR"}

# Airline assignment by region pair
def assign_airline(origin_country: str, dest_country: str, origin: str) -> list:
    IN = {"IN","PK","BD","LK","NP"}
    EU = {"GB","DE","FR","NL","ES","IT","CH","AT","BE","SE","NO","DK","FI","PL","PT","IE","GR"}
    NA = {"US","CA","MX"}
    ME = {"AE","SA","QA","KW","BH","OM","IQ","IR","YE","JO","IL"}
    AS = {"SG","MY","TH","JP","KR","CN","HK","TW","VN","ID","PH"}

    airlines = []
    if origin_country in IN:
        airlines = ["Air India (AI)","IndiGo (6E)","Air India Express (IX)","Vistara (UK)"]
    elif origin_country in ME:
        airlines = ["Emirates (EK)","Qatar Airways (QR)","Etihad Airways (EY)","flydubai (FZ)","Air Arabia (G9)"]
    elif origin_country in EU:
        airlines = ["British Airways (BA)","Lufthansa (LH)","Air France (AF)","KLM (KL)","Ryanair (FR)"]
    elif origin_country in NA:
        airlines = ["American Airlines (AA)","Delta Air Lines (DL)","United Airlines (UA)","Air Canada (AC)"]
    elif origin_country in AS:
        airlines = ["Singapore Airlines (SQ)","Cathay Pacific (CX)","ANA (NH)","Korean Air (KE)","Malaysia Airlines (MH)"]
    else:
        airlines = ["Ethiopian Airlines (ET)","LATAM Airlines (LA)","Qantas (QF)","Turkish Airlines (TK)"]
    return airlines[:2]

def get_region(country: str) -> str:
    if country in {"IN","PK","BD","LK","NP"}: return "IN"
    if country in {"GB","DE","FR","NL","ES","IT","CH","AT","BE","SE","NO","DK","FI","PL","PT","IE","GR","CZ","HU","RO"}: return "EU"
    if country in {"US","CA","MX"}: return "NA"
    if country in {"AE","SA","QA","KW","BH","OM","IQ","IR","YE","JO","IL","LB","SY"}: return "ME"
    if country in {"RU","UA","BY","KZ","UZ"}: return "RU"
    return "OTHER"

def get_wind_factor(o_lon, d_lon, season):
    is_ta = (o_lon < -20 and d_lon > -20) or (o_lon > -20 and d_lon < -20)
    if not is_ta: return 1.0, "none"
    direction = "eastbound" if d_lon > o_lon else "westbound"
    return WIND_FACTORS.get((True, direction, season), 1.0), f"transatlantic_{direction}_{season}"

def optimize(hub_iata: str, season: str = "winter",
             max_routes: int = 20, fleet_size: int = 15,
             max_freq_per_route: int = 14):
    conn = psycopg2.connect(DB)
    cur  = conn.cursor()

    cur.execute("""
        SELECT r.id, r.origin, r.destination, r.distance_km,
               r.base_demand, r.base_fare_usd,
               a1.lon, a2.lon, a1.country, a2.country,
               a1.name, a2.name, a1.city, a2.city,
               a1.continent, a2.continent, a1.type, a2.type
        FROM routes r
        JOIN airports a1 ON a1.iata = r.origin
        JOIN airports a2 ON a2.iata = r.destination
        WHERE (r.origin = %s OR r.destination = %s)
          AND r.distance_km IS NOT NULL
          AND r.base_demand IS NOT NULL
          AND r.base_fare_usd IS NOT NULL
        ORDER BY (r.base_demand * r.base_fare_usd - r.distance_km * 8.0) DESC
        LIMIT 150
    """, (hub_iata, hub_iata))
    rows = cur.fetchall()

    if not rows:
        cur.close(); conn.close()
        return []

    route_data = []
    seen_pairs = set()
    for row in rows:
        (rid, origin, dest, dist_km, demand, fare,
         o_lon, d_lon, o_country, d_country,
         o_name, d_name, o_city, d_city,
         o_cont, d_cont, o_type, d_type) = row
        if not all([dist_km, demand, fare]): continue

        pair_key = (min(origin, dest), max(origin, dest))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        o_region = get_region(o_country or "")
        d_region = get_region(d_country or "")
        detour_km, constraint = AIRSPACE_DETOURS.get(
            (o_region, d_region), AIRSPACE_DETOURS.get((d_region, o_region), (0, None))
        )
        wind_factor, wind_label = get_wind_factor(o_lon or 0, d_lon or 0, season)
        ac = aircraft_type(dist_km)
        airlines = assign_airline(o_country or "", d_country or "", origin)

        breakdown = route_profit(dist_km, demand, fare, 1, wind_factor=wind_factor, detour_km=detour_km, seats=ac["seats"])
        route_data.append({
            "id": rid, "origin": origin, "dest": dest,
            "origin_name": o_name, "dest_name": d_name,
            "origin_city": o_city, "dest_city": d_city,
            "dist_km": dist_km, "demand": demand, "fare": fare,
            "detour_km": detour_km, "wind_factor": wind_factor,
            "wind_label": wind_label, "constraint": constraint,
            "aircraft": ac, "airlines": airlines,
            "profit_per_flight": breakdown["profit"],
            "fuel_cost_per_flight": breakdown["fuel_cost"],
            "wind_saving_per_flight": breakdown["wind_saving_usd"],
        })

    if not route_data:
        cur.close(); conn.close()
        return []

    # OR-Tools CP-SAT
    model  = cp_model.CpModel()
    SCALE  = 10
    fly    = [model.NewBoolVar(f"fly_{i}") for i in range(len(route_data))]
    freq   = [model.NewIntVar(0, max_freq_per_route, f"freq_{i}") for i in range(len(route_data))]

    for i in range(len(route_data)):
        model.Add(freq[i] == 0).OnlyEnforceIf(fly[i].Not())
        model.Add(freq[i] >= 1).OnlyEnforceIf(fly[i])

    model.Add(sum(fly) <= max_routes)
    model.Add(sum(freq) <= fleet_size * 7)

    profit_terms = [
        int(max(-1e6, route_data[i]["profit_per_flight"]) * SCALE) * freq[i]
        for i in range(len(route_data))
    ]
    model.Maximize(sum(profit_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20.0
    status = solver.Solve(model)

    results = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for i, rd in enumerate(route_data):
            f = solver.Value(freq[i])
            if f == 0: continue
            breakdown = route_profit(rd["dist_km"], rd["demand"], rd["fare"], f,
                                     wind_factor=rd["wind_factor"], detour_km=rd["detour_km"],
                                     seats=rd["aircraft"]["seats"])
            cur.execute("""
                INSERT INTO optimized_routes
                  (route_id, frequency_per_week, profit_usd, fuel_cost_usd,
                   detour_km, wind_saving_usd, active_constraints)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (rd["id"], f, round(breakdown["profit"],2), round(breakdown["fuel_cost"],2),
                  rd["detour_km"], round(breakdown["wind_saving_usd"],2),
                  [rd["constraint"]] if rd["constraint"] else []))
            results.append({
                "route_id":          rd["id"],
                "origin":            rd["origin"],
                "dest":              rd["dest"],
                "origin_name":       rd["origin_name"] or "",
                "dest_name":         rd["dest_name"] or "",
                "origin_city":       rd["origin_city"] or "",
                "dest_city":         rd["dest_city"] or "",
                "distance_km":       round(rd["dist_km"]),
                "frequency":         f,
                "profit_usd":        round(breakdown["profit"], 2),
                "fuel_cost_usd":     round(breakdown["fuel_cost"], 2),
                "detour_km":         rd["detour_km"],
                "wind_saving_usd":   round(breakdown["wind_saving_usd"], 2),
                "wind_label":        rd["wind_label"],
                "active_constraints":[rd["constraint"]] if rd["constraint"] else [],
                "aircraft_type":     rd["aircraft"]["type"],
                "aircraft_seats":    rd["aircraft"]["seats"],
                "aircraft_range_km": rd["aircraft"]["range_km"],
                "aircraft_engine":   rd["aircraft"]["engine"],
                "aircraft_category": rd["aircraft"]["category"],
                "airlines":          rd["airlines"],
                "demand_pax":        rd["demand"],
                "fare_usd":          round(rd["fare"]),
                "load_factor":       round(min(1.0, rd["demand"] / rd["aircraft"]["seats"]), 2),
            })
        conn.commit()

    cur.close(); conn.close()
    return results

if __name__ == "__main__":
    import json, sys
    hub    = sys.argv[1] if len(sys.argv) > 1 else "DEL"
    season = sys.argv[2] if len(sys.argv) > 2 else "winter"
    print(json.dumps(optimize(hub, season=season), indent=2))
