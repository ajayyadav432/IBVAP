# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.rules.base
# Description: Abstract base class for deterministic, explainable activity rules.
# License: Apache-2.0
# ==============================================================================

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.services.tracking.tracker import Track
from app.services.zone.models import ZoneDefinition, IntrusionEventCandidate
from app.services.rules.models import SuspiciousActivityCandidate


class BaseActivityRule(ABC):
    """
    Abstract interface for suspicious activity detection rules.
    Rules must consume normalized data structures and have zero direct dependencies
    on raw neural network layers, UI components, or database/WebSocket plumbing.
    """

    @abstractmethod
    def evaluate(
        self,
        tracks: List[Track],
        zones: List[ZoneDefinition],
        zone_candidates: List[IntrusionEventCandidate],
        frame_time: float,
        timestamp_iso: str,
        frame_idx: int = 0,
    ) -> List[SuspiciousActivityCandidate]:
        """
        Evaluate normalized scene telemetry and return newly generated suspicious activity candidates.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal rule states (e.g. on camera restart)."""
        pass
