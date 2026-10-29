"""
Haversine formula for calculating great-circle distances between GPS coordinates.
"""

import math
from .models import Coordinate


# Earth's radius in meters
EARTH_RADIUS_METERS = 6_371_000


def haversine_distance(coord1: Coordinate, coord2: Coordinate) -> float:
    """
    Calculate the great-circle distance between two points on Earth.
    
    Uses the Haversine formula which is accurate for most purposes,
    with typical error < 0.5% due to Earth's ellipsoid shape.
    
    Args:
        coord1: First coordinate (lat, lon)
        coord2: Second coordinate (lat, lon)
    
    Returns:
        Distance in meters between the two points.
    """
    # Convert to radians
    lat1 = math.radians(coord1.lat)
    lat2 = math.radians(coord2.lat)
    lon1 = math.radians(coord1.lon)
    lon2 = math.radians(coord2.lon)
    
    # Differences
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    # Haversine formula
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return EARTH_RADIUS_METERS * c


def is_within_distance(coord1: Coordinate, coord2: Coordinate, threshold_meters: float) -> bool:
    """
    Check if two coordinates are within a certain distance of each other.
    
    Args:
        coord1: First coordinate
        coord2: Second coordinate  
        threshold_meters: Distance threshold in meters
    
    Returns:
        True if distance <= threshold, False otherwise
    """
    return haversine_distance(coord1, coord2) <= threshold_meters


def bearing_between(coord1: Coordinate, coord2: Coordinate) -> float:
    """
    Calculate the initial bearing from coord1 to coord2.
    
    Args:
        coord1: Starting coordinate
        coord2: Destination coordinate
    
    Returns:
        Bearing in degrees (0-360), where 0 is North
    """
    lat1 = math.radians(coord1.lat)
    lat2 = math.radians(coord2.lat)
    dlon = math.radians(coord2.lon - coord1.lon)
    
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    
    bearing = math.atan2(x, y)
    return (math.degrees(bearing) + 360) % 360
