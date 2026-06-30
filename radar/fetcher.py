from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from radar.config import USER_AGENT
from radar.text_utils import unwrap


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class Fetcher:
    def __init__(self, timeout: int = 15, sleep: float = 0.7):
        self.timeout = timeout
        self.sleep = sleep
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        url = "https://duckduckgo.com/html/?" + urlencode({"q": query})
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except Exception:
            return []
        time.sleep(self.sleep)
        soup = BeautifulSoup(response.text, "html.parser")
        results: list[SearchResult] = []
        for item in soup.select(".result"):
            link = item.select_one("a.result__a") or item.select_one("a")
            if not link:
                continue
            title = link.get_text(" ", strip=True)
            href = unwrap(link.get("href", ""))
            snippet_el = item.select_one(".result__snippet")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            if title and href:
                results.append(SearchResult(title=title, url=href, snippet=snippet))
            if len(results) >= limit:
                break
        return results

    def text(self, url: str) -> str:
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code >= 400:
                return ""
            if "pdf" in response.headers.get("content-type", "").lower():
                return ""
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()
            return soup.get_text(" ", strip=True)[:20000]
        except Exception:
            return ""
