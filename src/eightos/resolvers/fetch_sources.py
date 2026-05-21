"""fetch-sources — inside resolver that pulls items from HN + arXiv.

Block 3 Piece 5. First node of the SCAN dogfood. Hits two public APIs
without auth:

- HackerNews: `https://hacker-news.firebaseio.com/v0/topstories.json`
  + per-story metadata at `https://hacker-news.firebaseio.com/v0/item/<id>.json`.
- arXiv: `https://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.LG&sortBy=submittedDate&sortOrder=descending`.

Returns a structured list of items each with title, url, abstract
(optional), and source label. The adapter JSON-encodes that list into
resolution_text so downstream resolvers can parse it.

Fetch limits keep the workload tractable: 10 items per source, 20
total. Per-source priority is captured in the `source` field so
filter-and-rank can use it for tie-breaking.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Any

_HN_TOPSTORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
_HN_ITEM_URL_FMT = "https://hacker-news.firebaseio.com/v0/item/{}.json"
_HN_ITEM_LINK_FMT = "https://news.ycombinator.com/item?id={}"
_ARXIV_QUERY_URL = (
    "https://export.arxiv.org/api/query"
    "?search_query=cat:cs.AI+OR+cat:cs.LG"
    "&sortBy=submittedDate&sortOrder=descending"
    "&max_results=10"
)
_HTTP_TIMEOUT_SECONDS = 30
_PER_SOURCE_LIMIT = 10


def resolve(intention_id: str) -> dict[str, Any]:
    """Fetch top items from HN and arXiv. Return structured list."""
    start = time.monotonic()
    items: list[dict[str, Any]] = []
    fetch_errors: list[str] = []

    try:
        items.extend(_fetch_hn(_PER_SOURCE_LIMIT))
    except Exception as e:  # noqa: BLE001 - network failures are tolerated
        fetch_errors.append(f"hn: {type(e).__name__}: {e}")
    try:
        items.extend(_fetch_arxiv(_PER_SOURCE_LIMIT))
    except Exception as e:  # noqa: BLE001
        fetch_errors.append(f"arxiv: {type(e).__name__}: {e}")

    elapsed_ms = (time.monotonic() - start) * 1000.0
    return {
        "items": items,
        "elapsed_ms": elapsed_ms,
        "errors": fetch_errors,
        "intention_id": intention_id,
    }


def adapt(structured: dict[str, Any]) -> dict[str, Any]:
    """Adapter — JSON-encodes the items list as resolution_text."""
    items = structured.get("items") or []
    return {
        "resolution_text": json.dumps(
            {"items": items, "errors": structured.get("errors") or []}
        ),
        "resolution_value": items,
        "cost_actual": {
            "clock_ms": float(structured.get("elapsed_ms") or 0.0),
            "coin_usd": 0.0,
            "carbon_g": 0.001,
        },
    }


def _fetch_hn(limit: int) -> list[dict[str, Any]]:
    ids = _http_get_json(_HN_TOPSTORIES_URL)
    if not isinstance(ids, list):
        return []
    out: list[dict[str, Any]] = []
    for hn_id in ids[: limit * 2]:  # over-fetch in case some are jobs/polls
        if len(out) >= limit:
            break
        try:
            meta = _http_get_json(_HN_ITEM_URL_FMT.format(hn_id))
        except Exception:  # noqa: BLE001 — skip individual failures
            continue
        if not isinstance(meta, dict) or meta.get("type") != "story":
            continue
        title = meta.get("title")
        if not title:
            continue
        url = meta.get("url") or _HN_ITEM_LINK_FMT.format(hn_id)
        out.append(
            {
                "title": title,
                "url": url,
                "abstract": "",
                "source": "hackernews",
                "source_priority": 1,
                "id": f"hn-{hn_id}",
            }
        )
    return out


_ARXIV_ENTRY_RE = re.compile(r"<entry>(.*?)</entry>", re.DOTALL)
_ARXIV_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
_ARXIV_SUMMARY_RE = re.compile(r"<summary>(.*?)</summary>", re.DOTALL)
_ARXIV_LINK_RE = re.compile(r'<link[^>]*href="([^"]+)"[^>]*rel="alternate"')
_ARXIV_ID_RE = re.compile(r"<id>http://arxiv.org/abs/([^<]+)</id>")


def _fetch_arxiv(limit: int) -> list[dict[str, Any]]:
    text = _http_get_text(_ARXIV_QUERY_URL)
    out: list[dict[str, Any]] = []
    for entry in _ARXIV_ENTRY_RE.findall(text)[:limit]:
        title_m = _ARXIV_TITLE_RE.search(entry)
        summary_m = _ARXIV_SUMMARY_RE.search(entry)
        link_m = _ARXIV_LINK_RE.search(entry)
        id_m = _ARXIV_ID_RE.search(entry)
        if not (title_m and id_m):
            continue
        title = _whitespace_collapse(title_m.group(1))
        abstract = (
            _whitespace_collapse(summary_m.group(1)) if summary_m else ""
        )
        url = (
            link_m.group(1)
            if link_m
            else f"https://arxiv.org/abs/{id_m.group(1)}"
        )
        out.append(
            {
                "title": title,
                "url": url,
                "abstract": abstract[:1500],  # cap to keep prompts tractable
                "source": "arxiv",
                "source_priority": 2,
                "id": f"arxiv-{id_m.group(1)}",
            }
        )
    return out


def _http_get_json(url: str) -> Any:
    text = _http_get_text(url)
    return json.loads(text)


def _http_get_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "8OS-SCAN-dogfood/1.0"},
    )
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SECONDS) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _whitespace_collapse(s: str) -> str:
    return " ".join(s.split())
