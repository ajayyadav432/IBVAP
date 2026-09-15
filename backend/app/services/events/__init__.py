# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.events
# Description: Exports for Centralized Event Engine and Real-Time Alert Delivery.
# License: Apache-2.0
# ==============================================================================

from app.services.events.models import (
    EventCandidate,
    EventSeverity,
    EventStatus,
    SystemEventType,
    DEFAULT_SEVERITY_MAP,
)
from app.services.events.websocket import (
    ConnectionManager,
    connection_manager,
)
from app.services.events.engine import (
    EventEngine,
    event_engine,
)

__all__ = [
    "EventCandidate",
    "EventSeverity",
    "EventStatus",
    "SystemEventType",
    "DEFAULT_SEVERITY_MAP",
    "ConnectionManager",
    "connection_manager",
    "EventEngine",
    "event_engine",
]
