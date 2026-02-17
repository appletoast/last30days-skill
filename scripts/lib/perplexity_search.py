"""Perplexity Sonar web search for last30days skill.

Uses the Perplexity Sonar API directly (no OpenRouter intermediary).
Returns citations that are parsed into individual web search items.

API docs: https://docs.perplexity.ai/api-reference/chat-completions
"""

import re
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from . import http

ENDPOINT = "https://api.perplexity.ai/chat/completions"
MODEL = "sonar"

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
    """Search the web via Perplexity Sonar API.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        api_key: Perplexity API key
        depth: 'quick', 'default', or 'deep'

    Returns:
        List of result dicts with keys: url, title, snippet, source_domain, date, relevance

    Raises:
        http.HTTPError: On API errors
    """
    max_results_hint = {"quick": 8, "default": 15, "deep": 25}.get(depth, 15)
    max_tokens = {"quick": 1024, "default": 2048, "deep": 4096}.get(depth, 2048)
    # Sonar is LLM-based — needs more time than structured search APIs
    http_timeout = {"quick": 30, "default": 45, "deep": 60}.get(depth, 45)

    prompt = (
        f"Find up to {max_results_hint} recent blog posts, news articles, tutorials, "
        f"and discussions about {topic} published between {from_date} and {to_date}. "
        f"Exclude results from reddit.com, x.com, and twitter.com. "
        f"For each result, provide the title, URL, publication date, "
        f"and a brief summary of why it's relevant."
    )

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }

    sys.stderr.write(f"[Web] Searching Perplexity Sonar for: {topic}\n")
    sys.stderr.flush()

    response = http.post(
        ENDPOINT,
        json_data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
        },
        timeout=http_timeout,
    )

    return _normalize_results(response)


def _normalize_results(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert Perplexity Sonar response to websearch item schema.

    Sonar returns:
    - citations: [url, ...] -- flat list of cited URLs
    - choices[0].message.content -- synthesized text with [N] references
    """
    items = []

    citations = response.get("citations", [])
    content = _get_content(response)

    if not isinstance(citations, list) or not citations:
        sys.stderr.write("[Web] Perplexity Sonar: 0 results (no citations)\n")
        sys.stderr.flush()
        return items

    # Count citation references in content to gauge per-citation importance
    citation_counts = _count_citation_references(content, len(citations))

    for i, url in enumerate(citations):
        if not isinstance(url, str) or not url:
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

        # Extract title from content references like [1] Title...
        title = _extract_title_for_citation(content, i + 1) or domain
        snippet = _extract_snippet_for_citation(content, i + 1)

        # Estimate relevance from citation position and reference frequency.
        # Earlier citations and more-referenced citations are more relevant.
        # Range: 0.55 (last, single-ref) to 0.90 (first, multi-ref)
        position_score = max(0.0, 1.0 - (i / max(len(citations), 1)))  # 1.0 → 0.0
        ref_count = citation_counts.get(i + 1, 1)
        ref_bonus = min(0.1, (ref_count - 1) * 0.05)  # +0.05 per extra ref, max +0.1
        relevance = round(0.55 + 0.35 * position_score + ref_bonus, 2)

        items.append({
            "id": f"W{i+1}",
            "title": title[:200],
            "url": url,
            "source_domain": domain,
            "snippet": snippet[:500] if snippet else "",
            "date": None,
            "date_confidence": "low",
            "relevance": relevance,
            "why_relevant": "",
        })

    sys.stderr.write(f"[Web] Perplexity Sonar: {len(items)} results\n")
    sys.stderr.flush()

    return items


def _get_content(response: Dict[str, Any]) -> str:
    """Extract the text content from the chat completion response."""
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""


def _count_citation_references(content: str, num_citations: int) -> Dict[int, int]:
    """Count how many times each citation [N] is referenced in the content."""
    counts = {}
    if not content:
        return counts
    for i in range(1, num_citations + 1):
        counts[i] = len(re.findall(rf'\[{i}\](?!\d)', content))
    return counts


def _extract_title_for_citation(content: str, index: int) -> Optional[str]:
    """Try to extract a title near a citation reference [N] in the content."""
    if not content:
        return None

    # Look for patterns like [1] Title or **Title** [1]
    pattern = rf'\[{index}\][)\s]*([^\[\n]{{5,80}})'
    match = re.search(pattern, content)
    if match:
        title = match.group(1).strip().rstrip('.')
        title = re.sub(r'[*_`]', '', title)
        return title if len(title) > 3 else None

    return None


def _extract_snippet_for_citation(content: str, index: int) -> Optional[str]:
    """Try to extract context around a citation reference [N]."""
    if not content:
        return None

    # Find the sentence containing [N]
    pattern = rf'[^.]*\[{index}\][^.]*\.'
    match = re.search(pattern, content)
    if match:
        snippet = match.group(0).strip()
        snippet = re.sub(r'\[\d+\]', '', snippet).strip()
        snippet = re.sub(r'[*_`]', '', snippet)
        return snippet if len(snippet) > 10 else None

    return None
