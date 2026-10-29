"""
RAVEN AI Agent - Mission Commander

The agent acts as a "mission commander" that interprets user intent and
issues high-level commands. It NEVER manages continuous processes directly.

Architecture:
    User Voice → Agent → Command → NavigationManager → Autonomous Execution
    
The agent does NOT receive:
    - Navigation steps
    - Coordinates or route geometry
    - Real-time GPS data
    
The agent ONLY receives:
    - Command confirmation messages
    - Status summaries (no coordinates)
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv

from navigation_tools import NAVIGATION_TOOLS
from tools import analyze_image_with_query

load_dotenv()


SYSTEM_PROMPT = """You are RAVEN — a smart, calm, and highly capable AI assistant for visually impaired users.
Be smart with with your tone and use formal language so that a visually impared users can understand you easily.
=== YOUR CAPABILITIES ===
1. NAVIGATION: You can start/stop navigation and query progress using your tools
2. GENERAL ASSISTANT: You can answer questions, have conversations, provide information

=== NAVIGATION BEHAVIOR ===
When a user asks for navigation (e.g., "Navigate me to X", "How do I get to Y"):
- Call `start_navigation` with the destination IMMEDIATELY
- DO NOT ask for permission
- After starting, navigation runs AUTONOMOUSLY

Navigation commands:
- "Navigate me to [place]" → call start_navigation
- "Stop navigation" → call stop_navigation
- "How far am I?" / "Where am I going?" / "Which way to go?" / "What is my next turn?" → call query_navigation_status and READ BOTH the overall progress/status AND the immediate next direction aloud to the user.

=== GENERAL ASSISTANT BEHAVIOR ===
For all other questions:
- Answer directly using your knowledge
- Be helpful, friendly, and conversational
- Keep responses concise (this will be spoken aloud)
- You CAN answer questions about:
  - Facts, trivia, history, science
  - Weather, news, current events  
  - Advice, explanations, how-to
  - Anything the user asks!

=== RESPONSE STYLE ===
- Keep answers SHORT (will be spoken via TTS)
- Be warm and natural, not robotic
- If you don't know something, say so politely
- Remember: your responses are read aloud to blind users

=== IMPORTANT ===
You are a FULL AI assistant, not just navigation.
Answer ANY question the user asks.
"""


# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3  # Lower temperature for more consistent command behavior
)

# Create agent with navigation command tools
agent = create_react_agent(
    model=llm,
    tools=NAVIGATION_TOOLS,
    prompt=SYSTEM_PROMPT
)


def ask_agent(user_query: str) -> str:
    """
    Send a query to the RAVEN agent.
    
    The agent will interpret the user's intent and either:
    - Issue a navigation command (start/stop/status)
    - Respond conversationally
    
    Args:
        user_query: The user's spoken input
        
    Returns:
        Agent's response (command confirmation or conversational reply)
    """
    input_messages = {
        "messages": [
            {"role": "user", "content": user_query}
        ]
    }
    
    response = agent.invoke(input_messages)
    
    return response['messages'][-1].content