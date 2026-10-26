from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class AirportOut(BaseModel):
    iata: str
    name: str
    city: Optional[str]
    country: Optional[str]
    lat: float
    lon: float
    class Config: from_attributes = True

class RouteOut(BaseModel):
    id: int
    origin: str
    destination: str
    distance_km: Optional[float]
    base_demand: Optional[int]
    base_fare_usd: Optional[float]
    class Config: from_attributes = True

class OptimizedRouteOut(BaseModel):
    id: int
    route_id: int
    frequency_per_week: int
    profit_usd: float
    fuel_cost_usd: float
    detour_km: float
    wind_saving_usd: float
    active_constraints: Optional[List[str]]
    run_at: datetime
    class Config: from_attributes = True

class OptimizeRequest(BaseModel):
    hub_iata: str
    season: str = "winter"
    max_routes: int = 20
    fleet_size: int = 10

class AirspaceConstraintOut(BaseModel):
    id: int
    name: str
    reason: Optional[str]
    active: bool
    class Config: from_attributes = True

class WindCorridorOut(BaseModel):
    id: int
    name: str
    direction: str
    season: str
    tailwind_factor: float
    class Config: from_attributes = True
