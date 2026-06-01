# tests/conftest.py
import pytest
import uuid
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport
from langchain_core.messages import AIMessage, HumanMessage


# ── Shared thread ID ──────────────────────────────────────────────────────────

@pytest.fixture
def thread_id():
    return str(uuid.uuid4())


# ── Mock LLM responses ────────────────────────────────────────────────────────
# Avoids real Groq API calls in every test. Override per-test when needed.

@pytest.fixture
def mock_primary_llm():
    with patch("backend.primary_llm") as mock:
        mock.invoke.return_value = AIMessage(content="mocked response")
        mock.bind_tools.return_value = mock
        yield mock


@pytest.fixture
def mock_review_llm():
    with patch("backend.review_llm") as mock:
        mock.invoke.return_value = AIMessage(content="PASSED")
        mock.with_structured_output.return_value = mock
        yield mock


# ── Mock Supabase ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_supabase():
    with patch("utils._supabase") as mock:
        mock.table.return_value.select.return_value \
            .ilike.return_value.eq.return_value.execute.return_value \
            .data = [
                {"name": "Jane Doe", "headline": "NL Immigration Expert", "booking_url": "janedoe"},
            ]
        yield mock


# ── FastAPI test client ───────────────────────────────────────────────────────

@pytest.fixture
async def client(mock_primary_llm, mock_review_llm, mock_supabase):
    """Async HTTP client with all external calls mocked."""
    import os
    os.environ.setdefault("GROQ_API_KEY",    "test-key")
    os.environ.setdefault("TAVILY_API_KEY",  "test-key")
    os.environ.setdefault("EXA_API_KEY",     "test-key")
    os.environ.setdefault("SUPABASE_URL",    "https://fake.supabase.co")
    os.environ.setdefault("SUPABASE_KEY",    "fake-key")

    from main import api
    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as c:
        yield c


# ── Minimal PDF/DOCX fixtures ─────────────────────────────────────────────────

@pytest.fixture
def minimal_pdf_bytes():
    """Smallest valid PDF magic bytes + stub."""
    return b"%PDF-1.4 stub content"


@pytest.fixture
def minimal_docx_bytes():
    """PK magic bytes that satisfy docx detection."""
    return b"PK\x03\x04" + b"\x00" * 20