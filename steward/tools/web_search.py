"""web_search tool - web search returning contextual answers with citations."""
from __future__ import annotations

import re
from urllib.parse import unquote

import requests

from ..types import ToolResult
from .shared import BROWSER_USER_AGENT, clear_status, env_cap, print_status


def tool_web_search(query: str) -> ToolResult:
    """AI-powered web search returning synthesized answers with citations.

    Args:
        query: A clear, specific question or search query
    """
    if not query or not query.strip():
        raise ValueError("'query' must be a non-empty string")

    max_results = env_cap("STEWARD_SEARCH_WEB_MAX_RESULTS", 5)

    print_status(f"searching: {query[:60]}{'...' if len(query) > 60 else ''}")
    try:
        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=10,
        )
        response.raise_for_status()
        html = response.text
    except requests.RequestException as exc:
        clear_status()
        return {"id": "web_search", "output": f"[error] Search failed: {exc}"}
    finally:
        clear_status()

    results = _parse_duckduckgo_results(html, max_results)

    if not results:
        return {"id": "web_search", "output": f"No results found for: {query}", "next_tool": ["web_fetch"]}

    # Build context for LLM synthesis
    context_lines = [f"Query: {query}", "", "Search Results:"]
    for i, result in enumerate(results, 1):
        context_lines.append(f"\n[{i}] {result['title']}")
        context_lines.append(f"URL: {result['url']}")
        context_lines.append(f"Snippet: {result['snippet']}")

    context = "\n".join(context_lines)

    # Return as meta-tool for runner to synthesize
    return {
        "id": "web_search",
        "output": "",  # Will be replaced by synthesized response
        "meta_prompt": (
            "Based on the web search results below, provide a comprehensive answer to the user's query. "
            "Include inline citations using [N] format referencing the source numbers. "
            "Be concise but thorough. If the results don't fully answer the query, acknowledge limitations.\n\n"
            f"{context}"
        ),
        "meta_context": context,
        "next_tool": ["web_fetch"],
    }


def _parse_duckduckgo_results(html: str, max_results: int) -> list[dict]:
    """Parse search results from DuckDuckGo HTML response."""
    results = []

    result_pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>.*?'
        r'<a[^>]*class="result__snippet"[^>]*>([^<]*(?:<[^>]*>[^<]*)*)</a>',
        re.DOTALL | re.IGNORECASE
    )

    alt_pattern = re.compile(
        r'<h2[^>]*class="result__title"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>.*?'
        r'class="result__snippet"[^>]*>([^<]*)',
        re.DOTALL | re.IGNORECASE
    )

    for pattern in [result_pattern, alt_pattern]:
        for match in pattern.finditer(html):
            if len(results) >= max_results:
                break
            url = match.group(1)
            title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
            snippet = re.sub(r"<[^>]+>", "", match.group(3)).strip()
            if "duckduckgo.com" in url:
                uddg_match = re.search(r"uddg=([^&]+)", url)
                if uddg_match:
                    url = unquote(uddg_match.group(1))
            if title and url and url.startswith("http"):
                results.append({"title": title, "url": url, "snippet": snippet or "(no snippet)"})
        if results:
            break

    return results[:max_results]
