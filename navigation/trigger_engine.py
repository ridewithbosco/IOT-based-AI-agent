"""
Trigger Engine - Determines when to output navigation instructions.
"""

from typing import Optional, Callable
from .models import NavigationStep, TriggerType


class TriggerEngine:
    """
    Determines when to output navigation instructions.
    
    Formats TTS-ready instruction strings based on trigger type and step data.
    """
    
    def __init__(self, on_instruction: Optional[Callable[[str], None]] = None):
        """
        Initialize the trigger engine.
        
        Args:
            on_instruction: Callback function to receive instruction strings
        """
        self._on_instruction = on_instruction
    
    def set_callback(self, callback: Callable[[str], None]) -> None:
        """Set the instruction callback."""
        self._on_instruction = callback
    
    def trigger_instruction(
        self,
        step: NavigationStep,
        trigger_type: TriggerType,
        step_progress: tuple[int, int]
    ) -> str:
        """
        Generate and optionally output a navigation instruction.
        
        Args:
            step: Current navigation step
            trigger_type: Type of trigger (PREPARE, EXECUTE, COMPLETED)
            step_progress: Tuple of (current_step, total_steps)
        
        Returns:
            The formatted instruction string
        """
        instruction = self._format_instruction(step, trigger_type, step_progress)
        
        if self._on_instruction:
            self._on_instruction(instruction)
        
        return instruction
    
    def trigger_arrival(self, destination: str) -> str:
        """
        Generate arrival notification.
        
        Args:
            destination: Name of the destination
        
        Returns:
            The arrival instruction string
        """
        instruction = f"You have arrived at your destination: {destination}"
        
        if self._on_instruction:
            self._on_instruction(instruction)
        
        return instruction
    
    def trigger_off_route(self) -> str:
        """
        Generate off-route warning.
        
        Returns:
            The off-route warning string
        """
        instruction = "You appear to be off route. Recalculating directions."
        
        if self._on_instruction:
            self._on_instruction(instruction)
        
        return instruction
    
    def trigger_recalculation_complete(self, step_count: int) -> str:
        """
        Generate recalculation complete notification.
        
        Args:
            step_count: Number of steps in new route
        
        Returns:
            The notification string
        """
        instruction = f"New route calculated with {step_count} steps. Resuming navigation."
        
        if self._on_instruction:
            self._on_instruction(instruction)
        
        return instruction
    
    def trigger_navigation_start(
        self,
        destination: str,
        step_count: int,
        total_distance: str,
        total_duration: str
    ) -> str:
        """
        Generate navigation start announcement.
        
        Args:
            destination: Destination name
            step_count: Number of navigation steps
            total_distance: Human-readable total distance
            total_duration: Human-readable total duration
        
        Returns:
            The start announcement string
        """
        instruction = (
            f"Starting navigation to {destination}. "
            f"Route has {step_count} steps, {total_distance}, "
            f"approximately {total_duration}."
        )
        
        if self._on_instruction:
            self._on_instruction(instruction)
        
        return instruction
    
    def _format_instruction(
        self,
        step: NavigationStep,
        trigger_type: TriggerType,
        step_progress: tuple[int, int]
    ) -> str:
        """
        Format an instruction based on trigger type.
        
        Args:
            step: Navigation step
            trigger_type: Type of trigger
            step_progress: (current, total) step numbers
        
        Returns:
            Formatted instruction string
        """
        current, total = step_progress
        
        if trigger_type == TriggerType.PREPARE:
            # "In about 30 meters, turn left onto Main Street. Step 3 of 12."
            return (
                f"In about {step.distance_text}, {step.instruction}. "
                f"Step {current} of {total}."
            )
        
        elif trigger_type == TriggerType.EXECUTE:
            # "Now, turn left onto Main Street."
            maneuver_prefix = self._get_maneuver_prefix(step.maneuver)
            return f"{maneuver_prefix}{step.instruction}."
        
        elif trigger_type == TriggerType.COMPLETED:
            next_msg = "Preparing next direction." if current < total else "Approaching destination."
            return f"Direction completed. {next_msg}"
        
        return step.instruction
    
    @staticmethod
    def _get_maneuver_prefix(maneuver: Optional[str]) -> str:
        """Get an action prefix based on maneuver type."""
        if not maneuver:
            return "Now, "
        
        maneuver_prefixes = {
            "turn-left": "Turn left now. ",
            "turn-right": "Turn right now. ",
            "turn-slight-left": "Bear left now. ",
            "turn-slight-right": "Bear right now. ",
            "turn-sharp-left": "Sharp left now. ",
            "turn-sharp-right": "Sharp right now. ",
            "straight": "Continue straight. ",
            "uturn-left": "Make a U-turn. ",
            "uturn-right": "Make a U-turn. ",
            "roundabout-left": "At the roundabout, go left. ",
            "roundabout-right": "At the roundabout, go right. ",
            "merge": "Merge now. ",
            "fork-left": "Keep left at the fork. ",
            "fork-right": "Keep right at the fork. ",
        }
        
        return maneuver_prefixes.get(maneuver, "Now, ")
