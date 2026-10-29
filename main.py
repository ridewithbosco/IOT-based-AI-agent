"""
RAVEN - AI Navigation Assistant (Terminal Version)

Architecture: LangGraph StateGraph
- Speech gating as graph node
- Conversation memory with checkpointing
- Conditional routing based on gate results
- Agent as commander, Navigation as autopilot

Flow:
    Audio → STT → LangGraph(speech_gate → route → agent/idle → response) → TTS
"""

import os
import sys
import asyncio
import logging
import threading
import signal
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("RAVEN")

# Global flag for graceful shutdown
_shutdown_flag = threading.Event()

# Import components
from stt2 import record_audio, transcribe_with_groq
from audio_manager import audio_manager, AudioPriority
from agent_graph import invoke_agent, agent_graph
from navigation import nav_manager
from speech_gate import speech_gate
from conversation_logger import init_logger
from cam import env_scanner


class RAVENAssistant:
    """
    RAVEN Voice Assistant with LangGraph StateGraph.
    
    Features:
    - LangGraph-based agent with memory
    - Speech gating integrated as graph node
    - Conversation persistence across turns
    - Navigation runs autonomously in background
    """
    
    def __init__(self, use_real_gps: bool = False, gps_port: str = "COM3"):
        """
        Initialize the RAVEN assistant.
        
        Args:
            use_real_gps: Use UART GPS hardware instead of mock
            gps_port: Serial port for GPS module
        """
        self.audio_file = "audio_question.mp3"
        self.running = False
        self.thread_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize conversation logger
        self.conv_logger = init_logger()
        logger.info(f"Conversation log: {self.conv_logger.log_path}")
        
        # Start audio manager
        audio_manager.start()
        
        # Configure navigation manager
        nav_manager.configure(
            use_real_gps=use_real_gps,
            gps_port=gps_port,
            on_instruction=self.on_navigation_instruction
        )
        
        logger.info("=" * 60)
        logger.info("RAVEN AI Navigation Assistant")
        logger.info("Architecture: LangGraph StateGraph with Memory")
        logger.info(f"Session: {self.thread_id}")
        logger.info(f"GPS Mode: {'UART Hardware' if use_real_gps else 'Mock/Simulation'}")
        logger.info("=" * 60)
    
    def speak(self, text: str, priority: AudioPriority = AudioPriority.NORMAL) -> None:
        """Queue text for TTS (non-blocking)."""
        if text:
            logger.info(f"[TTS:{priority.name}] {text}")
            audio_manager.speak(text, priority)
    
    def on_navigation_instruction(self, instruction: str) -> None:
        """Callback for autonomous navigation instructions."""
        logger.info(f"[AUTOPILOT] {instruction}")
        audio_manager.speak_navigation(instruction)
    
    async def run(self) -> None:
        """
        Main assistant loop using LangGraph.
        
        Flow:
        1. Record audio
        2. Transcribe (STT)
        3. Invoke LangGraph agent
        4. Speak response (if any)
        """
        self.running = True
        
        # Start continuous vision safety subsystem
        try:
            await env_scanner.start()
        except Exception as e:
            logger.error(f"Failed to start vision subsystem: {e}")
        
        
        print("\n" + "=" * 60)
        print("RAVEN - AI Navigation Assistant")
        print("    Powered by LangGraph StateGraph")
        print("=" * 60)
        print("Say 'Hey Raven' or 'Raven' to activate")
        print("Then: 'Navigate me to [destination]'")
        print("Or ask any question!")
        print("Say 'Goodbye' to exit")
        print("=" * 60)
        print("Listening for wake word...\n")
        
        # Initial message
        self.speak("RAVEN ready. Say 'Hey Raven' to begin.")
        await asyncio.sleep(0.5)
        
        while self.running:
            try:
                # Show status
                if speech_gate.is_activated:
                    if nav_manager.is_navigating:
                        logger.info(f"[ACTIVATED] Navigating to {nav_manager.current_destination}")
                    else:
                        logger.info("[ACTIVATED] Ready for command")
                else:
                    logger.info("[WAITING] Say 'Hey Raven' to activate")
                
                # Record audio (run in thread to prevent blocking vision/nav loops)
                await asyncio.to_thread(record_audio, file_path=self.audio_file)
                
                # Transcribe (run in thread)
                user_input = await asyncio.to_thread(transcribe_with_groq, self.audio_file)
                
                if not user_input or len(user_input.strip()) < 2:
                    continue
                
                logger.info(f"[HEARD] '{user_input}'")
                
                # Check for exit (handle locally)
                if "goodbye" in user_input.lower() and speech_gate.is_activated:
                    logger.info("[EXIT] Goodbye command received")
                    if nav_manager.is_navigating:
                        await nav_manager.stop_navigation()
                    self.speak("Goodbye! Stay safe.", AudioPriority.CRITICAL)
                    speech_gate.reset()
                    await asyncio.sleep(2)
                    break
                
                # === INVOKE LANGGRAPH AGENT ===
                logger.info("[LANGGRAPH] Processing...")
                
                response = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: invoke_agent(user_input, self.thread_id)
                )
                
                if response:
                    logger.info(f"[AGENT] {response}")
                    self.speak(response, AudioPriority.NORMAL)
                else:
                    logger.debug("No response (rejected by gate)")
                
                await asyncio.sleep(0.3)
                
            except KeyboardInterrupt:
                logger.info("[INTERRUPTED]")
                break
            except Exception as e:
                logger.error(f"[ERROR] {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Cleanup
        if nav_manager.is_navigating:
            await nav_manager.stop_navigation()
            
        await env_scanner.stop()
        
        audio_manager.stop()
        self.running = False
        logger.info("[STOPPED] RAVEN Assistant stopped")


async def main():
    """Main entry point."""
    use_real_gps = "--gps" in sys.argv or "-g" in sys.argv
    gps_port = "COM3" if os.name == 'nt' else "/dev/serial0"
    
    for arg in sys.argv:
        if arg.startswith("--port="):
            gps_port = arg.split("=")[1]
    
    assistant = RAVENAssistant(
        use_real_gps=use_real_gps,
        gps_port=gps_port
    )
    
    # Signal handler
    def signal_handler(signum, frame):
        logger.info("\nCtrl+C detected - shutting down...")
        _shutdown_flag.set()
        assistant.running = False
        
        # Release camera immediately
        try:
            from cam import env_scanner
            
            if hasattr(env_scanner, 'flush_logs'):
                env_scanner.flush_logs()
                logger.info("Vision logs saved.")
                
            if hasattr(env_scanner, 'cap') and env_scanner.cap is not None:
                env_scanner.cap.release()
                logger.info("Camera released.")
        except Exception as e:
            logger.error(f"Error releasing camera: {e}")
            
        try:
            audio_manager.stop()
        except:
            pass
        print("\nGoodbye!")
        os._exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await assistant.run()
    except KeyboardInterrupt:
        pass
    finally:
        if nav_manager.is_navigating:
            try:
                await nav_manager.stop_navigation()
            except:
                pass
        audio_manager.stop()


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║            🦅 RAVEN - AI Navigation Assistant            ║
    ║                                                          ║
    ║          Powered by LangGraph StateGraph                 ║
    ║          With conversation memory!                       ║
    ╚══════════════════════════════════════════════════════════╝
    
    Usage: python main.py [options]
    
    Options:
        --gps, -g       Use real GPS hardware
        --port=COMx     Specify GPS serial port
    
    How to use:
        1. Say "Hey Raven" to activate
        2. Ask anything or navigate somewhere
        3. Memory persists across the conversation!
        
    Press Ctrl+C to exit.
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except SystemExit:
        pass