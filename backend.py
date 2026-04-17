# backend.py
from typing import Annotated, TypedDict, Optional
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

import config
from utils import career_market_search, neural_research_tool
from prompts import SYSTEM_PROMPT, REVIEWER_PROMPT, ROUTER_PROMPT
from config import GROQ_API_KEY, MAIN_MODEL_NAME, FALLBACK_MODEL_NAME, TEMPERATURE

# Define the Primary Model
primary_llm = ChatGroq(
    model=MAIN_MODEL_NAME, 
    temperature=TEMPERATURE, 
    api_key=GROQ_API_KEY
)

# Define the Fallback Model
fallback_llm = ChatGroq(
    model=FALLBACK_MODEL_NAME, 
    temperature=TEMPERATURE, 
    api_key=GROQ_API_KEY
)


# LLM Initialization from config
main_llm = main_llm = primary_llm.with_fallbacks([fallback_llm])
router_llm = ChatGroq(model=config.ROUTER_MODEL_NAME, temperature=config.TEMPERATURE, api_key=config.GROQ_API_KEY)

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    resume_text: Optional[str] # Changed to hold text directly
    critique: Optional[str]
    revision_count: int
    search_route: Optional[str]

def router_node(state: AgentState):
    last_message = state['messages'][-1].content
    prompt = ROUTER_PROMPT.format(query=last_message)
    response = router_llm.invoke([SystemMessage(content=prompt)])
    return {"search_route": "EXA" if "EXA" in response.content.upper() else "TAVILY"}

def call_model(state: AgentState):
    messages = state['messages']
    resume_text = state.get('resume_text')
    critique = state.get('critique')
    search_route = state.get('search_route')

    search_tool = neural_research_tool if search_route == "EXA" else career_market_search
    llm_with_tools = main_llm.bind_tools([search_tool])

    prompt = SYSTEM_PROMPT
    if resume_text:
        # Inject resume directly into the system context
        prompt += f"\n\n### USER RESUME CONTENT ###\n{resume_text}\n"

    if critique and critique != "PASSED":
        prompt += f"\n\n### FEEDBACK ###\n{critique}\n"

    messages_to_send = [SystemMessage(content=prompt)] + [m for m in messages if not isinstance(m, SystemMessage)]
    return {"messages": [llm_with_tools.invoke(messages_to_send)]}

def reviewer_node(state: AgentState):
    last_msg = state['messages'][-1]
    user_msg = [m for m in state['messages'] if isinstance(m, HumanMessage)][-1]
    audit_text = f"PROMPT: {user_msg.content}\nDRAFT: {last_msg.content}"
    critique = main_llm.invoke([SystemMessage(content=REVIEWER_PROMPT), HumanMessage(content=audit_text)])
    return {"critique": critique.content, "revision_count": state.get("revision_count", 0) + 1}

def should_revise(state: AgentState):
    if state.get("revision_count", 0) >= 2 or "PASSED" in state.get("critique", ""):
        return END
    return "agent"

def should_continue(state: AgentState):
    last_message = state['messages'][-1]
    return "tools" if (isinstance(last_message, AIMessage) and last_message.tool_calls) else "reviewer"

workflow = StateGraph(AgentState)
workflow.add_node("router", router_node)
workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode([career_market_search, neural_research_tool]))
workflow.add_node("reviewer", reviewer_node)

workflow.add_edge(START, "router")
workflow.add_edge("router", "agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "reviewer": "reviewer"})
workflow.add_conditional_edges("reviewer", should_revise, {"agent": "agent", END: END})
workflow.add_edge("tools", "agent")

app = workflow.compile(checkpointer=MemorySaver())