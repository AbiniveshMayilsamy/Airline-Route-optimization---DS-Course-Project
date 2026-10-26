from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database import get_db
from backend.models import Route, OptimizedRoute, AirspaceConstraint, WindCorridor
from backend.schemas import RouteOut, OptimizedRouteOut, AirspaceConstraintOut, WindCorridorOut
from typing import List

router = APIRouter()

@router.get("/", response_model=List[RouteOut])
def list_routes(db: Session = Depends(get_db)):
    return db.query(Route).limit(500).all()

@router.get("/optimized")
def list_optimized(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT
            o.id, o.route_id, o.frequency_per_week AS frequency, o.profit_usd,
            o.fuel_cost_usd, o.detour_km, o.wind_saving_usd, o.active_constraints,
            r.origin, r.destination AS dest, r.distance_km, r.base_demand AS demand_pax, r.base_fare_usd AS fare_usd,
            a1.name AS origin_name, a1.city AS origin_city,
            a2.name AS dest_name,   a2.city AS dest_city
        FROM optimized_routes o
        JOIN routes   r  ON r.id    = o.route_id
        JOIN airports a1 ON a1.iata = r.origin
        JOIN airports a2 ON a2.iata = r.destination
        ORDER BY o.run_at DESC, o.profit_usd DESC
        LIMIT 40
    """)).mappings().all()
    return [
        {
            "route_id":          row["route_id"],
            "origin":            row["origin"],
            "dest":              row["dest"],
            "origin_name":       row["origin_name"] or "",
            "dest_name":         row["dest_name"] or "",
            "origin_city":       row["origin_city"] or "",
            "dest_city":         row["dest_city"] or "",
            "distance_km":       round(row["distance_km"] or 0),
            "frequency":         row["frequency"],
            "profit_usd":        row["profit_usd"],
            "fuel_cost_usd":     row["fuel_cost_usd"],
            "detour_km":         row["detour_km"] or 0,
            "wind_saving_usd":   row["wind_saving_usd"] or 0,
            "wind_label":        "",
            "active_constraints": row["active_constraints"] or [],
            "aircraft_type":     "", "aircraft_seats": 0,
            "aircraft_range_km": 0, "aircraft_engine": "", "aircraft_category": "",
            "airlines":          [],
            "demand_pax":        row["demand_pax"] or 0,
            "fare_usd":          round(row["fare_usd"] or 0),
            "load_factor":       0,
        }
        for row in rows
    ]

@router.get("/airspace-constraints", response_model=List[AirspaceConstraintOut])
def list_constraints(db: Session = Depends(get_db)):
    return db.query(AirspaceConstraint).all()

@router.get("/wind-corridors", response_model=List[WindCorridorOut])
def list_wind_corridors(db: Session = Depends(get_db)):
    return db.query(WindCorridor).all()


@router.get("/model-metrics")
def model_metrics(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT metric_name, value, epoch
        FROM model_metrics
        WHERE model_name = 'DemandNet'
        ORDER BY epoch DESC
        LIMIT 30
    """)).mappings().all()
    if not rows:
        return None
    latest = {}
    for r in rows:
        if r["metric_name"] not in latest:
            latest[r["metric_name"]] = r["value"]
    return latest

@router.get("/international/{iata}")
def get_international_routes(iata: str, db: Session = Depends(get_db)):
    """Return all international routes for a given airport with full details."""
    iata = iata.upper()
    rows = db.execute(text("""
        SELECT
            r.id, r.origin, r.destination, r.distance_km,
            r.base_demand, r.base_fare_usd,
            a1.name  AS origin_name,  a1.city  AS origin_city,  a1.country AS origin_country,
            a1.lat   AS origin_lat,   a1.lon   AS origin_lon,
            a2.name  AS dest_name,    a2.city  AS dest_city,    a2.country AS dest_country,
            a2.lat   AS dest_lat,     a2.lon   AS dest_lon,
            -- hourly demand simulation: peak morning/evening
            ARRAY(
                SELECT ROUND(
                    r.base_demand * 0.3 *
                    CASE
                        WHEN h IN (6,7,8,9,17,18,19,20) THEN 1.8
                        WHEN h IN (10,11,12,13,14,15,16) THEN 1.0
                        ELSE 0.4
                    END
                )::int
                FROM generate_series(0,23) AS h
            ) AS hourly_demand
        FROM routes r
        JOIN airports a1 ON a1.iata = r.origin
        JOIN airports a2 ON a2.iata = r.destination
        WHERE (r.origin = :iata OR r.destination = :iata)
          AND a1.country != a2.country
          AND r.distance_km IS NOT NULL
          AND r.base_demand IS NOT NULL
        ORDER BY r.distance_km DESC
        LIMIT 60
    """), {"iata": iata}).mappings().all()

    return [
        {
            "id": row["id"],
            "origin": row["origin"],
            "destination": row["destination"],
            "distance_km": round(row["distance_km"], 0),
            "base_demand": row["base_demand"],
            "base_fare_usd": round(row["base_fare_usd"], 0),
            "origin_name": row["origin_name"],
            "origin_city": row["origin_city"],
            "origin_country": row["origin_country"],
            "origin_lat": row["origin_lat"],
            "origin_lon": row["origin_lon"],
            "dest_name": row["dest_name"],
            "dest_city": row["dest_city"],
            "dest_country": row["dest_country"],
            "dest_lat": row["dest_lat"],
            "dest_lon": row["dest_lon"],
            "hourly_demand": list(row["hourly_demand"]),
            "fuel_cost_usd": round(row["distance_km"] * 12 * 0.85, 0),
            "revenue_usd": round(row["base_demand"] * row["base_fare_usd"], 0),
        }
        for row in rows
    ]
