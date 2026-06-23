"""Domain discovery via web search."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from duckduckgo_search import DDGS

from websitescorecard.url_utils import parse_url

OVERSAMPLE_FACTOR = 5


def normalize_suffixes(suffixes: Sequence[str] | None) -> list[str] | None:
    """Normalize suffixes: strip dots, lowercase, dedupe, longest-first."""
    if suffixes is None:
        return None

    normalized: list[str] = []
    for suffix in suffixes:
        cleaned = suffix.strip().lower().lstrip(".")
        if cleaned:
            normalized.append(cleaned)

    if not normalized:
        return None

    return sorted(set(normalized), key=len, reverse=True)


def matches_suffix(hostname: str, suffixes: Sequence[str] | None) -> bool:
    """Return True if hostname matches any allowed suffix."""
    if not suffixes:
        return True

    host = hostname.lower().rstrip(".")
    normalized = normalize_suffixes(suffixes)
    if not normalized:
        return True

    for suffix in normalized:
        if host == suffix or host.endswith("." + suffix):
            return True
    return False


def extract_hostname(url: str) -> str | None:
    """Extract registrable hostname from a URL, stripping www."""
    try:
        parsed = parse_url(url)
    except ValueError:
        return None

    hostname = parsed.hostname.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def hostnames_from_results(
    results: Iterable[dict[str, str]],
    *,
    suffixes: Sequence[str] | None = None,
) -> list[str]:
    """Extract unique hostnames from search results, optionally filtered by suffix."""
    seen: set[str] = set()
    hostnames: list[str] = []

    for result in results:
        href = result.get("href") or result.get("url") or ""
        hostname = extract_hostname(href)
        if not hostname or hostname in seen:
            continue
        if not matches_suffix(hostname, suffixes):
            continue
        seen.add(hostname)
        hostnames.append(hostname)

    return hostnames


def search_domains(
    query: str,
    *,
    limit: int = 1,
    suffixes: Sequence[str] | None = None,
    oversample_factor: int = OVERSAMPLE_FACTOR,
    timeout: int | None = None,
) -> list[str]:
    """Search for domains matching a query, filtered by optional hostname suffixes."""
    if limit < 1:
        return []

    max_results = max(limit * oversample_factor, limit)
    ddgs_kwargs: dict[str, int] = {}
    if timeout is not None:
        ddgs_kwargs["timeout"] = timeout

    with DDGS(**ddgs_kwargs) as ddgs:
        results = ddgs.text(query, max_results=max_results)

    hostnames = hostnames_from_results(results, suffixes=suffixes)
    return hostnames[:limit]
