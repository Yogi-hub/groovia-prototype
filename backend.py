import os
from typing import Annotated, TypedDict, List, Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from utils import extract_resume_tool, career_market_search, neural_research_tool
from prompts import SYSTEM_PROMPT, REVIEWER_PROMPT, ROUTER_PROMPT

load_dotenv(override=True)

MAIN_MODEL_NAME = "llama-3.3-70b-versatile"
ROUTER_MODEL_NAME = "llama-3.1-8b-instant"
TEMPERATURE = 0.0

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

main_llm = ChatGroq(model=MAIN_MODEL_NAME, temperature=TEMPERATURE, api_key=GROQ_API_KEY)
router_llm = ChatGroq(model=ROUTER_MODEL_NAME, temperature=TEMPERATURE, api_key=GROQ_API_KEY)

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    resume_path: Optional[str]
    critique: Optional[str]
    revision_count: int
    search_route: Optional[str]

def router_node(state: AgentState):
    last_message = state['messages'][-1].content
    prompt = ROUTER_PROMPT.format(query=last_message)
    response = router_llm.invoke([SystemMessage(content=prompt)])
    return {
        "search_route": "EXA" if "EXA" in response.content.upper() else "TAVILY",
        "revision_count": 0,
        "critique": None,
    }

def call_model(state: AgentState):
    messages = state['messages']
    resume_path = state.get('resume_path')
    critique = state.get('critique')
    search_route = state.get('search_route')

    search_tool = neural_research_tool if search_route == "EXA" else career_market_search
    active_tools = [extract_resume_tool, search_tool]

    llm_with_tools = main_llm.bind_tools(active_tools)

    prompt = SYSTEM_PROMPT
    if resume_path:
        normalized_path = resume_path.replace("\\", "/")
        prompt += f"\n\nCOMMAND: You must now call 'extract_resume_tool' with file_path='{normalized_path}' to parse the user's resume."

    if critique and critique != "PASSED":
        prompt += f"\n\n### CRITICAL FEEDBACK FROM AUDITOR ###\n{critique}\n"
        prompt += "Please revise your previous draft to address the feedback above."

    filtered_messages = [m for m in messages if not isinstance(m, SystemMessage)]
    messages_to_send = [SystemMessage(content=prompt)] + filtered_messages
    response = llm_with_tools.invoke(messages_to_send)

    return {"messages": [response]}

def reviewer_node(state: AgentState):
    last_msg = state['messages'][-1]
    user_msg = [m for m in state['messages'] if isinstance(m, HumanMessage)][-1]
    audit_text = f"USER'S PROMPT:\n{user_msg.content}\n\nADVISOR'S DRAFT:\n{last_msg.content}"
    review_input = [SystemMessage(content=REVIEWER_PROMPT), HumanMessage(content=audit_text)]
    critique = main_llm.invoke(review_input)
    return {"critique": critique.content, "revision_count": state.get("revision_count", 0) + 1}

def should_revise(state: AgentState):
    if state.get("revision_count", 0) >= 2 or "PASSED" in state.get("critique", ""):
        return END
    return "agent"

def should_continue(state: AgentState):
    last_message = state['messages'][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "reviewer"

workflow = StateGraph(AgentState)
workflow.add_node("router", router_node)
workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode([extract_resume_tool, career_market_search, neural_research_tool]))
workflow.add_node("reviewer", reviewer_node)

workflow.add_edge(START, "router")
workflow.add_edge("router", "agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "reviewer": "reviewer"})
workflow.add_conditional_edges("reviewer", should_revise, {"agent": "agent", END: END})
workflow.add_edge("tools", "agent")

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

if __name__ == "__main__":
    graph_image = app.get_graph().draw_mermaid_png()
    with open("agent_graph.png", "wb") as f:
        f.write(graph_image)
    print("Graph visualization generated successfully.")
