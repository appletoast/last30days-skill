"""Tavily web search for last30days skill.

Uses the Tavily Search API which returns structured search results natively.
Preferred web search backend -- structured output, no parsing needed.

API docs: https://docs.tavily.com/documentation/api-reference/search
"""

import sys
from typing import Any, Dict, List
from urllib.parse import urlparse

from . import http

ENDPOINT = "https://api.tavily.com/search"

# Domains to exclude (handled by Reddit/X search)
EXCLUDED_DOMAINS = {
    "reddit.com", "www.reddit.com", "old.reddit.com",
    "twitter.com", "www.twitter.com", "x.com", "www.x.com",
}


def search_web(
    topic: str,
    from_date: str,
    to_date: str,
    api_key: str,
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search the web via Tavily Search API.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        api_key: Tavily API key
        depth: 'quick', 'default', or 'deep'

    Returns:
        List of result dicts with keys: url, title, snippet, source_domain, date, relevance

    Raises:
        http.HTTPError: On API errors
    """
    max_results = {"quick": 8, "default": 15, "deep": 25}.get(depth, 15)
    search_depth = "advanced" if depth == "deep" else "basic"

    payload = {
        "api_key": api_key,
        "query": f"{topic} (recent, {from_date} to {to_date})",
        "search_depth": search_depth,
        "max_results": max_results,
        "exclude_domains": [
            "reddit.com", "x.com", "twitter.com",
        ],
    }

    sys.stderr.write(f"[Web] Searching Tavily for: {topic}\n")
    sys.stderr.flush()

    response = http.post(
        ENDPOINT,
        json_data=payload,
        headers={},
        timeout=20,
    )

    return _normalize_results(response)


def _normalize_results(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert Tavily response to websearch item schema.

    Tavily returns structured results with title, url, content, score, etc.
    """
    items = []

    results = response.get("results", [])
    if not isinstance(results, list):
        return items

    for i, result in enumerate(results):
        if not isinstance(result, dict):
            continue

        url = result.get("url", "")
        if not url:
            continue

        # Skip excluded domains
        try:
            domain = urlparse(url).netloc.lower()
            if domain in EXCLUDED_DOMAINS:
                continue
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception:
            domain = ""

        title = str(result.get("title", "")).strip()
        snippet = str(result.get("content", "")).strip()

        if not title and not snippet:
            continue

        # Tavily provides a relevance score (0-1)
        relevance = result.get("score", 0.6)
        try:
            relevance = min(1.0, max(0.0, float(relevance)))
        except (TypeError, ValueError):
            relevance = 0.6

        # Tavily may include published_date
        date = result.get("published_date")
        if date and len(date) >= 10:
            date = date[:10]  # Trim to YYYY-MM-DD
        date_confidence = "med" if date else "low"

        items.append({
            "id": f"W{i+1}",
            "title": title[:200],
            "url": url,
            "source_domain": domain,
            "snippet": snippet[:500],
            "date": date,
            "date_confidence": date_confidence,
            "relevance": relevance,
            "why_relevant": "",
        })

    sys.stderr.write(f"[Web] Tavily: {len(items)} results\n")
    sys.stderr.flush()

    return items
