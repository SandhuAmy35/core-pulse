from langchain_community.chat_models import ChatOllama
import logging

logging.basicConfig(level=logging.INFO)

def get_local_llm(model_name="qwen2:0.5b", temperature=0.0):
    """
    Attempts to connect to the local Ollama instance.
    """
    try:
        # Initialize the LangChain Ollama wrapper
        llm = ChatOllama(model=model_name, temperature=temperature)
        return llm
    except Exception as e:
        logging.error(f"[!] Failed to connect to Ollama ({model_name}): {e}")
        logging.warning("[-] Falling back to mock LLM responses for demo safety.")
        return None