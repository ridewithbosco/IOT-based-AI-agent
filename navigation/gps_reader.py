"""
GPS Reader - Abstraction for GPS input sources.

Supports mock GPS for testing and UART GPS (NEO-6M/NEO-8M) for production.
"""

import asyncio
import re
from abc import ABC, abstractmethod
from typing import Optional, List, Callable
from .models import Coordinate


class GPSReader(ABC):
    """Abstract base class for GPS input sources."""
    
    @abstractmethod
    async def get_position(self) -> Optional[Coordinate]:
        """
        Get the current GPS position.
        
        Returns:
            Coordinate with current lat/lon, or None if no fix available
        """
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start the GPS reader."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the GPS reader."""
        pass


class MockGPSReader(GPSReader):
    """
    Mock GPS reader for testing and simulation.
    
    Can simulate movement along a predefined path or return static positions.
    """
    
    def __init__(
        self,
        waypoints: Optional[List[Coordinate]] = None,
        static_position: Optional[Coordinate] = None,
        update_interval: float = 1.0
    ):
        """
        Initialize mock GPS reader.
        
        Args:
            waypoints: List of coordinates to traverse (loops back to start)
            static_position: Single static position to return
            update_interval: Time in seconds between position updates
        """
        self._waypoints = waypoints or []
        self._static_position = static_position
        self._update_interval = update_interval
        self._current_index = 0
        self._running = False
        
        # Default to Kolkata coordinates if nothing provided
        if not self._waypoints and not self._static_position:
            self._static_position = Coordinate(22.5726, 88.3639)
    
    async def get_position(self) -> Optional[Coordinate]:
        """Get the current mock position."""
        if self._static_position:
            return self._static_position
        
        if self._waypoints:
            return self._waypoints[self._current_index]
        
        return None
    
    async def start(self) -> None:
        """Start the mock GPS reader."""
        self._running = True
        self._current_index = 0
    
    async def stop(self) -> None:
        """Stop the mock GPS reader."""
        self._running = False
    
    def advance(self) -> None:
        """Advance to the next waypoint (for simulation)."""
        if self._waypoints:
            self._current_index = (self._current_index + 1) % len(self._waypoints)
    
    def set_position(self, coord: Coordinate) -> None:
        """Set a specific position (for testing)."""
        self._static_position = coord
        self._waypoints = []


class UARTGPSReader(GPSReader):
    """
    UART GPS reader for NEO-6M/NEO-8M GPS modules.
    
    Parses NMEA sentences from the GPS module via serial port.
    """
    
    def __init__(
        self,
        port: str = None,
        baudrate: int = 9600,
        timeout: float = 1.0
    ):
        """
        Initialize UART GPS reader.
        
        Args:
            port: Serial port name (e.g., "COM3" on Windows, "/dev/serial0" on Linux). If None, it detects OS automatically.
            baudrate: Serial baudrate (default 9600 for NEO-6M/NEO-8M)
            timeout: Serial read timeout in seconds
        """
        import os
        if port is None:
            port = "COM3" if os.name == 'nt' else "/dev/serial0"
            
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial = None
        self._running = False
        self._last_position: Optional[Coordinate] = None
        self._read_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the UART GPS reader."""
        try:
            import serial
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                timeout=self._timeout
            )
            self._running = True
            # Start background reading task
            self._read_task = asyncio.create_task(self._read_loop())
        except ImportError:
            raise RuntimeError("pyserial is required for UART GPS. Install with: pip install pyserial")
        except Exception as e:
            raise RuntimeError(f"Failed to open GPS serial port {self._port}: {e}")
    
    async def stop(self) -> None:
        """Stop the UART GPS reader."""
        self._running = False
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        if self._serial and self._serial.is_open:
            self._serial.close()
            self._serial = None
    
    async def get_position(self) -> Optional[Coordinate]:
        """Get the last known GPS position."""
        return self._last_position
    
    async def _read_loop(self) -> None:
        """Background loop to read and parse NMEA sentences."""
        while self._running and self._serial and self._serial.is_open:
            try:
                # Run blocking I/O in executor to not block the event loop
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self._serial.readline
                )
                if line:
                    sentence = line.decode('ascii', errors='ignore').strip()
                    coord = self._parse_nmea(sentence)
                    if coord:
                        self._last_position = coord
            except Exception:
                # Continue reading on errors
                pass
            await asyncio.sleep(0.1)  # Small delay to prevent tight loop
    
    def _parse_nmea(self, sentence: str) -> Optional[Coordinate]:
        """
        Parse NMEA sentence to extract GPS coordinates.
        
        Supports GGA and RMC sentences which contain position data.
        
        Args:
            sentence: NMEA sentence string
        
        Returns:
            Coordinate if valid position found, None otherwise
        """
        if not sentence.startswith('$'):
            return None
        
        # Remove checksum if present
        if '*' in sentence:
            sentence = sentence.split('*')[0]
        
        parts = sentence.split(',')
        if len(parts) < 6:
            return None
        
        sentence_type = parts[0]
        
        try:
            if sentence_type in ('$GPGGA', '$GNGGA'):
                # GGA - Global Positioning System Fix Data
                # Format: $GPGGA,time,lat,N/S,lon,E/W,quality,...
                if len(parts) >= 7 and parts[2] and parts[4]:
                    lat = self._parse_nmea_coord(parts[2], parts[3])
                    lon = self._parse_nmea_coord(parts[4], parts[5])
                    if lat and lon:
                        return Coordinate(lat=lat, lon=lon)
            
            elif sentence_type in ('$GPRMC', '$GNRMC'):
                # RMC - Recommended Minimum Specific GPS/Transit Data
                # Format: $GPRMC,time,status,lat,N/S,lon,E/W,...
                if len(parts) >= 7 and parts[3] and parts[5]:
                    status = parts[2]
                    if status == 'A':  # A = Active (valid fix)
                        lat = self._parse_nmea_coord(parts[3], parts[4])
                        lon = self._parse_nmea_coord(parts[5], parts[6])
                        if lat and lon:
                            return Coordinate(lat=lat, lon=lon)
        except (ValueError, IndexError):
            pass
        
        return None
    
    @staticmethod
    def _parse_nmea_coord(value: str, direction: str) -> Optional[float]:
        """
        Parse NMEA coordinate value to decimal degrees.
        
        NMEA format: DDDMM.MMMM where DDD is degrees and MM.MMMM is minutes
        
        Args:
            value: Coordinate value string (e.g., "2234.3578")
            direction: Direction character (N, S, E, W)
        
        Returns:
            Decimal degrees, or None if invalid
        """
        if not value or not direction:
            return None
        
        try:
            # Determine number of degree digits (2 for lat, 3 for lon)
            if direction in ('N', 'S'):
                deg_digits = 2
            else:
                deg_digits = 3
            
            degrees = float(value[:deg_digits])
            minutes = float(value[deg_digits:])
            decimal = degrees + (minutes / 60.0)
            
            # Apply direction
            if direction in ('S', 'W'):
                decimal = -decimal
            
            return decimal
        except (ValueError, IndexError):
            return None
