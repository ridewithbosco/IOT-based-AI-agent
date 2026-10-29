"""
Speech Gate - Wake-word detection and pre-agent intent filtering.

Prevents background noise and ambient speech from invoking the LLM agent.
The agent is ONLY invoked after explicit activation.

Activation Methods:
1. Wake-word: "Hey Raven" or "Raven"
2. Push-to-talk: External trigger (keyboard/button)

Pre-Agent Filters:
1. Minimum speech length
2. Keyword presence check
3. Noise rejection (too short, only filler words)
"""

import re
import logging
from typing import Optional, Tuple
from enum import Enum, auto

logger = logging.getLogger("RAVEN.SpeechGate")


class SpeechGateResult(Enum):
    """Result of speech gate evaluation."""
    WAKE_WORD_DETECTED = auto()    # Wake word heard, ready for command
    COMMAND_VALID = auto()          # Valid command after wake word
    NOISE_REJECTED = auto()         # Background noise, reject
    TOO_SHORT = auto()              # Speech too short
    NO_INTENT = auto()              # No recognizable intent
    FILLER_ONLY = auto()            # Only filler words detected


class SpeechGate:
    """
    Speech gating layer that controls when the LLM agent is invoked.
    
    Flow:
        STT Output → SpeechGate.evaluate() → PASS/REJECT
        
    Only PASS results should invoke the agent.
    """
    
    # Wake words (case-insensitive) - includes common STT mishearings
    WAKE_WORDS = [
        "hey raven",
        "raven",
        "ok raven",
        "okay raven",
        # Common STT mishearings
        "hey revan",
        "revan",
        "hey ravin",
        "ravin",
        "hey raving",
        "hey haven",
    ]
    
    # Minimum characters for valid speech (filters noise)
    MIN_SPEECH_LENGTH = 5
    
    # Filler words to ignore if they appear alone
    FILLER_WORDS = {
        "um", "uh", "hmm", "hm", "ah", "eh", "oh", "mm",
        "yeah", "yes", "no", "okay", "ok", "alright",
        "so", "well", "like", "you know", "i mean",
    }
    
    # Navigation keywords (for quick intent check)
    NAVIGATION_KEYWORDS = {
        "navigate", "navigation", "directions", "take me", "guide me",
        "how do i get", "how to go", "route", "way to",
        "stop navigation", "stop navigating", "cancel navigation",
        "where am i", "how far", "status", "destination",
    }
    
    # General command keywords
    COMMAND_KEYWORDS = {
        "goodbye", "exit", "quit", "stop", "help",
        "what", "who", "where", "when", "why", "how",
        "tell me", "can you", "please", "could you",
    }
    
    def __init__(self):
        """Initialize the speech gate."""
        self._activated = False  # True after wake word detected
        self._last_wake_time = 0
        self._activation_timeout = 30.0  # seconds before requiring wake word again
    
    def evaluate(self, text: str) -> Tuple[SpeechGateResult, Optional[str]]:
        """
        Evaluate speech text and determine if agent should be invoked.
        
        Args:
            text: Transcribed speech text
            
        Returns:
            Tuple of (result, processed_text)
            - processed_text is the command text if valid, None otherwise
        """
        if not text:
            return (SpeechGateResult.NOISE_REJECTED, None)
        
        text = text.strip()
        text_lower = text.lower()
        
        # 1. Check minimum length
        if len(text) < self.MIN_SPEECH_LENGTH:
            logger.debug(f"Rejected: too short ({len(text)} chars)")
            return (SpeechGateResult.TOO_SHORT, None)
        
        # 2. Check if it's only filler words
        if self._is_only_filler(text_lower):
            logger.debug(f"Rejected: filler words only")
            return (SpeechGateResult.FILLER_ONLY, None)
        
        # 3. Check for wake word
        wake_result = self._check_wake_word(text_lower)
        if wake_result:
            command = wake_result  # Text after wake word
            if command and len(command.strip()) > 3:
                # Wake word + command in same utterance
                logger.info(f"Wake word + command: '{command}'")
                self._activated = True
                return (SpeechGateResult.COMMAND_VALID, command.strip())
            else:
                # Just wake word, waiting for command
                logger.info("Wake word detected, waiting for command")
                self._activated = True
                return (SpeechGateResult.WAKE_WORD_DETECTED, None)
        
        # 4. If already activated, validate command
        if self._activated:
            if self._has_valid_intent(text_lower):
                logger.info(f"Command accepted: '{text}'")
                # Keep activated for follow-up commands
                return (SpeechGateResult.COMMAND_VALID, text)
            else:
                logger.debug(f"No valid intent detected")
                return (SpeechGateResult.NO_INTENT, None)
        
        # 5. Not activated and no wake word - reject
        logger.debug(f"Rejected: no wake word and not activated")
        return (SpeechGateResult.NOISE_REJECTED, None)
    
    def _check_wake_word(self, text_lower: str) -> Optional[str]:
        """
        Check if text starts with a wake word.
        
        Returns:
            Text after the wake word, or None if no wake word found
        """
        for wake in self.WAKE_WORDS:
            if text_lower.startswith(wake):
                # Return text after wake word
                remainder = text_lower[len(wake):].strip()
                # Remove common connectors
                for connector in [",", ".", "!", "?"]:
                    remainder = remainder.lstrip(connector).strip()
                return remainder
            
            # Check if wake word is anywhere in short phrases
            if len(text_lower) < 30 and wake in text_lower:
                idx = text_lower.find(wake)
                remainder = text_lower[idx + len(wake):].strip()
                return remainder
        
        return None
    
    def _is_only_filler(self, text_lower: str) -> bool:
        """Check if text contains only filler words."""
        # Remove punctuation
        cleaned = re.sub(r'[^\w\s]', '', text_lower)
        words = cleaned.split()
        
        if not words:
            return True
        
        # Check if all words are fillers
        non_filler_count = sum(1 for w in words if w not in self.FILLER_WORDS)
        return non_filler_count == 0
    
    def _has_valid_intent(self, text_lower: str) -> bool:
        """
        Check if text contains recognizable intent keywords.
        
        This is a lightweight check to filter obvious noise.
        The LLM will do deeper understanding.
        """
        # Check navigation keywords
        for keyword in self.NAVIGATION_KEYWORDS:
            if keyword in text_lower:
                return True
        
        # Check command keywords
        for keyword in self.COMMAND_KEYWORDS:
            if keyword in text_lower:
                return True
        
        # Check for question patterns
        if text_lower.endswith('?'):
            return True
        
        # Check minimum word count for non-keyword speech
        words = text_lower.split()
        if len(words) >= 3:
            # Allow longer utterances even without keywords
            return True
        
        return False
    
    def reset(self) -> None:
        """Reset activation state (require wake word again)."""
        self._activated = False
        logger.info("Speech gate reset, wake word required")
    
    def force_activate(self) -> None:
        """Force activation (for push-to-talk mode)."""
        self._activated = True
        logger.info("Speech gate force-activated (push-to-talk)")
    
    @property
    def is_activated(self) -> bool:
        """Check if the gate is currently activated."""
        return self._activated


# Global singleton
speech_gate = SpeechGate()
