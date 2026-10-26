import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import airports, routes, optimize, flights
from backend.ingestion import run_ingestion


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start live flight ingestion as background task
    task = asyncio.create_task(run_ingestion())
    yield
    task.cancel()


app = FastAPI(title="Airline Route Optimization API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(airports.router, prefix="/airports", tags=["airports"])
app.include_router(routes.router,   prefix="/routes",   tags=["routes"])
app.include_router(optimize.router, prefix="/optimize", tags=["optimize"])
app.include_router(flights.router,  prefix="/flights",  tags=["flights"])
