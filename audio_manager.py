"""
Audio Manager - Priority-based TTS queue with concurrent playback.

Allows navigation instructions to interrupt or queue alongside agent responses.
Runs TTS in a background thread so the main loop isn't blocked.
"""

import os
import queue
import threading
import time
import logging
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional, Callable

import pygame
from gtts import gTTS

logger = logging.getLogger("RAVEN.Audio")


class AudioPriority(IntEnum):
    """Priority levels for audio playback."""
    LOW = 3          # Background info
    NORMAL = 2       # Agent responses
    HIGH = 1         # Navigation instructions
    CRITICAL = 0     # Warnings (off-route, arrival)


@dataclass
class AudioItem:
    """An item in the audio queue."""
    text: str
    priority: AudioPriority
    timestamp: float
    
    def __lt__(self, other):
        # Lower priority number = higher priority
        # If same priority, earlier timestamp wins
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


class AudioManager:
    """
    Manages TTS audio with priority queue and background playback.
    
    Features:
    - Non-blocking TTS (runs in background thread)
    - Priority queue (navigation > agent responses)
    - Can interrupt current playback for higher priority
    """
    
    _instance: Optional["AudioManager"] = None
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
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._current_priority: Optional[AudioPriority] = None
        self._interrupt_event = threading.Event()
        self._tts_file = "tts_output.mp3"
        self._tts_file_alt = "tts_output_alt.mp3"
        self._use_alt = False
        
        # Initialize pygame mixer
        pygame.mixer.init()
        
        logger.info("AudioManager initialized (singleton)")
    
    def start(self) -> None:
        """Start the background audio worker."""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("Audio worker started")
    
    def stop(self) -> None:
        """Stop the audio worker."""
        self._running = False
        self._interrupt_event.set()
        
        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)
        
        pygame.mixer.quit()
        logger.info("Audio worker stopped")
    
    def speak(self, text: str, priority: AudioPriority = AudioPriority.NORMAL) -> None:
        """
        Queue text for TTS playback.
        
        Args:
            text: Text to speak
            priority: Priority level (higher priority = plays sooner)
        """
        item = AudioItem(
            text=text,
            priority=priority,
            timestamp=time.time()
        )
        self._queue.put(item)
        
        # If higher priority than current, interrupt
        if self._current_priority is not None and priority < self._current_priority:
            logger.info(f"Interrupting for higher priority audio: {priority.name}")
            self._interrupt_event.set()
    
    def speak_navigation(self, text: str) -> None:
        """Queue navigation instruction (high priority)."""
        self.speak(text, AudioPriority.HIGH)
    
    def speak_agent(self, text: str) -> None:
        """Queue agent response (normal priority)."""
        self.speak(text, AudioPriority.NORMAL)
    
    def speak_critical(self, text: str) -> None:
        """Queue critical message (highest priority, interrupts everything)."""
        self.speak(text, AudioPriority.CRITICAL)
    
    def _worker_loop(self) -> None:
        """Background worker that processes the audio queue."""
        while self._running:
            try:
                # Wait for item with timeout
                try:
                    item = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                self._current_priority = item.priority
                self._interrupt_event.clear()
                
                logger.debug(f"Playing audio [{item.priority.name}]: {item.text[:50]}...")
                
                # Generate TTS
                tts_file = self._get_tts_file()
                self._generate_tts(item.text, tts_file)
                
                # Play audio
                self._play_audio(tts_file)
                
                self._current_priority = None
                self._queue.task_done()
                
            except Exception as e:
                logger.error(f"Audio worker error: {e}")
                self._current_priority = None
    
    def _get_tts_file(self) -> str:
        """Alternate between two TTS files to avoid file locking."""
        self._use_alt = not self._use_alt
        return self._tts_file_alt if self._use_alt else self._tts_file
    
    def _generate_tts(self, text: str, filepath: str) -> None:
        """Generate TTS audio file."""
        try:
            tts = gTTS(text=text, lang="en", tld="co.uk", slow=False)
            tts.save(filepath)
        except Exception as e:
            logger.error(f"TTS generation error: {e}")
    
    def _play_audio(self, filepath: str) -> None:
        """Play audio file with interrupt support."""
        try:
            if not os.path.exists(filepath):
                return
            
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            # Wait for playback with interrupt check
            while pygame.mixer.music.get_busy():
                if self._interrupt_event.is_set():
                    pygame.mixer.music.stop()
                    logger.info("Audio interrupted")
                    break
                time.sleep(0.05)
            
            pygame.mixer.music.unload()
            
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
    
    def clear_queue(self) -> None:
        """Clear all pending audio."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
    
    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self._current_priority is not None


# Global singleton instance
audio_manager = AudioManager()
