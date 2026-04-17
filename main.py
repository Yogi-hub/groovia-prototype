# main.py
import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from langchain_core.messages import HumanMessage

# Import our project modules
from backend import app as agent_app
from schema import ChatResponse
import config

# Initialize the API
api = FastAPI(title="Immigroov AI Career Engine")

# Security: Allow the frontend to communicate with this backend
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, change to your specific Vercel URL
    allow_methods=["*"],
    allow_headers=["*"],
)

@api.post("/chat", response_model=ChatResponse)
async def chat_handler(
    message: str = Form(...),
    thread_id: str = Form(...),
    file: Optional[UploadFile] = File(None)
):
    # Setup the thread configuration for LangGraph memory
    session_config = {"configurable": {"thread_id": thread_id}}
    
    # Save file to disk if provided (for the extract_resume_tool)
    file_path = None
    if file:
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, file.filename)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

    # Initial state for the LangGraph
    input_state = {
        "messages": [HumanMessage(content=message)],
        "resume_path": str(file_path) if file_path else None,
        "revision_count": 0
    }

    try:
        # Execute the Agent logic asynchronously
        final_state = await agent_app.ainvoke(input_state, config=session_config)
        
        # Get the final AI response content
        ai_content = final_state["messages"][-1].content
        
        return {
            "status": "success",
            "response": ai_content,
            "thread_id": thread_id
        }
    except Exception as e:
        # Log error for debugging
        print(f"Agent Execution Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal AI Processing Error")

if __name__ == "__main__":
    import uvicorn
    # Start the server on port 8000
    uvicorn.run(api, host="0.0.0.0", port=config.PORT)