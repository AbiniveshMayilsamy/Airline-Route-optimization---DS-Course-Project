from fastapi import APIRouter, BackgroundTasks
from backend.schemas import OptimizeRequest, OptimizedRouteOut
from typing import List
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from ml.optimizer import optimize as run_optimizer

router = APIRouter()

@router.post("/", response_model=List[dict])
def trigger_optimize(req: OptimizeRequest):
    results = run_optimizer(
        hub_iata=req.hub_iata,
        season=req.season,
        max_routes=req.max_routes,
        fleet_size=req.fleet_size,
    )
    return results
