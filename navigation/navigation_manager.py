"""
Navigation Manager - Singleton manager for autonomous navigation execution.

This module provides the bridge between the AI Agent (commander) and the
Navigation Engine (autopilot). The agent issues commands, the manager executes.

Architecture:
    User Voice → Agent → Command Tool → NavigationManager → Navigation Engine
    
The agent NEVER receives navigation steps, coordinates, or route geometry.
It only receives status confirmations.
"""

import asyncio
import threading
import logging
from typing import Optional, Callable
from enum import Enum, auto

from navigation import (
    NavigationController,
    MockGPSReader,
    UARTGPSReader,
    Coordinate,
    NavigationStatus,
)

logger = logging.getLogger("RAVEN.NavManager")


class NavigationCommandResult(Enum):
    """Results from navigation commands."""
    SUCCESS = auto()
    ALREADY_NAVIGATING = auto()
    NOT_NAVIGATING = auto()
    ROUTE_NOT_FOUND = auto()
    GPS_ERROR = auto()
    ERROR = auto()


class NavigationManager:
    """
    Singleton manager for autonomous navigation.
    
    The agent issues commands to this manager, which then controls
    the navigation engine autonomously. The agent remains passive
    during navigation execution.
    
    Commands:
        - start_navigation(destination) -> Starts autonomous navigation
        - stop_navigation() -> Stops current navigation
        - query_status() -> Returns current navigation status
    """
    
    _instance: Optional["NavigationManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._controller: Optional[NavigationController] = None
        self._navigation_loop_task: Optional[asyncio.Task] = None
        self._current_destination: str = ""
        self._is_navigating: bool = False
        self._use_real_gps: bool = False
        self._gps_port: str = "COM3"
        self._on_instruction: Optional[Callable[[str], None]] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        
        logger.info("NavigationManager initialized (singleton)")
    
    def configure(
        self,
        use_real_gps: bool = False,
        gps_port: str = "COM3",
        on_instruction: Optional[Callable[[str], None]] = None
    ) -> None:
        """
        Configure the navigation manager.
        
        Args:
            use_real_gps: Use UART GPS hardware instead of mock
            gps_port: Serial port for GPS module
            on_instruction: Callback for navigation instructions (TTS)
        """
        self._use_real_gps = use_real_gps
        self._gps_port = gps_port
        self._on_instruction = on_instruction
        logger.info(f"NavigationManager configured: GPS={'UART' if use_real_gps else 'Mock'}")
    
    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for async operations."""
        self._event_loop = loop
    
    async def start_navigation(self, destination: str) -> tuple[NavigationCommandResult, str]:
        """
        Start autonomous navigation to a destination.
        
        This is the ONLY method the agent should call to begin navigation.
        After calling this, the navigation engine runs autonomously.
        
        Args:
            destination: Destination address or place name
            
        Returns:
            Tuple of (result_code, message)
        """
        if self._is_navigating:
            return (
                NavigationCommandResult.ALREADY_NAVIGATING,
                f"Already navigating to {self._current_destination}. Say 'stop navigation' first."
            )
        
        logger.info(f"[COMMAND] START_NAVIGATION: {destination}")
        
        try:
            # Create GPS reader
            if self._use_real_gps:
                gps_reader = UARTGPSReader(port=self._gps_port)
            else:
                gps_reader = MockGPSReader(
                    static_position=Coordinate(22.5726, 88.3639)
                )
            
            # Create controller
            self._controller = NavigationController(
                gps_reader=gps_reader,
                on_instruction=self._on_instruction
            )
            
            # Start navigation
            success = await self._controller.start_navigation(destination)
            
            if success:
                self._is_navigating = True
                self._current_destination = destination
                logger.info(f"[COMMAND] Navigation started to: {destination}")
                return (
                    NavigationCommandResult.SUCCESS,
                    f"Navigation started to {destination}. I'll guide you along the way."
                )
            else:
                return (
                    NavigationCommandResult.ROUTE_NOT_FOUND,
                    f"Could not find a route to {destination}. Please try a different destination."
                )
                
        except Exception as e:
            logger.error(f"[COMMAND] Navigation start error: {e}")
            return (
                NavigationCommandResult.ERROR,
                f"Navigation error: {str(e)}"
            )
    
    async def stop_navigation(self) -> tuple[NavigationCommandResult, str]:
        """
        Stop the current navigation.
        
        Args: None
        
        Returns:
            Tuple of (result_code, message)
        """
        if not self._is_navigating:
            return (
                NavigationCommandResult.NOT_NAVIGATING,
                "No active navigation to stop."
            )
        
        logger.info("[COMMAND] STOP_NAVIGATION")
        
        try:
            if self._controller:
                await self._controller.stop_navigation()
            
            destination = self._current_destination
            self._is_navigating = False
            self._current_destination = ""
            self._controller = None
            
            logger.info("[COMMAND] Navigation stopped")
            return (
                NavigationCommandResult.SUCCESS,
                f"Navigation to {destination} has been stopped."
            )
            
        except Exception as e:
            logger.error(f"[COMMAND] Navigation stop error: {e}")
            return (
                NavigationCommandResult.ERROR,
                f"Error stopping navigation: {str(e)}"
            )
    
    def query_status(self) -> tuple[NavigationCommandResult, str]:
        """
        Query the current navigation status.
        
        This returns a human-readable status including:
        - Destination
        - Progress (step X of Y)
        - Remaining distance and time
        
        The agent does NOT receive coordinates or route geometry.
        
        Returns:
            Tuple of (result_code, status_message)
        """
        logger.info("[COMMAND] QUERY_STATUS")
        
        if not self._is_navigating:
            return (
                NavigationCommandResult.NOT_NAVIGATING,
                "No active navigation. Where would you like to go?"
            )
        
        if not self._controller:
            return (
                NavigationCommandResult.ERROR,
                "Navigation state error. Please restart navigation."
            )
        
        try:
            status = self._controller.current_status
            
            # Get remaining distance and time
            distance, duration, current, total = self._controller.get_remaining_info()
            
            if status == NavigationStatus.NAVIGATING:
                current_instruction = self._controller.get_current_instruction()
                instruction_part = f" Your immediate next direction is: {current_instruction}." if current_instruction else ""
                
                message = (
                    f"You are navigating to {self._current_destination}. "
                    f"Currently on step {current} of {total}. "
                    f"About {distance} remaining, approximately {duration} to go."
                    f"{instruction_part}"
                )
            elif status == NavigationStatus.ARRIVED:
                message = f"You have arrived at {self._current_destination}."
            elif status == NavigationStatus.OFF_ROUTE:
                message = "You appear to be off route. I'm recalculating the route."
            elif status == NavigationStatus.RECALCULATING:
                message = "Recalculating route, please wait."
            else:
                message = f"Navigation active to {self._current_destination}."
            
            return (NavigationCommandResult.SUCCESS, message)
            
        except Exception as e:
            logger.error(f"[COMMAND] Status query error: {e}")
            return (
                NavigationCommandResult.ERROR,
                f"Error querying status: {str(e)}"
            )
    
    @property
    def is_navigating(self) -> bool:
        """Check if navigation is currently active."""
        return self._is_navigating
    
    @property
    def current_destination(self) -> str:
        """Get the current destination (empty if not navigating)."""
        return self._current_destination


# Global singleton instance
nav_manager = NavigationManager()
