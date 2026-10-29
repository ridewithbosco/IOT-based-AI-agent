"""
Navigation Demo Script - Demonstrates the continuous navigation engine.

This script shows how to use the navigation system with:
- Mock GPS for simulation
- Real TTS output via gTTS
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from navigation import (
    NavigationController,
    MockGPSReader,
    UARTGPSReader,
    Coordinate,
)
from text_to_speech import text_to_speech_with_gtts


class NavigationDemo:
    """Demo class for running the navigation engine."""
    
    def __init__(self, use_tts: bool = True, use_real_gps: bool = False):
        """
        Initialize the demo.
        
        Args:
            use_tts: Whether to use TTS for audio output
            use_real_gps: Whether to use real UART GPS (requires hardware)
        """
        self.use_tts = use_tts
        self.use_real_gps = use_real_gps
        self.controller: NavigationController = None
        
    def on_instruction(self, instruction: str) -> None:
        """
        Handle navigation instructions.
        
        Args:
            instruction: The navigation instruction text
        """
        print(f"\n🔊 {instruction}")
        
        if self.use_tts:
            try:
                text_to_speech_with_gtts(instruction, "nav_instruction.mp3")
            except Exception as e:
                print(f"TTS error: {e}")
    
    async def run_simulation(self, destination: str) -> None:
        """
        Run a navigation simulation with mock GPS.
        
        Args:
            destination: Destination to navigate to
        """
        print("=" * 60)
        print("RAVEN Navigation Engine - Simulation Mode")
        print("=" * 60)
        
        # Create mock GPS reader with static position (Kolkata)
        gps_reader = MockGPSReader(
            static_position=Coordinate(22.5726, 88.3639)
        )
        
        # Create navigation controller
        self.controller = NavigationController(
            gps_reader=gps_reader,
            on_instruction=self.on_instruction
        )
        
        print(f"\n📍 Starting navigation to: {destination}")
        print("-" * 60)
        
        # Start navigation
        success = await self.controller.start_navigation(destination)
        
        if not success:
            print("❌ Failed to start navigation")
            return
        
        # In simulation mode, we run for a limited time
        # In real use, the loop runs until arrival or cancellation
        print("\n⏳ Navigation running... (Press Ctrl+C to stop)")
        
        try:
            # Run for 30 seconds in demo mode
            for i in range(30):
                if not self.controller.is_navigating:
                    break
                
                current, total = self.controller.progress
                status = self.controller.current_status
                print(f"\r📡 Step {current}/{total} | Status: {status.name}", end="", flush=True)
                
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n⚠️ Navigation cancelled by user")
        
        await self.controller.stop_navigation()
        print("\n✅ Navigation stopped")
    
    async def run_with_real_gps(self, destination: str, port: str = "COM3") -> None:
        """
        Run navigation with real UART GPS.
        
        Args:
            destination: Destination to navigate to
            port: Serial port for GPS module
        """
        print("=" * 60)
        print("RAVEN Navigation Engine - Live GPS Mode")
        print(f"GPS Port: {port}")
        print("=" * 60)
        
        try:
            gps_reader = UARTGPSReader(port=port)
        except Exception as e:
            print(f"❌ Failed to initialize GPS: {e}")
            return
        
        self.controller = NavigationController(
            gps_reader=gps_reader,
            on_instruction=self.on_instruction
        )
        
        print(f"\n📍 Starting navigation to: {destination}")
        print("🛰️ Waiting for GPS fix...")
        print("-" * 60)
        
        success = await self.controller.start_navigation(destination)
        
        if not success:
            print("❌ Failed to start navigation")
            return
        
        print("\n🚶 Navigation active. Walk towards your destination.")
        print("   Press Ctrl+C to stop.\n")
        
        try:
            while self.controller.is_navigating:
                current, total = self.controller.progress
                status = self.controller.current_status
                print(f"\r📡 Step {current}/{total} | Status: {status.name}", end="", flush=True)
                await asyncio.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\n\n⚠️ Navigation cancelled by user")
        
        await self.controller.stop_navigation()
        print("\n✅ Navigation complete")


async def main():
    """Main entry point."""
    # Default destination
    destination = "Techno Main Saltlake"
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        destination = " ".join(sys.argv[1:])
    
    # Check for GPS mode flag
    use_real_gps = "--gps" in sys.argv or "-g" in sys.argv
    no_tts = "--no-tts" in sys.argv
    
    # Create and run demo
    demo = NavigationDemo(use_tts=not no_tts, use_real_gps=use_real_gps)
    
    if use_real_gps:
        # Find GPS port from args or use default
        port = "COM3"  # Default Windows port
        for arg in sys.argv:
            if arg.startswith("--port="):
                port = arg.split("=")[1]
        
        await demo.run_with_real_gps(destination, port)
    else:
        await demo.run_simulation(destination)


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                    RAVEN Navigation                      ║
    ║           Continuous Navigation Engine Demo              ║
    ╚══════════════════════════════════════════════════════════╝
    
    Usage: python run_navigation.py [destination] [options]
    
    Options:
        --gps, -g       Use real GPS hardware (UART)
        --port=COMx     Specify GPS serial port (default: COM3)
        --no-tts        Disable text-to-speech output
    
    Examples:
        python run_navigation.py "Central Park"
        python run_navigation.py "Airport" --gps --port=COM4
    """)
    
    asyncio.run(main())
