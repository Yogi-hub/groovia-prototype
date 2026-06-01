# utils.py
import io
import json
import docx2txt
from pypdf import PdfReader
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from exa_py import Exa
from supabase import create_client, Client
from config import EXA_API_KEY, SUPABASE_URL, SUPABASE_KEY, MENTOR_BOOKING_COL

exa = Exa(api_key=EXA_API_KEY)
_tavily = TavilySearch(max_results=5)
_supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def parse_pdf_to_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

def parse_docx_to_text(file_bytes: bytes) -> str:
    return docx2txt.process(io.BytesIO(file_bytes))

@tool
def general_search(query: str) -> str:
    """
    Broad web search for country overviews, culture, cost of living, general market trends, pros and cons.
    Use for: 'Tech scene in Germany', 'Cost of living in Amsterdam', 'Issues faced by expats in USA'.
    Do NOT use for visa rules, salary thresholds, or government policies.
    """
    try:
        results = _tavily.invoke({"query": query})
        return str(results)
    except Exception as e:
        return f"[SEARCH_ERROR] general_search failed: {e}"

@tool
def precise_search(query: str) -> str:
    """
    Precise neural search for accurate legal, visa, salary, and policy data.
    Use for: exact visa names, salary thresholds, immigration law updates, university syllabi.
    Argument: query — a specific natural language question about visa, law, salary, or policy.
    """
    try:
        response = exa.search(
            query,
            type="neural",
            num_results=3,
            contents={"highlights": {"max_characters": 1000}},
        )
        results = [
            {"url": r.url, "summary": r.highlights[0] if getattr(r, "highlights", None) else "N/A"}
            for r in response.results
        ]
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return f"[SEARCH_ERROR] precise_search failed: {e}"

@tool
def retrieve_matching_mentors(target_country: str) -> str:
    """Retrieves mentors from the database for a specific country including their booking URLs."""
    try:
        resp = (
            _supabase.table("mentors")
            .select(f"name, headline, {MENTOR_BOOKING_COL}")
            .ilike("country_expertise", target_country)   # case-insensitive match
            .eq("is_active", True)
            .execute()
        )
        results = [
            {
                "name": r["name"],
                "headline": r["headline"],
                "booking_url": f"https://cal.com/{r[MENTOR_BOOKING_COL]}" if r.get(MENTOR_BOOKING_COL) else "No booking link available",
            }
            for r in resp.data
        ]
        return json.dumps(results)
    except Exception as e:
        print(f"[TOOL_ERROR] Mentor retrieval failed: {e}")
        return f"[TOOL_ERROR] Mentor retrieval failed: {e}"