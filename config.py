# config.py
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
EXA_API_KEY = os.getenv("EXA_API_KEY")

# Model Settings
MAIN_MODEL_NAME = "llama-3.3-70b-versatile"
FALLBACK_MODEL_NAME = "llama-3.1-8b-instant"
ROUTER_MODEL_NAME = "llama-3.1-8b-instant"
TEMPERATURE = 0.0

# Server Settings
PORT = 8000
HOST = "0.0.0.0"