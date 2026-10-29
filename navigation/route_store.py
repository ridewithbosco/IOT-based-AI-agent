"""
Route store - In-memory storage for route and navigation state.
"""

from typing import Optional, List
from .models import NavigationStep, NavigationState, NavigationStatus, RouteInfo


class RouteStore:
    """
    In-memory storage for navigation route and state.
    
    Stores the complete route and tracks navigation progress.
    """
    
    def __init__(self):
        """Initialize empty route store."""
        self._route: Optional[RouteInfo] = None
        self._state: NavigationState = NavigationState()
    
    def load_route(self, route: RouteInfo, destination: str) -> None:
        """
        Load a new route into the store.
        
        Args:
            route: RouteInfo containing parsed steps
            destination: Destination name for reference
        """
        self._route = route
        self._state.reset()
        self._state.total_steps = route.step_count
        self._state.destination = destination
        self._state.status = NavigationStatus.IDLE
    
    def get_current_step(self) -> Optional[NavigationStep]:
        """
        Get the current navigation step.
        
        Returns:
            Current NavigationStep, or None if no route is loaded or navigation is complete
        """
        if not self._route or not self._route.steps:
            return None
        
        if self._state.current_step_index >= len(self._route.steps):
            return None
        
        return self._route.steps[self._state.current_step_index]
    
    def get_next_step(self) -> Optional[NavigationStep]:
        """
        Get the next navigation step (peek ahead).
        
        Returns:
            Next NavigationStep, or None if at the last step
        """
        if not self._route or not self._route.steps:
            return None
        
        next_index = self._state.current_step_index + 1
        if next_index >= len(self._route.steps):
            return None
        
        return self._route.steps[next_index]
    
    def advance_step(self) -> bool:
        """
        Advance to the next step.
        
        Returns:
            True if advanced to next step, False if already at the end
        """
        if not self._route:
            return False
        
        if self._state.current_step_index >= len(self._route.steps) - 1:
            self._state.status = NavigationStatus.ARRIVED
            return False
        
        self._state.current_step_index += 1
        return True
    
    def get_all_steps(self) -> List[NavigationStep]:
        """Get all navigation steps."""
        if not self._route:
            return []
        return self._route.steps
    
    def get_remaining_steps(self) -> List[NavigationStep]:
        """Get remaining navigation steps from current position."""
        if not self._route:
            return []
        return self._route.steps[self._state.current_step_index:]
    
    @property
    def state(self) -> NavigationState:
        """Get current navigation state."""
        return self._state
    
    @property
    def route(self) -> Optional[RouteInfo]:
        """Get loaded route info."""
        return self._route
    
    @property
    def is_route_loaded(self) -> bool:
        """Check if a route is currently loaded."""
        return self._route is not None and len(self._route.steps) > 0
    
    @property
    def is_navigation_complete(self) -> bool:
        """Check if navigation has reached the destination."""
        return self._state.status == NavigationStatus.ARRIVED
    
    @property
    def progress(self) -> tuple[int, int]:
        """
        Get navigation progress.
        
        Returns:
            Tuple of (current_step_number, total_steps) - 1-indexed for display
        """
        return (self._state.current_step_index + 1, self._state.total_steps)
    
    def reset(self) -> None:
        """Reset the store to initial state."""
        self._route = None
        self._state.reset()
    
    def set_status(self, status: NavigationStatus) -> None:
        """Update the navigation status."""
        self._state.status = status
