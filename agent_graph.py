"""
RAVEN Agent Graph - LangGraph-based conversational agent.

Uses LangGraph StateGraph for:
- Conversation state management
- Memory persistence across turns
- Conditional routing based on speech gate
- Proper graph-based flow control

Flow:
    START → speech_gate → [route] → agent/idle → response → END
"""

import os
import logging
from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

from dotenv import load_dotenv

from speech_gate import speech_gate, SpeechGateResult
from navigation_tools import NAVIGATION_TOOLS

load_dotenv()

logger = logging.getLogger("RAVEN.Graph")


# =============================================================================
# STATE DEFINITION
# =============================================================================

class ConversationState(TypedDict):
    """
    State schema for the RAVEN conversation graph.
    
    Attributes:
        messages: Chat history (managed by add_messages reducer)
        user_input: Raw STT input from current turn
        gate_result: Result of speech gate evaluation
        command: Extracted command after gate processing
        response: Final response to speak
        is_navigating: Whether navigation is active
    """
    messages: Annotated[list, add_messages]
    user_input: str
    gate_result: str
    command: Optional[str]
    response: str
    is_navigating: bool


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """You are RAVEN — a smart, calm, and highly capable AI assistant for visually impaired users.

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
- "How far am I?" / "Where am I going?" → call query_navigation_status

=== GENERAL ASSISTANT BEHAVIOR ===
For all other questions:
- Answer directly using your knowledge
- Be helpful, friendly, and conversational
- Keep responses concise (this will be spoken aloud)
- You CAN answer questions about facts, trivia, advice, explanations, anything!

=== RESPONSE STYLE ===
- Keep answers SHORT (will be spoken via TTS)
- Be warm and natural, not robotic
- Remember: your responses are read aloud to blind users

You are a FULL AI assistant. Answer ANY question the user asks.
"""


# =============================================================================
# LLM AND TOOLS
# =============================================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.5
)

# Bind tools to LLM
llm_with_tools = llm.bind_tools(NAVIGATION_TOOLS)


# =============================================================================
# GRAPH NODES
# =============================================================================

def speech_gate_node(state: ConversationState) -> dict:
    """
    Evaluate user input through the speech gate.
    
    Determines if the input should be processed or rejected.
    """
    user_input = state.get("user_input", "")
    
    if not user_input:
        return {
            "gate_result": "REJECTED",
            "command": None,
            "response": ""
        }
    
    result, command = speech_gate.evaluate(user_input)
    
    logger.info(f"Speech gate: {result.name} | Command: {command}")
    
    # Map result to routing key
    if result == SpeechGateResult.WAKE_WORD_DETECTED:
        return {
            "gate_result": "WAKE_WORD",
            "command": None,
            "response": "Yes?"
        }
    elif result == SpeechGateResult.COMMAND_VALID:
        return {
            "gate_result": "VALID",
            "command": command,
            "response": ""
        }
    else:
        return {
            "gate_result": "REJECTED",
            "command": None,
            "response": ""
        }


def agent_node(state: ConversationState) -> dict:
    """
    Process valid command through the LLM agent.
    
    The agent can call navigation tools or answer questions.
    """
    command = state.get("command", "")
    messages = state.get("messages", [])
    
    if not command:
        return {"response": "I didn't catch that. Could you repeat?"}
    
    # Build messages with system prompt
    full_messages = [SystemMessage(content=SYSTEM_PROMPT)]
    full_messages.extend(messages)
    full_messages.append(HumanMessage(content=command))
    
    logger.info(f"Agent processing: '{command}'")
    
    try:
        # Invoke LLM
        response = llm_with_tools.invoke(full_messages)
        
        # Check if tool was called
        if response.tool_calls:
            # Execute tools
            tool_node = ToolNode(NAVIGATION_TOOLS)
            tool_result = tool_node.invoke({"messages": [response]})
            
            # Get tool response
            if tool_result.get("messages"):
                tool_message = tool_result["messages"][-1]
                final_response = tool_message.content
            else:
                final_response = response.content
        else:
            final_response = response.content
            
        # Ensure final_response is a string (Gemini API can sometimes return a list of dicts)
        if isinstance(final_response, list):
            text_parts = []
            for item in final_response:
                if isinstance(item, dict) and "text" in item:
                    text_parts.append(item["text"])
                elif isinstance(item, str):
                    text_parts.append(item)
            final_response = " ".join(text_parts)
        elif not isinstance(final_response, str):
            final_response = str(final_response)
        
        # Update messages
        return {
            "messages": [
                HumanMessage(content=command),
                AIMessage(content=final_response)
            ],
            "response": final_response
        }
        
    except Exception as e:
        logger.error(f"Agent error: {e}")
        return {"response": "Sorry, I encountered an error. Please try again."}


