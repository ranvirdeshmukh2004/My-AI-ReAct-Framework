"""
events.py — Agent Streaming Event System
==========================================
Dataclass-based events for real-time communication between
the ReAct agent loop and the Streamlit UI.

Each event represents a discrete moment in the agent's lifecycle:
thinking, tool calls, observations, answer tokens, etc.
"""

import time
from dataclasses import dataclass, field


@dataclass
class AgentEvent:
    """
    A single event emitted by the streaming agent.
    
    Attributes:
        type: Event category — determines how the UI renders it.
        data: Event-specific payload (varies by type).
        iteration: Which ReAct loop iteration (0-indexed, -1 for post-loop).
        timestamp: Unix timestamp when the event was created.
    
    Event Types:
        "thinking"      — Agent is reasoning (partial thought text)
        "tool_call"     — Agent decided to use a tool
        "tool_result"   — Tool returned a result
        "answer_start"  — Final answer is about to stream
        "answer_token"  — A single token of the final answer
        "answer_done"   — Final answer is complete
        "audit"         — Audit report ready
        "validation"    — Validation report ready
        "done"          — Everything complete, full result dict available
        "error"         — An error occurred
    """
    type: str
    data: dict = field(default_factory=dict)
    iteration: int = 0
    timestamp: float = field(default_factory=time.time)
