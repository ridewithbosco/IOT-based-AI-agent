"""
Data models for the navigation engine.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List


class TriggerType(Enum):
    """Types of navigation instruction triggers."""
    PREPARE = auto()   # Approaching step (30m)
    EXECUTE = auto()   # At step (10m)
    COMPLETED = auto() # Step completed


class NavigationStatus(Enum):
    """Current navigation status."""
    IDLE = auto()
    NAVIGATING = auto()
    ARRIVED = auto()
    OFF_ROUTE = auto()
    RECALCULATING = auto()


@dataclass
class Coordinate:
    """GPS coordinate with latitude and longitude."""
    lat: float
    lon: float
    
    def __post_init__(self):
        if not -90 <= self.lat <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {self.lat}")
        if not -180 <= self.lon <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {self.lon}")
    
    def as_tuple(self) -> tuple[float, float]:
        """Return as (lat, lon) tuple."""
        return (self.lat, self.lon)
    
    def __str__(self) -> str:
        return f"({self.lat:.6f}, {self.lon:.6f})"


@dataclass
class NavigationStep:
    """A single navigation step from the route."""
    index: int
    instruction: str  # Plain text, HTML stripped
    start_coord: Coordinate
    end_coord: Coordinate
    distance_meters: float
    distance_text: str  # Human readable, e.g., "150 m"
    duration_seconds: float
    duration_text: str  # Human readable, e.g., "2 mins"
    polyline: Optional[str] = None  # Encoded polyline
    maneuver: Optional[str] = None  # e.g., "turn-left", "turn-right"
    
    def get_tts_instruction(self, trigger_type: TriggerType) -> str:
        """Generate TTS-ready instruction based on trigger type."""
        if trigger_type == TriggerType.PREPARE:
            return f"In {self.distance_text}, {self.instruction}"
        elif trigger_type == TriggerType.EXECUTE:
            return f"Now, {self.instruction}"
        elif trigger_type == TriggerType.COMPLETED:
            return "Step completed. Continuing to next direction."
        return self.instruction


@dataclass
class NavigationState:
    """Current state of navigation."""
    current_step_index: int = 0
    status: NavigationStatus = NavigationStatus.IDLE
    last_trigger: Optional[TriggerType] = None
    last_trigger_step: int = -1  # Prevents duplicate triggers
    total_steps: int = 0
    destination: str = ""
    
    def reset(self):
        """Reset state to initial values."""
        self.current_step_index = 0
        self.status = NavigationStatus.IDLE
        self.last_trigger = None
        self.last_trigger_step = -1
        self.total_steps = 0
        self.destination = ""


@dataclass
class RouteInfo:
    """Complete route information."""
    steps: List[NavigationStep] = field(default_factory=list)
    total_distance_meters: float = 0.0
    total_distance_text: str = ""
    total_duration_seconds: float = 0.0
    total_duration_text: str = ""
    start_address: str = ""
    end_address: str = ""
    
    @property
    def step_count(self) -> int:
        return len(self.steps)
