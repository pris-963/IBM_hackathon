
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Alert
from device.security import verify_token


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the alerts table if it does not exist.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Dynamic Exposed-Only Safety Layer API",
    description="Validates authenticated safety alerts and stores metadata.",
    version="1.0.0",
    lifespan=lifespan,
)


class AlertRequest(BaseModel):
    token: str = Field(min_length=10, max_length=4096)


@app.get("/")
def home():
    return {
        "project": "Dynamic, Exposed-Only Safety Layer",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/alerts", status_code=201)
def receive_alert(
    request: AlertRequest,
    db: Session = Depends(get_db),
):
    # Step 1: Verify the token's signature and timestamp.
    payload = verify_token(request.token)

    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid signature or expired token",
        )

    # Step 2: Extract only authenticated metadata.
    event_id = payload["event_id"]
    device_id = payload["device_id"]
    risk_level = payload["risk_level"]
    event_type = payload["event_type"]

    # Step 3: Save the alert without raw sensor readings.
    alert = Alert(
        event_id=event_id,
        device_id=device_id,
        risk_level=risk_level,
        event_type=event_type,
    )

    try:
        db.add(alert)
        db.commit()

    except IntegrityError:
        # A previously received event ID cannot be stored again.
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Duplicate alert: event already received",
        )

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable",
        )

    return {
        "accepted": True,
        "event_id": event_id,
        "device_id": device_id,
        "risk_level": risk_level,
        "message": "Alert verified and stored successfully",
    }


@app.get("/alerts")
def list_alerts(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    if not 1 <= limit <= 200:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 200",
        )

    alerts = (
        db.query(Alert)
        .order_by(Alert.received_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "event_id": alert.event_id,
            "device_id": alert.device_id,
            "risk_level": alert.risk_level,
            "event_type": alert.event_type,
            "received_at": alert.received_at,
        }
        for alert in alerts
    ]
