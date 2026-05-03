import io
import os

import pytest
from unittest.mock import MagicMock, patch

# Must be set before any app module is imported — config.py calls sys.exit if missing.
# In CI these are real secrets injected via GitHub Actions env; locally they're dummies
# (all LLM/API calls are mocked in tests, so the actual key values don't matter).
os.environ.setdefault("GROQ_API_KEY", "test-dummy-key")
os.environ.setdefault("TAVILY_API_KEY", "test-dummy-key")
os.environ.setdefault("EXA_API_KEY", "test-dummy-key")

from langchain_core.messages import AIMessage  # noqa: E402 — must come after env setup
from starlette.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from main import api
    with TestClient(api) as c:
        yield c


@pytest.fixture
def sample_pdf_bytes():
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def mock_llm():
    """
    Replaces primary_llm and review_llm module variables so no real Groq calls are made.
    ChatGroq is a frozen Pydantic model — patching attributes directly raises ValueError.
    Replacing the whole object is the only reliable approach.
    """
    mock_response = AIMessage(content="Mock LLM response.")
    mock_bound = MagicMock()
    mock_bound.invoke.return_value = mock_response

    mock_primary = MagicMock()
    mock_primary.invoke.return_value = mock_response
    mock_primary.bind_tools.return_value = mock_bound

    mock_review = MagicMock()
    mock_review.invoke.return_value = mock_response

    with patch("backend.primary_llm", mock_primary), \
         patch("backend.review_llm", mock_review):
        yield mock_response
