# Airline Route Optimization System — Project Plan

A full-stack data science project combining network optimization, demand forecasting, and
3D geospatial visualization of airline routes using IATA codes.

---

## 1. Project Scope

**Core question:** Given a hub airport and a set of candidate destinations, which routes
should an airline operate (and at what frequency) to maximize profit?

**First-version scope (keep it tractable):**
- 1 hub airport
- 15–30 candidate destination routes
- Optimize which subset to fly + frequency to maximize profit

**Possible extensions once the core works:**
- Pricing / fare optimization per route
- Delay-aware scheduling
- Multi-hub network optimization

---

## 2. Architecture Overview

```
[PostgreSQL + PostGIS] → [Python ML/Optimization] → [FastAPI backend] → [React frontend + 3D Globe]
```

**Data flow:**
1. BTS / OpenFlights data → cleaned in pandas → loaded into PostgreSQL
2. Python trains demand model, runs OR-Tools optimization → writes results back to Postgres (`optimized_routes` table)
3. FastAPI reads from Postgres, serves JSON with IATA codes + lat/lon + route metrics
4. React fetches JSON, feeds it into `react-globe.gl` as `arcsData`, colored by profit/demand

---

## 3. Data Sources

| Source | Use |
|---|---|
| [US DOT/BTS On-Time Performance data](https://www.transtats.bts.gov/) | Flights, delays, carriers, origin/destination (large, free, monthly) |
| [OpenFlights](https://openflights.org/data.php) | Airport locations, routes, airlines — good for network graphs |
| DOT DB1B (10% ticket sample) | Fare data, for pricing/demand modeling |
| [OpenSky Network](https://opensky-network.org/) / FlightAware | Real historical/live flight tracking |
| Airport/city demographics (population, GDP) | Demand proxy modeling |

---

## 4. Database Layer — PostgreSQL

- **PostgreSQL** — core relational store
- **PostGIS extension** — geospatial queries (great-circle distances, proximity searches)

**Suggested tables:**
- `airports` — IATA code, name, lat, lon, country
- `routes` — origin, destination, distance, demand
- `flights` — historical BTS records
- `predictions` — model output (predicted demand/fare per route)
- `optimized_routes` — final optimizer output (selected routes, frequency, profit)

---

## 5. Model Training — Python

| Tool | Purpose |
|---|---|
| pandas / numpy | Data cleaning & prep |
| scikit-learn / XGBoost / LightGBM | Demand & fare prediction |
| PuLP or Google OR-Tools | Route optimization (linear/integer programming) |
| networkx | Route network analysis (centrality, shortest paths, hub detection) |
| joblib / ONNX | Save/export trained models |

**Pipeline steps:**
1. Data prep — clean flights/routes, merge airport coordinates, build route-level table
2. EDA — network graph of routes, busiest hubs, delay patterns, seasonal demand
3. Demand forecasting — regression/time series model per route
4. Cost/profit modeling — cost (distance, fuel, fixed costs) vs. revenue (demand × fare)
5. Optimization — LP/IP formulation:
   - Decision variables: which routes to fly, frequency
   - Objective: maximize profit
   - Constraints: fleet size, airport slots, crew hours, max routes per hub
6. Visualization — feed optimizer output to the globe

---

## 6. Backend API — FastAPI

Connects the trained models/optimizer to the frontend.

| Tool | Purpose |
|---|---|
| FastAPI | API framework (Python-native, plugs directly into ML code) |
| SQLAlchemy / asyncpg / psycopg2 | Postgres connectivity |
| Pydantic | Request/response validation (built into FastAPI) |
| uvicorn | ASGI server |

**Suggested endpoints:**
- `GET /airports` → all IATA airports with coordinates
- `GET /routes` → current/optimized routes
- `POST /optimize` → trigger a new optimization run
- `GET /predictions/{route_id}` → demand forecast for a route

---

## 7. Frontend — React + 3D Globe

| Library | Notes |
|---|---|
| **react-globe.gl** | Easiest option — purpose-built for arcs/points/labels on a 3D globe. Best starting point. |
| Three.js (raw) | More control, more manual work — use if react-globe.gl is too limiting |
| deck.gl + react-map-gl | Better for large-scale geospatial "data viz" over a map |
| Kepler.gl | Full geospatial analytics UI — overkill for this scope |

For IATA-code-to-IATA-code route arcs, **react-globe.gl** is the fastest path: feed it
lat/lon pairs via `arcsData`, `pointsData`, and `labelsData` props.

**Supporting frontend tools:**
- React + Vite + TypeScript
- Axios / fetch / TanStack Query — calling the FastAPI backend
- Tailwind CSS — dashboard UI (filters, route tables, stats panels)
- Recharts — supplementary charts (demand trends, profit comparisons)

---

## 8. Optional / Impressive Additions

- **Docker Compose** — containerize Postgres + FastAPI + React together (great for portfolio, shows deployment awareness)
- **Redis** — cache optimization results if runs are slow
- **Celery** — background job runner if training/optimization takes long

---

## 9. Full Tool Stack Summary

| Layer | Tools |
|---|---|
| Database | PostgreSQL, PostGIS |
| Data prep / ML | pandas, numpy, scikit-learn, XGBoost/LightGBM, networkx |
| Optimization | PuLP, Google OR-Tools |
| Backend API | FastAPI, SQLAlchemy/asyncpg, Pydantic, uvicorn |
| Frontend | React, Vite, TypeScript, react-globe.gl, Tailwind CSS, Recharts |
| Data fetching | Axios / TanStack Query |
| DevOps (optional) | Docker Compose, Redis, Celery |

---

## 10. Suggested Project Structure

```
airline-route-optimization/
├── data/
│   ├── raw/                  # BTS, OpenFlights raw downloads
│   └── processed/            # cleaned CSVs ready for DB load
├── db/
│   ├── schema.sql            # table definitions + PostGIS setup
│   └── seed.py                # load cleaned data into Postgres
├── ml/
│   ├── eda.ipynb              # exploratory analysis
│   ├── demand_model.py        # demand/fare forecasting
│   ├── optimizer.py           # PuLP/OR-Tools route optimization
│   └── utils.py
├── backend/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── routers/
│   │   ├── airports.py
│   │   ├── routes.py
│   │   └── optimize.py
│   ├── models.py               # SQLAlchemy models
│   └── schemas.py              # Pydantic schemas
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Globe.tsx       # react-globe.gl component
│   │   │   ├── Dashboard.tsx
│   │   │   └── RouteTable.tsx
│   │   ├── api/                # axios/query hooks
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
└── README.md
```

---

## 11. Next Steps

1. Pull and clean real datasets (BTS on-time performance + OpenFlights)
2. Set up PostgreSQL + PostGIS locally (or via Docker)
3. Build the demand model and optimizer in Python, validate on a single hub
4. Scaffold FastAPI backend with the core endpoints
5. Scaffold React + react-globe.gl frontend with dummy IATA route data first
6. Wire real optimizer output into the globe visualization
