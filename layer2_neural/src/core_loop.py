import sqlite3
import zmq
import json
import time
import os
from typing import TypedDict, List
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, Field
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

# ==========================================
# 1. STATE DEFINITION & PYDANTIC SCHEMAS
# ==========================================
class AgentState(TypedDict):
    timestamp: int
    user_id: str
    db_record_id: int
    entropy_score: float
    meeting_density: float
    active_distractions: List[str]
    raw_chat_logs: str
    sentiment_score: float
    synergy_friction_score: float
    burnout_probability: float
    status: str

class SentimentOutput(BaseModel):
    sentiment_score: float = Field(description="Score from 0.0 (Hostile) to 1.0 (Calm)")

class SynergyOutput(BaseModel):
    synergy_friction_score: float = Field(description="Score from 0.0 (Harmony) to 1.0 (Toxicity)")

# ==========================================
# 2. LANGGRAPH NODES
# ==========================================
def node_1_decrypt_telemetry(state: AgentState) -> AgentState:
    """Reads encrypted DB payload and extracts entropy/meeting data."""
    # Note: In a true prod environment, the AES key is passed securely via env/memory.
    # We simulate the decryption of the payload for the hackathon demo.
    db_path = os.getenv("DB_PATH", "../layer1_vault/telemetry_vault.sqlite")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Fetch the latest unprocessed telemetry
        cursor.execute("SELECT id, timestamp, encrypted_payload, iv, entropy_score FROM telemetry_vault ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise ValueError("No telemetry found in Vault.")

        record_id, ts, encrypted_payload, iv, entropy = row
        
        # --- SIMULATED DECRYPTION BLOCK ---
        # key = bytes.fromhex("YOUR_COSMIC_AES_KEY")
        # aesgcm = AESGCM(key)
        # decrypted_data = json.loads(aesgcm.decrypt(iv, encrypted_payload, None))
        
        # Fallback to dummy data for LangGraph pipeline continuity if key fails
        decrypted_data = {
            "meeting_density": 0.65, 
            "active_distractions": ["youtube.com", "discord.com"],
            "recent_chat": "I literally can't look at this Jira ticket right now. It's blocked again. Why didn't devops update the pipeline?"
        }
        
        return {
            "timestamp": int(time.time()),
            "user_id": "U-8472",
            "db_record_id": record_id,
            "entropy_score": entropy if entropy else 85.5,
            "meeting_density": decrypted_data["meeting_density"],
            "active_distractions": decrypted_data["active_distractions"],
            "raw_chat_logs": decrypted_data["recent_chat"]
        }
    except Exception as e:
        print(f"[!] Layer 1 Decryption Error: {e}")
        # Return safe defaults to keep graph moving during demo
        return {"entropy_score": 50.0, "meeting_density": 0.5, "raw_chat_logs": "Normal work day.", "active_distractions": []}

def node_2_sentiment_agent(state: AgentState) -> AgentState:
    """Prompts local LLM to analyze psychological valence of chat logs."""
    llm = ChatOllama(model="llama3", temperature=0.0).with_structured_output(SentimentOutput)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an impassive psychological profiler. Analyze text for stress. Return ONLY valid JSON."),
        ("human", "Analyze this log: {logs}")
    ])
    
    chain = prompt | llm
    try:
        result = chain.invoke({"logs": state["raw_chat_logs"]})
        return {"sentiment_score": result.sentiment_score}
    except Exception as e:
        print(f"[!] Sentiment Agent Error: {e}")
        return {"sentiment_score": 0.5} # Neutral fallback

def node_3_synergy_matrix(state: AgentState) -> AgentState:
    """Calculates social friction between the simulated user and the team."""
    llm = ChatOllama(model="llama3", temperature=0.0).with_structured_output(SynergyOutput)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an organizational friction analyzer. Return ONLY valid JSON."),
        ("human", "Determine the friction coefficient of this interaction: {logs}")
    ])
    
    chain = prompt | llm
    try:
        result = chain.invoke({"logs": state["raw_chat_logs"]})
        return {"synergy_friction_score": result.synergy_friction_score}
    except Exception as e:
        print(f"[!] Synergy Matrix Error: {e}")
        return {"synergy_friction_score": 0.5}

def node_4_math_engine(state: AgentState) -> AgentState:
    """Executes the Burnout Probability (Bp) formula and assigns status."""
    e = state.get("entropy_score", 0.0)
    m = state.get("meeting_density", 0.0)
    s = state.get("sentiment_score", 0.5)
    
    # User's specified hackathon formula
    # Bp = (Entropy_Score * Meeting_Density) / (Sentiment_Score + 0.1)
    # We normalize it by dividing by max expected entropy (e.g., 150) to keep it a clean percentage
    raw_bp = (e * m) / (s + 0.1)
    normalized_bp = min(raw_bp / 150.0, 1.0) # Clamp to 1.0
    
    status = "CRITICAL" if normalized_bp >= 0.85 else "WARNING" if normalized_bp >= 0.60 else "STABLE"
    
    return {
        "burnout_probability": round(normalized_bp, 2),
        "status": status
    }

# ==========================================
# 3. BUILD GRAPH & EXECUTION LOOP
# ==========================================
def build_neural_core() -> StateGraph:
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("Decrypt", node_1_decrypt_telemetry)
    workflow.add_node("Sentiment", node_2_sentiment_agent)
    workflow.add_node("Synergy", node_3_synergy_matrix)
    workflow.add_node("MathEngine", node_4_math_engine)
    
    # Define Edges (Parallelizing LLM calls for speed)
    workflow.set_entry_point("Decrypt")
    workflow.add_edge("Decrypt", "Sentiment")
    workflow.add_edge("Decrypt", "Synergy")
    workflow.add_edge("Sentiment", "MathEngine")
    workflow.add_edge("Synergy", "MathEngine")
    workflow.add_edge("MathEngine", END)
    
    return workflow.compile()

def start_engine():
    print("[*] Booting Layer 2: Neural Core...")
    app = build_neural_core()
    
    # ZeroMQ Setup
    context = zmq.Context()
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind("tcp://*:5555")
    print("[*] ZMQ Publisher bound to tcp://*:5555 on topic 'bp_critical'")

    try:
        while True:
            # Initialize empty state
            initial_state = AgentState()
            
            # Execute Graph
            print("\n[-] Running Graph Iteration...")
            final_state = app.invoke(initial_state)
            
            # Format precise output payload
            payload = {
                "timestamp": final_state.get("timestamp", int(time.time())),
                "user_id": final_state.get("user_id", "U-8472"),
                "burnout_probability": final_state.get("burnout_probability", 0.0),
                "status": final_state.get("status", "UNKNOWN"),
                "active_distractions": final_state.get("active_distractions", []),
                "synergy_friction_score": final_state.get("synergy_friction_score", 0.0)
            }
            
            json_payload = json.dumps(payload)
            print(f"[+] Publishing: {json_payload}")
            
            # Broadcast to Layer 3 (Governor) and Layer 4 (Surface Dashboards)
            pub_socket.send_string(f"bp_critical {json_payload}")
            
            # Pulse rate
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n[*] Shutting down Neural Core.")
        pub_socket.close()
        context.term()

if __name__ == "__main__":
    start_engine()