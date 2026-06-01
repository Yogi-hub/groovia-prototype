# tests/unit/test_routing.py
# Tests for intent routing and track detection — the most bug-prone area.
import pytest
import re
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage


from backend import route_from_start

class TestRouteFromStart:
    def test_routes_to_compressor_when_resume_not_processed(self):
        state = {"resume_text": "some text", "resume_processed": False}
        assert route_from_start(state) == "compressor"

    def test_routes_to_agent_when_already_processed(self):
        state = {"resume_text": "some text", "resume_processed": True}
        assert route_from_start(state) == "agent"

    def test_routes_to_agent_when_no_resume(self):
        state = {"resume_text": None, "resume_processed": False}
        assert route_from_start(state) == "agent"



from backend import should_continue, AgentState

def _make_state(messages, intent="qna", track=None) -> dict:
    return {
        "messages": messages, "user_intent": intent, "track": track,
        "resume_text": "summary", "resume_processed": True,
        "revision_count": 0, "critique": None,
    }

class TestShouldContinue:
    def test_routes_to_tools_when_tool_calls_present(self):
        ai_msg = AIMessage(content="", tool_calls=[{"name": "general_search", "args": {}, "id": "1", "type": "tool_call"}])
        state = _make_state([ai_msg])
        assert should_continue(state) == "tools"

    def test_routes_to_reviewer_for_report_with_headers(self):
        ai_msg = AIMessage(content="### Germany\n content\n### Netherlands\ncontent\n### Canada\ncontent")
        state = _make_state([ai_msg], intent="report")
        assert should_continue(state) == "reviewer"

    def test_routes_to_end_for_plain_response(self):
        ai_msg = AIMessage(content="Here is your answer.")
        state = _make_state([ai_msg])
        assert should_continue(state) == "end"

    def test_report_without_headers_goes_to_end(self):
        # Incomplete report should not trigger reviewer
        ai_msg = AIMessage(content="I need more info.")
        state = _make_state([ai_msg], intent="report")
        assert should_continue(state) == "end"


from backend import should_revise

class TestShouldRevise:
    def test_ends_on_passed(self):
        state = {**_make_state([]), "critique": "PASSED", "revision_count": 0}
        assert should_revise(state) == "end"

    def test_revises_on_failure(self):
        state = {**_make_state([]), "critique": "Missing citations", "revision_count": 0}
        assert should_revise(state) == "agent"

    def test_ends_when_max_revision_reached(self):
        import config
        state = {**_make_state([]), "critique": "Missing citations", "revision_count": config.MAX_REVISION}
        assert should_revise(state) == "end"



class TestTrackLoopRegression:
    """Verify that answering 'work' when intent=report sets track before the LLM prompt is built."""

    def test_work_answer_sets_track_in_state(self):
        """
        Simulate call_model being called after user answers 'work'.
        Track should be detected from the user message so LOCKED_CONTEXT
        sees TRACK=WORK, not Unknown.
        """
        from langchain_core.messages import AIMessage
        from unittest.mock import patch, MagicMock

        mock_response = AIMessage(content="Do you have preferences?")

        with patch("backend.primary_llm") as mock_llm, \
             patch("backend.review_llm") as mock_review:
            mock_llm.bind_tools.return_value.invoke.return_value = mock_response
            # Intent classifier returns "maintain" (user is continuing report flow)
            mock_classifier = MagicMock()
            mock_classifier.invoke.return_value = MagicMock(intent="maintain")
            mock_review.with_structured_output.return_value = mock_classifier

            from backend import call_model
            state = {
                "messages": [HumanMessage(content="work")],
                "resume_text": "John Doe, Software Engineer",
                "resume_processed": True,
                "user_intent": "report",
                "track": None,       # track is Unknown before this call
                "revision_count": 0,
                "critique": None,
            }
            result = call_model(state)

        # Track must be set from the user's "work" message
        assert result["track"] == "WORK", \
            "Track loop bug: user answered 'work' but track was not set"