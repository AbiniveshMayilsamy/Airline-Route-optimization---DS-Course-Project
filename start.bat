@echo off
echo ===================================================
echo Starting Airline Route Optimization System
echo ===================================================

echo Starting Docker containers (db, backend, frontend)...
docker compose up -d

echo.
echo Containers are up and running!
echo Frontend: http://localhost:5173
echo Backend API: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo To seed or re-seed database:
echo   docker compose exec backend python db/seed.py
echo.
echo To view logs:
echo   docker compose logs -f
echo ===================================================
