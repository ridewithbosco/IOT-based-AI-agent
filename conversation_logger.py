"""
Conversation History Logger - Persists chat history to JSON files.

Stores each conversation turn with timestamp, user input, and agent response.
"""

import json
import os
from datetime import datetime
from typing import Optional
from pathlib import Path


class ConversationLogger:
    """
    Logs conversation history to a JSON file.
    
    Each session creates a new log file.
    All turns are appended to maintain history.
    """
    
    def __init__(self, log_dir: str = "conversation_logs"):
        """
        Initialize the logger.
        
        Args:
            log_dir: Directory to store log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create session file
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"session_{self.session_id}.json"
        
        # Initialize with metadata
        self._history = {
            "session_id": self.session_id,
            "started_at": datetime.now().isoformat(),
            "turns": []
        }
        self._save()
    
    def log_turn(
        self,
        user_input: str,
        gate_result: str,
        agent_response: Optional[str] = None,
        is_navigation: bool = False,
        destination: Optional[str] = None
    ) -> None:
        """
        Log a conversation turn.
        
        Args:
            user_input: What the user said (STT output)
            gate_result: Speech gate result (VALID, REJECTED, etc.)
            agent_response: Agent's response (if any)
            is_navigation: Whether navigation is active
            destination: Current navigation destination
        """
        turn = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "gate_result": gate_result,
            "agent_response": agent_response,
            "is_navigation": is_navigation,
            "destination": destination
        }
        
        self._history["turns"].append(turn)
        self._save()
    
    def _save(self) -> None:
        """Save history to file."""
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self._history, f, indent=2, ensure_ascii=False)
    
    def get_history(self) -> list:
        """Get all conversation turns."""
        return self._history["turns"]
    
    def get_last_n_turns(self, n: int = 5) -> list:
        """Get the last N turns."""
        return self._history["turns"][-n:]
    
    @property
    def turn_count(self) -> int:
        """Get number of turns in this session."""
        return len(self._history["turns"])
    
    @property
    def log_path(self) -> str:
        """Get path to the log file."""
        return str(self.log_file)


# Global logger instance
conversation_logger: Optional[ConversationLogger] = None


def init_logger(log_dir: str = "conversation_logs") -> ConversationLogger:
    """Initialize the global conversation logger."""
    global conversation_logger
    conversation_logger = ConversationLogger(log_dir)
    return conversation_logger


def get_logger() -> Optional[ConversationLogger]:
    """Get the global logger instance."""
    return conversation_logger
