# schemas.py
from pydantic import BaseModel
from typing import Optional, List

# validates the incoming chat request
class ChatRequest(BaseModel):
    message: str
    thread_id: str
    resume_path: Optional[str] = None

# validates the outgoing response
class ChatResponse(BaseModel):
    response: str
    thread_id: str
    status: str = "success"