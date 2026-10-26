from sqlalchemy import Column, String, Integer, Float, Boolean, ARRAY, TIMESTAMP, Text, func
from backend.database import Base

class Airport(Base):
    __tablename__ = "airports"
    iata    = Column(String(3), primary_key=True)
    name    = Column(Text)
    city    = Column(Text)
    country = Column(Text)
    lat     = Column(Float)
    lon     = Column(Float)

class Route(Base):
    __tablename__ = "routes"
    id            = Column(Integer, primary_key=True)
    origin        = Column(String(3))
    destination   = Column(String(3))
    distance_km   = Column(Float)
    base_demand   = Column(Integer)
    base_fare_usd = Column(Float)

class OptimizedRoute(Base):
    __tablename__ = "optimized_routes"
    id                 = Column(Integer, primary_key=True)
    route_id           = Column(Integer)
    frequency_per_week = Column(Integer)
    profit_usd         = Column(Float)
    fuel_cost_usd      = Column(Float)
    detour_km          = Column(Float)
    wind_saving_usd    = Column(Float)
    active_constraints = Column(ARRAY(Text))
    run_at             = Column(TIMESTAMP, server_default=func.now())

class AirspaceConstraint(Base):
    __tablename__ = "airspace_constraints"
    id     = Column(Integer, primary_key=True)
    name   = Column(Text)
    reason = Column(Text)
    active = Column(Boolean)

class WindCorridor(Base):
    __tablename__ = "wind_corridors"
    id             = Column(Integer, primary_key=True)
    name           = Column(Text)
    direction      = Column(Text)
    season         = Column(Text)
    tailwind_factor= Column(Float)