def idle_node(state: ConversationState) -> dict:
    """
    Handle rejected inputs (do nothing).
    """
    return {"response": ""}


def response_node(state: ConversationState) -> dict:
    """
    Finalize the response for TTS output.
    """
    response = state.get("response", "")
    return {"response": response}


# =============================================================================
# ROUTING LOGIC
# =============================================================================

def route_after_gate(state: ConversationState) -> Literal["agent", "idle", "response"]:
    """
    Route based on speech gate result.
    """
    gate_result = state.get("gate_result", "REJECTED")
    
    if gate_result == "VALID":
        return "agent"
    elif gate_result == "WAKE_WORD":
        return "response"  # Just say "Yes?"
    else:
        return "idle"


# =============================================================================
# BUILD GRAPH
# =============================================================================

def build_agent_graph():
    """
    Build the LangGraph StateGraph for RAVEN.
    
    Returns:
        Compiled graph with memory checkpointing
    """
    # Create graph
    graph = StateGraph(ConversationState)
    
    # Add nodes
    graph.add_node("speech_gate", speech_gate_node)
    graph.add_node("agent", agent_node)
    graph.add_node("idle", idle_node)
    graph.add_node("response", response_node)
    
    # Add edges
    graph.add_edge(START, "speech_gate")
    
    # Conditional routing after speech gate
    graph.add_conditional_edges(
        "speech_gate",
        route_after_gate,
        {
            "agent": "agent",
            "idle": "idle",
            "response": "response"
        }
    )
    
    # All paths lead to response then END
    graph.add_edge("agent", "response")
    graph.add_edge("idle", END)
    graph.add_edge("response", END)
    
    # Add memory
    memory = MemorySaver()
    
    # Compile
    compiled = graph.compile(checkpointer=memory)
    
    logger.info("Agent graph compiled with memory")
    
    return compiled


# =============================================================================
# GLOBAL GRAPH INSTANCE
# =============================================================================

# Create graph on import
agent_graph = build_agent_graph()


def invoke_agent(user_input: str, thread_id: str = "main") -> str:
    """
    Invoke the agent graph with user input.
    
    Args:
        user_input: Raw STT transcription
        thread_id: Conversation thread ID for memory
        
    Returns:
        Agent response (may be empty if rejected)
    """
    from conversation_logger import get_logger
    from navigation import nav_manager
    
    config = {"configurable": {"thread_id": thread_id}}
    
    result = agent_graph.invoke(
        {
            "user_input": user_input,
            "messages": [],
            "gate_result": "",
            "command": None,
            "response": "",
            "is_navigating": False
        },
        config=config
    )
    
    response = result.get("response", "")
    gate_result = result.get("gate_result", "REJECTED")
    
    # Log only valid commands with responses (skip noise)
    if gate_result == "VALID" and response:
        conv_logger = get_logger()
        if conv_logger:
            conv_logger.log_turn(
                user_input=user_input,
                gate_result=gate_result,
                agent_response=response,
                is_navigation=nav_manager.is_navigating,
                destination=nav_manager.current_destination if nav_manager.is_navigating else None
            )
    
    return response


def get_graph_state(thread_id: str = "main") -> Optional[ConversationState]:
    """
    Get current state of the conversation graph.
    
    Args:
        thread_id: Conversation thread ID
        
    Returns:
        Current state or None
    """
    config = {"configurable": {"thread_id": thread_id}}
    return agent_graph.get_state(config)
