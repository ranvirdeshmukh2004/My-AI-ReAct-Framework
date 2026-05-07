"""
server.py — FastAPI Backend (Optional)
========================================
A standalone REST API for the AI Agent.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from agent.react_agent import ReactAgent
from agent.memory import ConversationMemory

# ============================================
# App Setup
# ============================================

app = FastAPI(
    title="AI Agent API",
    description="Autonomous AI agent with reasoning and tool use",
    version="1.0.0",
)

# Allow CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the agent
agent = ReactAgent()


# ============================================
# Request/Response Models
# ============================================

class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Response body from the /chat endpoint."""
    final_answer: str
    steps: list[dict]
    session_id: str


# ============================================
# Endpoints
# ============================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "agent": "AI Agent",
        "model": "Grok (x-ai/grok-4.1-fast)",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to the agent and get a response.
    
    The agent will reason step-by-step, use tools if needed,
    and return a final answer along with the full reasoning trace.
    """
    try:
        result = agent.run(
            user_input=request.message,
            session_id=request.session_id,
        )
        return ChatResponse(
            final_answer=result["final_answer"],
            steps=result["steps"],
            session_id=result["session_id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/{session_id}")
async def get_history(session_id: str):
    """Get conversation history for a session."""
    history = agent.memory.get_history(session_id)
    return {"session_id": session_id, "messages": history}


@app.get("/sessions")
async def list_sessions():
    """List all conversation sessions."""
    sessions = agent.memory.list_sessions()
    return {"sessions": sessions}


@app.post("/new-session")
async def new_session():
    """Create a new conversation session."""
    session_id = ConversationMemory.new_session_id()
    return {"session_id": session_id}


@app.get("/tools")
async def list_tools():
    """List all available tools."""
    tools = agent.get_available_tools()
    return {"tools": tools}


# ============================================
# Run with: uvicorn server:app --reload
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
