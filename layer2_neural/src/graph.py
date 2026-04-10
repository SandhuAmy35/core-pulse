import time
from typing import TypedDict, List
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from src.llm_connector import get_local_llm

# --- SCHEMAS ---
class AgentState(TypedDict):
    timestamp: int
    user_id: str
    entropy_score: float
    meeting_density: float
    raw_chat_logs: str
    sentiment_score: float
    synergy_friction_score: float
    burnout_probability: float
    status: str

class SentimentOutput(BaseModel):
    sentiment_score: float = Field(description="Score from 0.0 (Hostile) to 1.0 (Calm)")

class SynergyOutput(BaseModel):
    synergy_friction_score: float = Field(description="Score from 0.0 (Harmony) to 1.0 (Toxicity)")

# --- NODES ---
def node_sentiment(state: AgentState) -> AgentState:
    llm = get_local_llm()
    if not llm:
        return {"sentiment_score": 0.4} # Fallback if LLM is down

    llm_structured = llm.with_structured_output(SentimentOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a psychological profiler. Analyze text for stress. Return ONLY valid JSON matching the schema."),
        ("human", "Analyze this: {logs}")
    ])
    
    try:
        result = (prompt | llm_structured).invoke({"logs": state.get("raw_chat_logs", "")})
        return {"sentiment_score": result.sentiment_score}
    except:
        return {"sentiment_score": 0.5}

def node_synergy(state: AgentState) -> AgentState:
    llm = get_local_llm()
    if not llm:
        return {"synergy_friction_score": 0.6} # Fallback if LLM is down

    llm_structured = llm.with_structured_output(SynergyOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You analyze team friction. Return ONLY valid JSON matching the schema."),
        ("human", "Analyze friction in this text: {logs}")
    ])
    
    try:
        result = (prompt | llm_structured).invoke({"logs": state.get("raw_chat_logs", "")})
        return {"synergy_friction_score": result.synergy_friction_score}
    except:
        return {"synergy_friction_score": 0.5}

def node_math_engine(state: AgentState) -> AgentState:
    e = state.get("entropy_score", 50.0)
    m = state.get("meeting_density", 0.5)
    s = state.get("sentiment_score", 0.5)
    
    raw_bp = (e * m) / (s + 0.1)
    normalized_bp = min(raw_bp / 150.0, 1.0)
    
    status = "CRITICAL" if normalized_bp >= 0.85 else "WARNING" if normalized_bp >= 0.60 else "STABLE"
    
    return {"burnout_probability": round(normalized_bp, 2), "status": status}

# --- GRAPH BUILDER ---
def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("Sentiment", node_sentiment)
    workflow.add_node("Synergy", node_synergy)
    workflow.add_node("MathEngine", node_math_engine)
    
    workflow.set_entry_point("Sentiment")
    # Parallel execution of LLM nodes
    workflow.add_edge("Sentiment", "MathEngine")
    workflow.add_edge("Synergy", "MathEngine")
    workflow.add_edge("MathEngine", END)
    
    return workflow.compile()