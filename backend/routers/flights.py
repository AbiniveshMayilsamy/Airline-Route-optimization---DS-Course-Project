"""
Flights API:
  GET  /flights/live          — current snapshot (JSON)
  GET  /flights/trail/{icao}  — last 2h trail for one aircraft
  WS   /flights/ws            — WebSocket stream, pushes update every 15s
"""
import asyncio, json, time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database import get_db
from backend.ingestion import get_snapshot
from fastapi import Depends

router = APIRouter()


@router.get("/live")
async def live_flights():
    flights, ts = get_snapshot()
    return {
        "flights": flights,
        "count":   len(flights),
        "ts":      ts,
    }


@router.get("/trail/{icao24}")
def flight_trail(icao24: str, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT lat, lon, altitude_m, heading, speed_ms,
               EXTRACT(EPOCH FROM ts)::bigint AS ts_epoch
        FROM flight_history
        WHERE icao24 = :icao
        ORDER BY ts DESC
        LIMIT 120
    """), {"icao": icao24.lower()}).mappings().all()
    return [dict(r) for r in rows]


@router.websocket("/ws")
async def flights_ws(websocket: WebSocket):
    """
    WebSocket: client connects, server pushes full flight snapshot every 15s.
    Client can send 'ping' to get immediate snapshot.
    """
    await websocket.accept()
    try:
        last_sent = 0.0
        while True:
            flights, ts = get_snapshot()
            if ts > last_sent:
                await websocket.send_text(json.dumps({
                    "type":    "snapshot",
                    "count":   len(flights),
                    "ts":      ts,
                    "flights": flights,
                }))
                last_sent = ts
            elif not flights:
                # keep-alive: send empty snapshot so client stays connected
                await websocket.send_text(json.dumps({"type": "snapshot", "count": 0, "ts": time.time(), "flights": []}))
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                if msg == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "count": len(flights)}))
            except asyncio.TimeoutError:
                pass
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
