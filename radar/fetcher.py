from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

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

    def __init__(self, session: requests.Session, connect_timeout: int, read_timeout: int, sleep: float, debug: bool = False):
        self.session = session
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.sleep = sleep
        self.debug = debug
        self.last_status = ""

    @property
    def timeout(self) -> tuple[int, int]:
        return (self.connect_timeout, self.read_timeout)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        raise NotImplementedError

    def _valid_result(self, title: str, href: str) -> bool:
        if not title or not href.startswith(("http://", "https://")):
            return False
        blocked_domains = (
            "bing.com",
            "microsoft.com",
            "duckduckgo.com",
            "go.microsoft.com",
            "support.microsoft.com",
        )
        blocked_schemes = ("javascript:", "mailto:")
        low = href.lower()
        if any(low.startswith(value) for value in blocked_schemes):
            return False
        return not any(domain in low for domain in blocked_domains)

    def _debug(self, query: str, count: int) -> None:
        if self.debug:
            print(f"[debug-search:{self.name}] {self.last_status} | resultados={count} | {query[:90]!r}")


def _unwrap_bing_url(href: str) -> str:
    href = unwrap(href or "")
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    for key in ("u", "url", "r"):
        if key in qs and qs[key]:
            candidate = unquote(qs[key][0])
            if candidate.startswith("a1"):
                candidate = candidate[2:]
            if candidate.startswith(("http://", "https://")):
                return candidate
    return href


class DuckDuckGoProvider(SearchProvider):
    name = "duckduckgo"

    def search(self, query: str, limit: int) -> list[SearchResult]:
        endpoint = "https://html.duckduckgo.com/html/"
        try:
            response = self.session.get(endpoint, params={"q": query, "kl": "br-pt"}, timeout=self.timeout)
            self.last_status = f"HTTP {response.status_code} ({len(response.text)} bytes)"
            response.raise_for_status()
        except Exception as exc:
            self.last_status = f"erro: {exc}"
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
            if self._valid_result(title, href):
                results.append(SearchResult(title=title, url=href, snippet=snippet, provider=self.name))
            if len(results) >= limit:
                break
        self._debug(query, len(results))
        return results


