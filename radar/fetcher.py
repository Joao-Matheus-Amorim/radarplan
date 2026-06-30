from __future__ import annotations

import os
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
    provider: str = ""


class SearchProvider:
    name = "base"

    def __init__(self, session: requests.Session, timeout: int, sleep: float, debug: bool = False):
        self.session = session
        self.timeout = timeout
        self.sleep = sleep
        self.debug = debug
        self.last_status = ""

    def search(self, query: str, limit: int) -> list[SearchResult]:
        raise NotImplementedError

    def _valid_result(self, title: str, href: str) -> bool:
        if not title or not href.startswith(("http://", "https://")):
            return False
        blocked = ("javascript:", "mailto:")
        return not any(value in href for value in blocked)

    def _debug(self, query: str, count: int) -> None:
        if self.debug:
            print(f"[debug-search:{self.name}] {self.last_status} | query={query!r} | resultados={count}")


class DuckDuckGoProvider(SearchProvider):
    name = "duckduckgo"

    def search(self, query: str, limit: int) -> list[SearchResult]:
        for endpoint in ("https://html.duckduckgo.com/html/", "https://duckduckgo.com/html/"):
            results = self._search_endpoint(endpoint, query, limit)
            if results:
                return results
        return []

    def _search_endpoint(self, endpoint: str, query: str, limit: int) -> list[SearchResult]:
        try:
            response = self.session.get(endpoint, params={"q": query, "kl": "br-pt"}, timeout=self.timeout)
            self.last_status = f"{endpoint} -> HTTP {response.status_code} ({len(response.text)} bytes)"
            response.raise_for_status()
        except Exception as exc:
            self.last_status = f"{endpoint} -> erro: {exc}"
            self._debug(query, 0)
            return []

        time.sleep(self.sleep)
        soup = BeautifulSoup(response.text, "html.parser")
        results: list[SearchResult] = []

        for item in soup.select(".result"):
            link = item.select_one("a.result__a") or item.select_one("a[href]")
            if not link:
                continue
            title = link.get_text(" ", strip=True)
            href = unwrap(link.get("href", ""))
            snippet_el = item.select_one(".result__snippet") or item.select_one(".result__body")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            if self._valid_result(title, href) and "duckduckgo.com" not in href:
                results.append(SearchResult(title=title, url=href, snippet=snippet, provider=self.name))
            if len(results) >= limit:
                break

        if not results:
            for link in soup.select("a[href]"):
                title = link.get_text(" ", strip=True)
                href = unwrap(link.get("href", ""))
                if self._valid_result(title, href) and "duckduckgo.com" not in href:
                    results.append(SearchResult(title=title, url=href, snippet="", provider=self.name))
                if len(results) >= limit:
                    break

        self._debug(query, len(results))
        return results


class BingProvider(SearchProvider):
    name = "bing"

    def search(self, query: str, limit: int) -> list[SearchResult]:
        endpoint = "https://www.bing.com/search"
        try:
            response = self.session.get(endpoint, params={"q": query, "cc": "br", "setlang": "pt-BR"}, timeout=self.timeout)
            self.last_status = f"{endpoint} -> HTTP {response.status_code} ({len(response.text)} bytes)"
            response.raise_for_status()
        except Exception as exc:
            self.last_status = f"{endpoint} -> erro: {exc}"
            self._debug(query, 0)
            return []

        time.sleep(self.sleep)
        soup = BeautifulSoup(response.text, "html.parser")
        results: list[SearchResult] = []
        for item in soup.select("li.b_algo"):
            link = item.select_one("h2 a[href]") or item.select_one("a[href]")
            if not link:
                continue
            title = link.get_text(" ", strip=True)
            href = unwrap(link.get("href", ""))
            snippet_el = item.select_one(".b_caption p") or item.select_one("p")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            if self._valid_result(title, href) and "bing.com" not in href:
                results.append(SearchResult(title=title, url=href, snippet=snippet, provider=self.name))
            if len(results) >= limit:
                break
        self._debug(query, len(results))
        return results


class SearxProvider(SearchProvider):
    name = "searxng"

    def __init__(self, session: requests.Session, timeout: int, sleep: float, debug: bool = False, base_url: str = ""):
        super().__init__(session, timeout, sleep, debug)
        self.base_url = (base_url or "").rstrip("/")

    def search(self, query: str, limit: int) -> list[SearchResult]:
        if not self.base_url:
            self.last_status = "RADAR_SEARX_URL não configurado"
            self._debug(query, 0)
            return []
        endpoint = f"{self.base_url}/search"
        try:
            response = self.session.get(endpoint, params={"q": query, "format": "json", "language": "pt-BR"}, timeout=self.timeout)
            self.last_status = f"{endpoint} -> HTTP {response.status_code} ({len(response.text)} bytes)"
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            self.last_status = f"{endpoint} -> erro: {exc}"
            self._debug(query, 0)
            return []

        time.sleep(self.sleep)
        results: list[SearchResult] = []
        for item in data.get("results", []):
            title = str(item.get("title") or "").strip()
            href = unwrap(str(item.get("url") or ""))
            snippet = str(item.get("content") or "").strip()
            if self._valid_result(title, href):
                results.append(SearchResult(title=title, url=href, snippet=snippet, provider=self.name))
            if len(results) >= limit:
                break
        self._debug(query, len(results))
        return results


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
        self.providers: list[SearchProvider] = [
            DuckDuckGoProvider(self.session, timeout, sleep, debug),
            BingProvider(self.session, timeout, sleep, debug),
            SearxProvider(self.session, timeout, sleep, debug, os.getenv("RADAR_SEARX_URL", "")),
        ]

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        seen: set[str] = set()
        merged: list[SearchResult] = []
        statuses: list[str] = []
        per_provider_limit = max(limit, 5)

        for provider in self.providers:
            results = provider.search(query, per_provider_limit)
            statuses.append(f"{provider.name}: {provider.last_status}")
            for result in results:
                key = result.url.split("#", 1)[0].rstrip("/").lower()
                if key in seen:
                    continue
                seen.add(key)
                merged.append(result)
                if len(merged) >= limit:
                    self.last_status = " | ".join(statuses)
                    return merged

        self.last_status = " | ".join(statuses)
        return merged

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
