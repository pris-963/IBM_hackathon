
from sqlalchemy import (
    Column,
    DateTime,
    String,
    func,
)

from .database import Base


class Alert(Base):
    __tablename__ = "alerts"

    # Unique event ID prevents duplicate alert records.
    event_id = Column(String(64), primary_key=True, index=True)

    device_id = Column(String(64), nullable=False, index=True)
    risk_level = Column(String(10), nullable=False, index=True)
    event_type = Column(String(40), nullable=False)

    # Time the server accepted the alert.
    received_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