class BingProvider(SearchProvider):
    name = "bing"

    def search(self, query: str, limit: int) -> list[SearchResult]:
        # O RSS do Bing é bem mais estável para automação simples que o HTML.
        results = self._search_rss(query, limit)
        if results:
            self._debug(query, len(results))
            return results
        results = self._search_html(query, limit)
        self._debug(query, len(results))
        return results

    def _search_rss(self, query: str, limit: int) -> list[SearchResult]:
        endpoint = "https://www.bing.com/search"
        try:
            response = self.session.get(
                endpoint,
                params={"q": query, "format": "rss", "cc": "br", "setlang": "pt-BR"},
                timeout=self.timeout,
            )
            self.last_status = f"RSS HTTP {response.status_code} ({len(response.text)} bytes)"
            response.raise_for_status()
        except Exception as exc:
            self.last_status = f"RSS erro: {exc}"
            return []

        soup = BeautifulSoup(response.text, "xml")
        results: list[SearchResult] = []
        for item in soup.find_all("item"):
            title = item.title.get_text(" ", strip=True) if item.title else ""
            link = item.link.get_text(" ", strip=True) if item.link else ""
            snippet = item.description.get_text(" ", strip=True) if item.description else ""
            href = _unwrap_bing_url(link)
            if self._valid_result(title, href):
                results.append(SearchResult(title=title, url=href, snippet=snippet, provider=self.name))
            if len(results) >= limit:
                break
        return results

    def _search_html(self, query: str, limit: int) -> list[SearchResult]:
        endpoint = "https://www.bing.com/search"
        try:
            response = self.session.get(endpoint, params={"q": query, "cc": "br", "setlang": "pt-BR"}, timeout=self.timeout)
            self.last_status = f"HTML HTTP {response.status_code} ({len(response.text)} bytes)"
            response.raise_for_status()
        except Exception as exc:
            self.last_status = f"HTML erro: {exc}"
            return []

        time.sleep(self.sleep)
        soup = BeautifulSoup(response.text, "html.parser")
        results: list[SearchResult] = []

        for item in soup.select("li.b_algo, .b_algo, .b_results li"):
            parsed = self._parse_bing_item(item)
            if parsed:
                results.append(parsed)
            if len(results) >= limit:
                break

        if not results:
            results = self._fallback_links(soup, limit)

        return results

    def _parse_bing_item(self, item) -> SearchResult | None:
        link = item.select_one("h2 a[href]") or item.select_one("a[href]")
        if not link:
            return None
        title = link.get_text(" ", strip=True)
        href = _unwrap_bing_url(link.get("href", ""))
        snippet_el = item.select_one(".b_caption p") or item.select_one("p")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        if self._valid_result(title, href):
            return SearchResult(title=title, url=href, snippet=snippet, provider=self.name)
        return None

    def _fallback_links(self, soup: BeautifulSoup, limit: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        seen: set[str] = set()
        for link in soup.select("a[href]"):
            title = link.get_text(" ", strip=True)
            href = _unwrap_bing_url(link.get("href", ""))
            if not self._valid_result(title, href):
                continue
            if len(title) < 4:
                continue
            if re.search(r"^(imagens|videos|noticias|maps|shopping|entrar|configura)", title, re.I):
                continue
            key = href.split("#", 1)[0].rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(SearchResult(title=title[:160], url=href, snippet="", provider=self.name))
            if len(results) >= limit:
                break
        return results


class SearxProvider(SearchProvider):
    name = "searxng"

    def __init__(self, session: requests.Session, connect_timeout: int, read_timeout: int, sleep: float, debug: bool = False, base_url: str = ""):
        super().__init__(session, connect_timeout, read_timeout, sleep, debug)
        self.base_url = (base_url or "").rstrip("/")

    def search(self, query: str, limit: int) -> list[SearchResult]:
        if not self.base_url:
            self.last_status = "não configurado"
            return []
        endpoint = f"{self.base_url}/search"
        try:
            response = self.session.get(endpoint, params={"q": query, "format": "json", "language": "pt-BR"}, timeout=self.timeout)
            self.last_status = f"HTTP {response.status_code} ({len(response.text)} bytes)"
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            self.last_status = f"erro: {exc}"
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
    def __init__(self, timeout: int = 12, sleep: float = 0.15, debug: bool = False):
        self.connect_timeout = int(os.getenv("RADAR_CONNECT_TIMEOUT", "5"))
        self.timeout = int(os.getenv("RADAR_TIMEOUT", str(timeout)))
        self.sleep = float(os.getenv("RADAR_SLEEP", str(sleep)))
        self.debug = debug
        self.deep_fetch = os.getenv("RADAR_DEEP_FETCH", "0") == "1"
        provider_names = [p.strip().lower() for p in os.getenv("RADAR_PROVIDERS", "bing,duckduckgo,searxng").split(",") if p.strip()]
        self.last_status = ""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })
        available: dict[str, SearchProvider] = {
            "duckduckgo": DuckDuckGoProvider(self.session, self.connect_timeout, self.timeout, self.sleep, debug),
            "bing": BingProvider(self.session, self.connect_timeout, self.timeout, self.sleep, debug),
            "searxng": SearxProvider(self.session, self.connect_timeout, self.timeout, self.sleep, debug, os.getenv("RADAR_SEARX_URL", "")),
        }
        self.providers = [available[name] for name in provider_names if name in available]

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        seen: set[str] = set()
        merged: list[SearchResult] = []
        statuses: list[str] = []
        per_provider_limit = max(3, min(limit, 5))

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
        if not self.deep_fetch:
            return ""
        try:
            response = self.session.get(url, timeout=(self.connect_timeout, self.timeout))
            if response.status_code >= 400:
                return ""
            if "pdf" in response.headers.get("content-type", "").lower():
                return ""
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()
            return soup.get_text(" ", strip=True)[:12000]
        except Exception:
            return ""
