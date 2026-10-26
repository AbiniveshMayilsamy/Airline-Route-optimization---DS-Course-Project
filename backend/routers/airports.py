from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Airport
from backend.schemas import AirportOut
from typing import List

router = APIRouter()

@router.get("/", response_model=List[AirportOut])
def list_airports(db: Session = Depends(get_db)):
    return db.query(Airport).all()

@router.get("/{iata}", response_model=AirportOut)
def get_airport(iata: str, db: Session = Depends(get_db)):
    airport = db.query(Airport).filter(Airport.iata == iata.upper()).first()
    if not airport:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Airport '{iata}' not found")
    return airport
