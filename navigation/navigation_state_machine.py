"""
Navigation State Machine - Manages step progression and state transitions.
"""

from typing import Optional, Tuple
from .models import Coordinate, NavigationStep, NavigationState, NavigationStatus, TriggerType
from .haversine import haversine_distance


class NavigationStateMachine:
    """
    Manages navigation state transitions based on user position and route.
    
    State transitions:
    - IDLE -> NAVIGATING: When navigation starts
    - NAVIGATING -> OFF_ROUTE: When user is too far from route (>50m)
    - NAVIGATING -> ARRIVED: When user reaches destination
    - OFF_ROUTE -> RECALCULATING: When recalculation is requested
    - RECALCULATING -> NAVIGATING: When new route is loaded
    """
    
    # Distance thresholds in meters
    OFF_ROUTE_THRESHOLD = 50.0
    PREPARE_THRESHOLD = 30.0
    EXECUTE_THRESHOLD = 10.0
    STEP_COMPLETE_THRESHOLD = 8.0  # Within 8m of step endpoint = completed
    
    def __init__(self, state: NavigationState):
        """
        Initialize the state machine.
        
        Args:
            state: NavigationState to manage
        """
        self._state = state
    
    def start_navigation(self) -> None:
        """Transition to NAVIGATING state."""
        self._state.status = NavigationStatus.NAVIGATING
        self._state.last_trigger = None
        self._state.last_trigger_step = -1
    
    def stop_navigation(self) -> None:
        """Transition to IDLE state."""
        self._state.status = NavigationStatus.IDLE
    
    def process_position(
        self,
        current_pos: Coordinate,
        current_step: NavigationStep,
        route_polyline_points: Optional[list[Coordinate]] = None
    ) -> Tuple[Optional[TriggerType], bool]:
        """
        Process a GPS position update and determine state transitions.
        
        Args:
            current_pos: Current user position
            current_step: Current navigation step
            route_polyline_points: Optional list of polyline points for off-route detection
        
        Returns:
            Tuple of (TriggerType if instruction should be spoken, bool if step is complete)
        """
        if self._state.status != NavigationStatus.NAVIGATING:
            return (None, False)
        
        # Calculate distance to current step endpoint
        distance_to_endpoint = haversine_distance(current_pos, current_step.end_coord)
        
        # Check if step is complete
        step_complete = distance_to_endpoint <= self.STEP_COMPLETE_THRESHOLD
        
        # Determine trigger type based on distance
        trigger = self._evaluate_trigger(distance_to_endpoint, current_step.index)
        
        # Check for off-route condition
        if self._is_off_route(current_pos, current_step, route_polyline_points):
            self._state.status = NavigationStatus.OFF_ROUTE
        
        return (trigger, step_complete)
    
    def _evaluate_trigger(self, distance: float, step_index: int) -> Optional[TriggerType]:
        """
        Evaluate if a trigger should fire based on distance.
        
        Implements debounce logic to prevent duplicate triggers for the same step.
        
        Args:
            distance: Distance to step endpoint in meters
            step_index: Index of current step
        
        Returns:
            TriggerType if trigger should fire, None otherwise
        """
        # Already triggered for this step? Check what we've already announced
        if self._state.last_trigger_step == step_index:
            if self._state.last_trigger == TriggerType.EXECUTE:
                # Already gave execute instruction for this step
                return None
            if self._state.last_trigger == TriggerType.PREPARE and distance > self.EXECUTE_THRESHOLD:
                # Already gave prepare, waiting for execute
                return None
        
        # Determine appropriate trigger
        if distance <= self.EXECUTE_THRESHOLD:
            trigger = TriggerType.EXECUTE
        elif distance <= self.PREPARE_THRESHOLD:
            trigger = TriggerType.PREPARE
        else:
            return None
        
        # Check if this is a new trigger we should announce
        if self._state.last_trigger_step != step_index:
            # New step, announce
            self._state.last_trigger = trigger
            self._state.last_trigger_step = step_index
            return trigger
        elif trigger == TriggerType.EXECUTE and self._state.last_trigger == TriggerType.PREPARE:
            # Upgrade from PREPARE to EXECUTE
            self._state.last_trigger = trigger
            return trigger
        
        return None
    
    def _is_off_route(
        self,
        current_pos: Coordinate,
        current_step: NavigationStep,
        polyline_points: Optional[list[Coordinate]] = None
    ) -> bool:
        """
        Check if the user is off-route.
        
        Uses distance to current step start/end as simple heuristic.
        Could be enhanced with polyline point-to-line distance.
        
        Args:
            current_pos: Current user position
            current_step: Current navigation step
            polyline_points: Optional polyline points for more accurate detection
        
        Returns:
            True if user is off-route, False otherwise
        """
        # Simple heuristic: check distance to both start and end of current step
        dist_to_start = haversine_distance(current_pos, current_step.start_coord)
        dist_to_end = haversine_distance(current_pos, current_step.end_coord)
        
        # Consider off-route if far from both points
        # During navigation, user should be between or near these points
        min_dist = min(dist_to_start, dist_to_end)
        
        # Also check if they're within the expected range of the step
        step_length = haversine_distance(current_step.start_coord, current_step.end_coord)
        max_allowed = max(self.OFF_ROUTE_THRESHOLD, step_length + self.OFF_ROUTE_THRESHOLD)
        
        return min_dist > max_allowed
    
    def mark_arrived(self) -> None:
        """Mark navigation as arrived at destination."""
        self._state.status = NavigationStatus.ARRIVED
    
    def request_recalculation(self) -> None:
        """Request route recalculation due to off-route condition."""
        self._state.status = NavigationStatus.RECALCULATING
    
    def on_route_recalculated(self) -> None:
        """Called when a new route has been calculated."""
        self._state.status = NavigationStatus.NAVIGATING
        self._state.current_step_index = 0
        self._state.last_trigger = None
        self._state.last_trigger_step = -1
    
    @property
    def status(self) -> NavigationStatus:
        """Get current navigation status."""
        return self._state.status
    
    @property
    def is_navigating(self) -> bool:
        """Check if currently navigating."""
        return self._state.status == NavigationStatus.NAVIGATING
    
    @property
    def is_off_route(self) -> bool:
        """Check if currently off-route."""
        return self._state.status == NavigationStatus.OFF_ROUTE
