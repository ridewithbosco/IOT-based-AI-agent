"""
Navigation Controller - Main orchestrator for continuous navigation.

Coordinates GPS reading, route management, and instruction triggering.
"""

import asyncio
from typing import Optional, Callable
from .models import Coordinate, NavigationStatus
from .route_fetcher import RouteFetcher
from .route_store import RouteStore
from .gps_reader import GPSReader, MockGPSReader
from .navigation_state_machine import NavigationStateMachine
from .trigger_engine import TriggerEngine


class NavigationController:
    """
    Main navigation controller that orchestrates the continuous navigation loop.
    
    Coordinates:
    - GPS reading at 1 Hz
    - Route fetching and storage
    - State machine transitions
    - Instruction triggering
    """
    
    GPS_POLL_INTERVAL = 1.0  # seconds (1 Hz)
    MAX_RECALCULATION_ATTEMPTS = 3
    
    def __init__(
        self,
        gps_reader: Optional[GPSReader] = None,
        on_instruction: Optional[Callable[[str], None]] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize the navigation controller.
        
        Args:
            gps_reader: GPS reader instance (defaults to MockGPSReader)
            on_instruction: Callback for navigation instructions (for TTS)
            api_key: Google Maps API key (optional, uses env var if not provided)
        """
        self._gps_reader = gps_reader or MockGPSReader()
        self._route_fetcher = RouteFetcher(api_key)
        self._route_store = RouteStore()
        self._state_machine: Optional[NavigationStateMachine] = None
        self._trigger_engine = TriggerEngine(on_instruction)
        
        self._navigation_task: Optional[asyncio.Task] = None
        self._running = False
        self._destination = ""
        self._recalculation_count = 0
    
    def set_instruction_callback(self, callback: Callable[[str], None]) -> None:
        """Set the callback for navigation instructions."""
        self._trigger_engine.set_callback(callback)
    
    async def start_navigation(self, destination: str) -> bool:
        """
        Start navigation to a destination.
        
        Args:
            destination: Destination address or place name
        
        Returns:
            True if navigation started successfully, False otherwise
        """
        try:
            # Get current position
            await self._gps_reader.start()
            current_pos = await self._gps_reader.get_position()
            
            if not current_pos:
                self._trigger_engine._on_instruction(
                    "Unable to get GPS position. Please ensure GPS is available."
                )
                return False
            
            # Fetch route
            route = self._route_fetcher.fetch_route(current_pos, destination)
            
            if not route.steps:
                self._trigger_engine._on_instruction(
                    f"Could not find a route to {destination}."
                )
                return False
            
            # Store route and initialize state
            self._route_store.load_route(route, destination)
            self._state_machine = NavigationStateMachine(self._route_store.state)
            self._destination = destination
            self._recalculation_count = 0
            
            # Announce navigation start
            self._trigger_engine.trigger_navigation_start(
                destination=destination,
                step_count=route.step_count,
                total_distance=route.total_distance_text,
                total_duration=route.total_duration_text
            )
            
            # Start navigation loop
            self._state_machine.start_navigation()
            self._running = True
            self._navigation_task = asyncio.create_task(self._navigation_loop())
            
            return True
            
        except Exception as e:
            self._trigger_engine._on_instruction(f"Navigation error: {str(e)}")
            return False
    
    async def stop_navigation(self) -> None:
        """Stop the current navigation."""
        self._running = False
        
        if self._navigation_task:
            self._navigation_task.cancel()
            try:
                await self._navigation_task
            except asyncio.CancelledError:
                pass
            self._navigation_task = None
        
        if self._state_machine:
            self._state_machine.stop_navigation()
        
        await self._gps_reader.stop()
        self._route_store.reset()
    
    async def _navigation_loop(self) -> None:
        """
        Main navigation loop running at 1 Hz.
        
        - Polls GPS position
        - Computes distance to current step
        - Triggers instructions based on thresholds
        - Advances steps when completed
        - Handles off-route conditions
        """
        while self._running and self._state_machine:
            try:
                # Get current position
                current_pos = await self._gps_reader.get_position()
                
                if not current_pos:
                    await asyncio.sleep(self.GPS_POLL_INTERVAL)
                    continue
                
                # Get current step
                current_step = self._route_store.get_current_step()
                
                if not current_step:
                    # No more steps - we've arrived
                    await self._handle_arrival()
                    break
                
                # Process position through state machine
                trigger, step_complete = self._state_machine.process_position(
                    current_pos, current_step
                )
                
                # Handle trigger if any
                if trigger:
                    self._trigger_engine.trigger_instruction(
                        step=current_step,
                        trigger_type=trigger,
                        step_progress=self._route_store.progress
                    )
                
                # Handle step completion
                if step_complete:
                    advanced = self._route_store.advance_step()
                    if not advanced:
                        # Reached final step
                        await self._handle_arrival()
                        break
                
                # Handle off-route condition
                if self._state_machine.is_off_route:
                    await self._handle_off_route(current_pos)
                
                await asyncio.sleep(self.GPS_POLL_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue navigation
                print(f"Navigation loop error: {e}")
                await asyncio.sleep(self.GPS_POLL_INTERVAL)
    
    async def _handle_arrival(self) -> None:
        """Handle arrival at destination."""
        if self._state_machine:
            self._state_machine.mark_arrived()
        
        self._trigger_engine.trigger_arrival(self._destination)
        self._running = False
        await self._gps_reader.stop()
    
    async def _handle_off_route(self, current_pos: Coordinate) -> None:
        """
        Handle off-route condition by recalculating the route.
        
        Args:
            current_pos: Current user position
        """
        if self._recalculation_count >= self.MAX_RECALCULATION_ATTEMPTS:
            self._trigger_engine._on_instruction(
                "Unable to find route. Please check your destination and try again."
            )
            await self.stop_navigation()
            return
        
        self._recalculation_count += 1
        self._trigger_engine.trigger_off_route()
        
        if self._state_machine:
            self._state_machine.request_recalculation()
        
        try:
            # Fetch new route from current position
            new_route = self._route_fetcher.fetch_route(current_pos, self._destination)
            
            if new_route.steps:
                self._route_store.load_route(new_route, self._destination)
                self._state_machine = NavigationStateMachine(self._route_store.state)
                self._state_machine.on_route_recalculated()
                
                self._trigger_engine.trigger_recalculation_complete(new_route.step_count)
            else:
                self._trigger_engine._on_instruction(
                    "Could not find a new route. Continuing with current directions."
                )
                if self._state_machine:
                    self._state_machine.on_route_recalculated()
                    
        except Exception as e:
            print(f"Route recalculation error: {e}")
            if self._state_machine:
                self._state_machine.on_route_recalculated()
    
    @property
    def is_navigating(self) -> bool:
        """Check if navigation is currently active."""
        return self._running and self._state_machine is not None
    
    @property
    def current_status(self) -> Optional[NavigationStatus]:
        """Get current navigation status."""
        if self._state_machine:
            return self._state_machine.status
        return None
    
    @property
    def progress(self) -> tuple[int, int]:
        """Get navigation progress as (current_step, total_steps)."""
        return self._route_store.progress
    
    def get_current_instruction(self) -> Optional[str]:
        """Get the instruction for the current step."""
        step = self._route_store.get_current_step()
        if step:
            return step.instruction
        return None
    
    def get_remaining_info(self) -> tuple[str, str, int, int]:
        """
        Get remaining distance and duration info.
        
        Returns:
            Tuple of (remaining_distance_text, remaining_duration_text, current_step, total_steps)
        """
        if not self._route_store.route:
            return ("unknown", "unknown", 0, 0)
        
        current, total = self._route_store.progress
        remaining_steps = self._route_store.get_remaining_steps()
        
        # Sum up remaining distance and duration
        remaining_distance = sum(step.distance_meters for step in remaining_steps)
        remaining_duration = sum(step.duration_seconds for step in remaining_steps)
        
        # Format for human readability
        if remaining_distance >= 1000:
            distance_text = f"{remaining_distance / 1000:.1f} km"
        else:
            distance_text = f"{int(remaining_distance)} meters"
        
        if remaining_duration >= 3600:
            hours = int(remaining_duration // 3600)
            mins = int((remaining_duration % 3600) // 60)
            duration_text = f"{hours} hour{'s' if hours > 1 else ''} {mins} minutes"
        elif remaining_duration >= 60:
            mins = int(remaining_duration // 60)
            duration_text = f"{mins} minute{'s' if mins > 1 else ''}"
        else:
            duration_text = f"{int(remaining_duration)} seconds"
        
        return (distance_text, duration_text, current, total)

