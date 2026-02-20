"""Tavily-based Reddit search for last30days skill.

Mirrors the interface of openai_reddit.py but uses Tavily Search API
with include_domains=["reddit.com"] instead of OpenAI Responses API.

API docs: https://docs.tavily.com/documentation/api-reference/search
"""

import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from . import dates as dates_mod
from . import http


ENDPOINT = "https://api.tavily.com/search"

DEPTH_CONFIG = {
    "quick": 10,
    "default": 20,
    "deep": 40,
}


def _log_error(msg: str):
    """Log error to stderr."""
    sys.stderr.write(f"[REDDIT ERROR] {msg}\n")
    sys.stderr.flush()


def _log_info(msg: str):
    """Log info to stderr."""
    sys.stderr.write(f"[REDDIT] {msg}\n")
    sys.stderr.flush()


def _extract_core_subject(topic: str) -> str:
    """Extract core subject from verbose query for retry.

    Reuses the same logic as openai_reddit._extract_core_subject().
    """
    noise = ['best', 'top', 'how to', 'tips for', 'practices', 'features',
             'killer', 'guide', 'tutorial', 'recommendations', 'advice',
             'prompting', 'using', 'for', 'with', 'the', 'of', 'in', 'on']
    words = topic.lower().split()
    result = [w for w in words if w not in noise]
    return ' '.join(result[:3]) or topic


def _extract_reddit_path(url: str) -> Optional[str]:
    """Extract /r/sub/comments/id/title path from a Reddit URL.

    Returns path suitable for get_reddit_json, or None if not a comments URL.
    """
    try:
        path = urlparse(url).path
        # Match /r/{sub}/comments/{id}/ pattern
        if '/r/' in path and '/comments/' in path:
            return path
    except Exception:
        pass
    return None


def _fetch_date_from_reddit(url: str) -> Optional[str]:
    """Fetch created_utc date from Reddit's free JSON endpoint.

    Returns YYYY-MM-DD string or None on failure.
    """
    path = _extract_reddit_path(url)
    if not path:
        return None
    try:
        data = http.get_reddit_json(path, timeout=10, retries=1)
        # Reddit returns a list: [post_listing, comments_listing]
        if isinstance(data, list) and len(data) > 0:
            children = data[0].get("data", {}).get("children", [])
            if children:
                created_utc = children[0].get("data", {}).get("created_utc")
                return dates_mod.timestamp_to_date(created_utc)
    except Exception:
        pass
    return None


def _enrich_dates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich items missing dates by fetching from Reddit JSON API.

    Uses parallel requests (max 5 concurrent) to avoid blocking.
    Only fetches for items where date is None.
    """
    items_needing_dates = [(i, item) for i, item in enumerate(items) if not item.get("date")]
    if not items_needing_dates:
        return items

    _log_info(f"Enriching dates for {len(items_needing_dates)}/{len(items)} items...")

    max_workers = min(5, len(items_needing_dates))
    enriched = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_fetch_date_from_reddit, item["url"]): idx
            for idx, item in items_needing_dates
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                date = future.result(timeout=15)
                if date:
                    items[idx]["date"] = date
                    enriched += 1
            except Exception:
                pass

    _log_info(f"Enriched {enriched}/{len(items_needing_dates)} dates from Reddit")
    return items


def search_reddit(
    api_key: str,
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
) -> Dict[str, Any]:
    """Search Reddit via Tavily Search API.

    Args:
        api_key: Tavily API key
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        depth: Research depth - "quick", "default", or "deep"

    Returns:
        Raw Tavily API response dict
    """
    max_results = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    search_depth = "advanced" if depth == "deep" else "basic"

    payload = {
        "api_key": api_key,
        "query": f"{topic} (recent, {from_date} to {to_date})",
        "search_depth": search_depth,
        "max_results": max_results,
        "include_domains": ["reddit.com"],
    }

    _log_info(f"Searching Tavily (Reddit) for: {topic}")

    timeout = 30 if depth == "quick" else 45 if depth == "default" else 60

    response = http.post(
        ENDPOINT,
        json_data=payload,
        headers={},
        timeout=timeout,
    )

    return response


def parse_reddit_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse Tavily response to extract Reddit items.

    Converts Tavily result format to the same item schema used by
    openai_reddit.parse_reddit_response(). Enriches missing dates
    by fetching created_utc from Reddit's free JSON API.

    Args:
        response: Raw Tavily API response

    Returns:
        List of item dicts with keys: id, title, url, subreddit, date,
        why_relevant, relevance
    """
    items = []

    results = response.get("results", [])
    if not isinstance(results, list):
        return items

    for i, result in enumerate(results):
        if not isinstance(result, dict):
            continue

        url = result.get("url", "")
        if not url or "reddit.com" not in url:
            continue

        title = str(result.get("title", "")).strip()
        if not title:
            title = str(result.get("content", "")).strip()[:100]
        if not title:
            continue

        # Parse subreddit from URL path (/r/{name}/)
        subreddit = ""
        try:
            path = urlparse(url).path
            match = re.search(r'/r/([^/]+)', path)
            if match:
                subreddit = match.group(1)
        except Exception:
            pass

        # Parse date from published_date
        date = result.get("published_date")
        if date and len(date) >= 10:
            date = date[:10]  # Trim to YYYY-MM-DD
        if date and not re.match(r'^\d{4}-\d{2}-\d{2}$', str(date)):
            date = None

        # Tavily relevance score
        relevance = result.get("score", 0.6)
        try:
            relevance = min(1.0, max(0.0, float(relevance)))
        except (TypeError, ValueError):
            relevance = 0.6

        items.append({
            "id": f"R{i+1}",
            "title": title[:200],
            "url": url,
            "subreddit": subreddit,
            "date": date,
            "why_relevant": "",
            "relevance": relevance,
        })

    _log_info(f"Tavily: {len(items)} Reddit results")

    # Enrich items missing dates from Reddit's free JSON API
    if items:
        items = _enrich_dates(items)

    return items
