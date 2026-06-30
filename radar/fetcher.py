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
    def __init__(self, timeout: int = 20, sleep: float = 0.9, debug: bool = False):
        self.timeout = timeout
        self.sleep = sleep
        self.debug = debug
        self.last_status = ""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        # DuckDuckGo possui variações de HTML. Tentamos duas rotas públicas.
        for endpoint in ("https://html.duckduckgo.com/html/", "https://duckduckgo.com/html/"):
            results = self._search_duckduckgo(endpoint, query, limit)
            if results:
                return results
        return []

    def _search_duckduckgo(self, endpoint: str, query: str, limit: int) -> list[SearchResult]:
        try:
            response = self.session.get(endpoint, params={"q": query, "kl": "br-pt"}, timeout=self.timeout)
            self.last_status = f"{endpoint} -> HTTP {response.status_code} ({len(response.text)} bytes)"
            response.raise_for_status()
        except Exception as exc:
            self.last_status = f"{endpoint} -> erro: {exc}"
            if self.debug:
                print(f"[debug-search] {self.last_status}")
            return []

        time.sleep(self.sleep)
        soup = BeautifulSoup(response.text, "html.parser")
        results: list[SearchResult] = []

        # Formato clássico do DuckDuckGo HTML.
        for item in soup.select(".result"):
            parsed = self._parse_result_item(item)
            if parsed:
                results.append(parsed)
            if len(results) >= limit:
                break

        # Fallback: anchors diretos, caso o layout mude.
        if not results:
            for link in soup.select("a[href]"):
                href = unwrap(link.get("href", ""))
                title = link.get_text(" ", strip=True)
                if not self._valid_result(title, href):
                    continue
                results.append(SearchResult(title=title, url=href, snippet=""))
                if len(results) >= limit:
                    break

        if self.debug:
            print(f"[debug-search] {self.last_status} | query={query!r} | resultados={len(results)}")
        return results

    def _parse_result_item(self, item) -> SearchResult | None:
        link = item.select_one("a.result__a") or item.select_one("a[href]")
        if not link:
            return None
        title = link.get_text(" ", strip=True)
        href = unwrap(link.get("href", ""))
        snippet_el = item.select_one(".result__snippet") or item.select_one(".result__body")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        if not self._valid_result(title, href):
            return None
        return SearchResult(title=title, url=href, snippet=snippet)

    def _valid_result(self, title: str, href: str) -> bool:
        if not title or not href.startswith(("http://", "https://")):
            return False
        blocked = ("duckduckgo.com", "javascript:", "mailto:")
        return not any(value in href for value in blocked)

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
