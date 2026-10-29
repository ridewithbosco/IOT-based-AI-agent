"""
Tests for the navigation engine components.
"""

import sys
import os

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from navigation.models import Coordinate, NavigationStep, NavigationState, TriggerType, NavigationStatus
from navigation.haversine import haversine_distance, is_within_distance, bearing_between


def test_coordinate_validation():
    """Test Coordinate validation."""
    print("Testing Coordinate validation...")
    
    # Valid coordinates
    c1 = Coordinate(22.5726, 88.3639)
    assert c1.lat == 22.5726
    assert c1.lon == 88.3639
    print("  ✓ Valid coordinates work")
    
    # Invalid latitude
    try:
        Coordinate(91.0, 0.0)
        assert False, "Should have raised ValueError"
    except ValueError:
        print("  ✓ Invalid latitude rejected")
    
    # Invalid longitude
    try:
        Coordinate(0.0, 181.0)
        assert False, "Should have raised ValueError"
    except ValueError:
        print("  ✓ Invalid longitude rejected")
    
    print("  ✓ All Coordinate tests passed\n")


def test_haversine_distance():
    """Test Haversine distance calculation."""
    print("Testing Haversine distance...")
    
    # Kolkata coordinates
    kolkata = Coordinate(22.5726, 88.3639)
    
    # Same point should be 0
    dist = haversine_distance(kolkata, kolkata)
    assert dist < 0.001, f"Same point should be ~0, got {dist}"
    print(f"  ✓ Same point distance: {dist:.6f}m")
    
    # Known distance: Kolkata to Delhi ~1,305 km
    delhi = Coordinate(28.6139, 77.2090)
    dist = haversine_distance(kolkata, delhi)
    expected_km = 1305
    actual_km = dist / 1000
    error_percent = abs(actual_km - expected_km) / expected_km * 100
    print(f"  ✓ Kolkata to Delhi: {actual_km:.1f} km (expected ~{expected_km} km, error: {error_percent:.1f}%)")
    assert error_percent < 5, "Distance error too large"
    
    # Short distance test
    nearby = Coordinate(22.5730, 88.3645)  # ~50-100m away
    dist = haversine_distance(kolkata, nearby)
    print(f"  ✓ Short distance: {dist:.1f}m")
    assert 50 < dist < 150
    
    print("  ✓ All Haversine tests passed\n")


def test_is_within_distance():
    """Test proximity check function."""
    print("Testing is_within_distance...")
    
    kolkata = Coordinate(22.5726, 88.3639)
    nearby = Coordinate(22.5728, 88.3641)  # ~25-35m away
    
    # Should be within 50m
    assert is_within_distance(kolkata, nearby, 50.0)
    print("  ✓ Within 50m returns True")
    
    # Should NOT be within 10m
    assert not is_within_distance(kolkata, nearby, 10.0)
    print("  ✓ Within 10m returns False")
    
    print("  ✓ All proximity tests passed\n")


def test_bearing():
    """Test bearing calculation."""
    print("Testing bearing calculation...")
    
    # Point directly north
    start = Coordinate(22.0, 88.0)
    north = Coordinate(23.0, 88.0)
    bearing = bearing_between(start, north)
    assert abs(bearing - 0) < 1 or abs(bearing - 360) < 1
    print(f"  ✓ Bearing to north: {bearing:.1f}° (expected ~0°)")
    
    # Point directly east
    east = Coordinate(22.0, 89.0)
    bearing = bearing_between(start, east)
    assert 89 < bearing < 91
    print(f"  ✓ Bearing to east: {bearing:.1f}° (expected ~90°)")
    
    # Point directly south
    south = Coordinate(21.0, 88.0)
    bearing = bearing_between(start, south)
    assert 179 < bearing < 181
    print(f"  ✓ Bearing to south: {bearing:.1f}° (expected ~180°)")
    
    print("  ✓ All bearing tests passed\n")


def test_navigation_step():
    """Test NavigationStep TTS generation."""
    print("Testing NavigationStep...")
    
    step = NavigationStep(
        index=0,
        instruction="Turn left onto Main Street",
        start_coord=Coordinate(22.5726, 88.3639),
        end_coord=Coordinate(22.5730, 88.3645),
        distance_meters=50.0,
        distance_text="50 m",
        duration_seconds=60,
        duration_text="1 min"
    )
    
    # Test PREPARE instruction
    prepare = step.get_tts_instruction(TriggerType.PREPARE)
    assert "50 m" in prepare
    assert "Turn left" in prepare
    print(f"  ✓ PREPARE: '{prepare}'")
    
    # Test EXECUTE instruction
    execute = step.get_tts_instruction(TriggerType.EXECUTE)
    assert "Now" in execute
    print(f"  ✓ EXECUTE: '{execute}'")
    
    # Test COMPLETED instruction
    completed = step.get_tts_instruction(TriggerType.COMPLETED)
    assert "completed" in completed.lower()
    print(f"  ✓ COMPLETED: '{completed}'")
    
    print("  ✓ All NavigationStep tests passed\n")


def test_navigation_state():
    """Test NavigationState operations."""
    print("Testing NavigationState...")
    
    state = NavigationState()
    assert state.status == NavigationStatus.IDLE
    assert state.current_step_index == 0
    print("  ✓ Initial state is IDLE at step 0")
    
    state.status = NavigationStatus.NAVIGATING
    state.current_step_index = 5
    state.total_steps = 10
    print("  ✓ State can be modified")
    
    state.reset()
    assert state.status == NavigationStatus.IDLE
    assert state.current_step_index == 0
    print("  ✓ Reset returns to initial state")
    
    print("  ✓ All NavigationState tests passed\n")


def run_all_tests():
    """Run all unit tests."""
    print("=" * 60)
    print("RAVEN Navigation Engine - Unit Tests")
    print("=" * 60 + "\n")
    
    test_coordinate_validation()
    test_haversine_distance()
    test_is_within_distance()
    test_bearing()
    test_navigation_step()
    test_navigation_state()
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
