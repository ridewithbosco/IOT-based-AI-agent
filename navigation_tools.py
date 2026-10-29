"""
Navigation Command Tools for AI Agent

These tools allow the AI agent to act as a "mission commander" that
issues high-level navigation commands. The agent NEVER receives
navigation steps, coordinates, or route geometry.

Commands:
    - start_navigation(destination) - Start autonomous navigation
    - stop_navigation() - Stop current navigation
    - query_navigation_status() - Get current status

Architecture:
    Agent calls tool → Tool calls NavigationManager → Manager controls engine
"""

import asyncio
from langchain_core.tools import tool
from navigation import nav_manager, NavigationCommandResult


def _run_async(coro):
    """Run async coroutine from sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop and loop.is_running():
        # We're in an async context, create a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


@tool
def start_navigation(destination: str) -> str:
    """
    Start autonomous navigation to a destination.
    
    Use this tool when the user wants to navigate somewhere.
    After calling this, navigation runs autonomously - you don't need to 
    manage it or provide step-by-step directions.
    
    Args:
        destination: The destination address or place name (e.g., "Central Station", 
                    "123 Main Street", "the nearest hospital")
    
    Returns:
        A confirmation message about navigation status.
        
    Examples:
        - "Navigate me to the airport" → start_navigation("the airport")
        - "Take me to Central Park" → start_navigation("Central Park")
        - "How do I get to the mall?" → start_navigation("the mall")
    """
    result, message = _run_async(nav_manager.start_navigation(destination))
    return message


@tool
def stop_navigation() -> str:
    """
    Stop the current navigation.
    
    Use this tool when the user wants to stop or cancel navigation.
    
    Returns:
        A confirmation message.
        
    Examples:
        - "Stop navigation"
        - "Cancel directions"
        - "I don't want to go there anymore"
    """
    result, message = _run_async(nav_manager.stop_navigation())
    return message


@tool
def query_navigation_status() -> str:
    """
    Query the current navigation status and immediate next direction.
    
    Use this tool when the user asks about their current navigation progress,
    how far they have left, OR when they ask which way to go next, what their 
    next turn is, or what direction to walk.
    
    Returns:
        Current navigation status (destination, progress, next immediate turn direction)
        
    Examples:
        - "Where am I going?"
        - "How far along am I?"
        - "Which way to go now?"
        - "What's my next turn?"
    """
    result, message = nav_manager.query_status()
    return message


@tool
def analyze_image(query: str) -> str:
    """
    Capture an image from the camera and analyze it with a query.
    
    Use this tool when the user asks about what's in front of them,
    wants to identify objects, read text, or understand their surroundings.
    
    Args:
        query: What to analyze about the image (e.g., "What do you see?",
               "Is there a door in front of me?", "Read the sign")
    
    Returns:
        Description of what's in the image based on the query.
        
    Examples:
        - "What's in front of me?" → analyze_image("Describe what you see")
        - "Is there anyone here?" → analyze_image("Are there any people visible?")
        - "Read that sign" → analyze_image("Read any text or signs visible")
    """
    from tools import analyze_image_with_query
    return analyze_image_with_query(query)


# Export all tools for the agent
NAVIGATION_TOOLS = [
    start_navigation,
    stop_navigation,
    query_navigation_status,
    analyze_image,
]
