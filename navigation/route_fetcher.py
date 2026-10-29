"""
Route fetcher - Fetches and parses routes from Google Maps Directions API.
"""

import os
import re
import requests
from typing import Optional
from dotenv import load_dotenv

from .models import Coordinate, NavigationStep, RouteInfo


load_dotenv()


class RouteFetcher:
    """Fetches and parses routes from Google Maps Directions API."""
    
    DIRECTIONS_API_URL = "https://maps.googleapis.com/maps/api/directions/json"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the route fetcher.
        
        Args:
            api_key: Google Maps API key. If not provided, reads from GOOGLE_MAPS_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        if not self.api_key:
            raise ValueError("Google Maps API key not found. Set GOOGLE_MAPS_API_KEY environment variable.")
    
    def fetch_route(
        self,
        origin: Coordinate,
        destination: str,
        mode: str = "walking"
    ) -> RouteInfo:
        """
        Fetch a route from the Google Maps Directions API.
        
        Args:
            origin: Starting coordinate
            destination: Destination address or place name
            mode: Travel mode - "walking", "driving", "bicycling", "transit"
        
        Returns:
            RouteInfo containing parsed steps and route metadata
            
        Raises:
            RuntimeError: If API call fails or returns no routes
        """
        params = {
            "origin": f"{origin.lat},{origin.lon}",
            "destination": destination,
            "mode": mode,
            "key": self.api_key,
        }
        
        response = requests.get(self.DIRECTIONS_API_URL, params=params)
        data = response.json()
        
        status = data.get("status")
        if status != "OK":
            error_message = data.get("error_message", f"API returned status: {status}")
            raise RuntimeError(f"Directions API error: {error_message}")
        
        routes = data.get("routes", [])
        if not routes:
            raise RuntimeError("No routes found for the given origin and destination.")
        
        return self._parse_route(routes[0])
    
    def _parse_route(self, route_data: dict) -> RouteInfo:
        """Parse a route from API response into RouteInfo."""
        leg = route_data["legs"][0]  # We only handle single-leg routes
        
        steps = []
        for idx, step_data in enumerate(leg["steps"]):
            step = self._parse_step(idx, step_data)
            steps.append(step)
        
        return RouteInfo(
            steps=steps,
            total_distance_meters=leg["distance"]["value"],
            total_distance_text=leg["distance"]["text"],
            total_duration_seconds=leg["duration"]["value"],
            total_duration_text=leg["duration"]["text"],
            start_address=leg.get("start_address", ""),
            end_address=leg.get("end_address", ""),
        )
    
    def _parse_step(self, index: int, step_data: dict) -> NavigationStep:
        """Parse a single step from API response."""
        # Strip HTML tags from instruction
        html_instruction = step_data.get("html_instructions", "")
        instruction = self._strip_html(html_instruction)
        
        # Parse coordinates
        start_loc = step_data["start_location"]
        end_loc = step_data["end_location"]
        
        return NavigationStep(
            index=index,
            instruction=instruction,
            start_coord=Coordinate(lat=start_loc["lat"], lon=start_loc["lng"]),
            end_coord=Coordinate(lat=end_loc["lat"], lon=end_loc["lng"]),
            distance_meters=step_data["distance"]["value"],
            distance_text=step_data["distance"]["text"],
            duration_seconds=step_data["duration"]["value"],
            duration_text=step_data["duration"]["text"],
            polyline=step_data.get("polyline", {}).get("points"),
            maneuver=step_data.get("maneuver"),
        )
    
    @staticmethod
    def _strip_html(html_text: str) -> str:
        """Remove HTML tags from text."""
        # Replace common HTML entities
        text = html_text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Clean up whitespace
        text = " ".join(text.split())
        return text
