# Airline Route Optimization System

Full-stack route optimization with fuel economics, wind corridor modeling, and airspace constraint handling.

## Stack
- **DB**: PostgreSQL + PostGIS
- **ML/Optimization**: Python, OR-Tools CP-SAT, scikit-learn
- **Backend**: FastAPI
- **Frontend**: React + Vite + react-globe.gl + Tailwind

## Key Features

### Fuel Economics
- Per-route fuel burn: `distance_km × 12 kg/km × $0.85/kg`
- Detour fuel cost added when airspace constraints are active
- Wind factor multiplied onto effective distance

### Transatlantic Wind Economics
| Season | Direction | Fuel Factor | Impact |
|--------|-----------|-------------|--------|
| Winter | Eastbound | 0.82 | 18% saving (jet stream tailwind) |
| Winter | Westbound | 1.18 | 18% penalty (headwind) |
| Summer | Eastbound | 0.93 | 7% saving |
| Summer | Westbound | 1.07 | 7% penalty |

### Airspace Constraints
| Constraint | Detour | Affected Routes |
|---|---|---|
| Pakistan Airspace | +1,200 km | India ↔ Europe (Air India DEL→LHR etc.) |
| Pakistan + Russia | +2,800 km | India ↔ North America |
| Red Sea / Houthi Zone | +600 km | Europe ↔ Middle East |
| Russian Airspace | 0 km | EU/US (polar route available) |

Globe arc colors:
- 🟢 Green = wind tailwind saving
- 🟠 Orange = airspace detour active
- 🔴 Red = unprofitable route
- 🔵 Blue = normal route

## Quick Start

```bash
# 1. Start DB + backend + frontend
docker-compose up

# 2. Seed data (first time)
docker-compose exec backend python db/seed.py

# 3. Open frontend
http://localhost:5173
```

## Manual Setup (no Docker)

```bash
# Python deps
pip install -r requirements.txt

# Start DB (PostgreSQL + PostGIS must be running)
psql -U postgres -c "CREATE DATABASE airline_opt;"
psql -U postgres -d airline_opt -f db/schema.sql
python db/seed.py

# Backend
uvicorn backend.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

## Optimize from CLI

```bash
# DEL hub, winter season
python ml/optimizer.py DEL winter

# JFK hub, summer season  
python ml/optimizer.py JFK summer
```

## EDA

```bash
python ml/eda.py
```
