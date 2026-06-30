from __future__ import annotations

import html
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

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
            "search.yahoo.com",
            "mojeek.com/search",
            "google.com",
            "google.com.br",
            "gstatic.com",
            "googleusercontent.com",
            "accounts.google.com",
            "support.google.com",
            "policies.google.com",
            "webcache.googleusercontent.com",
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


def _unwrap_yahoo_url(href: str) -> str:
    href = unwrap(href or "")
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)

    for key in ("RU", "u", "url"):
        if key in qs and qs[key]:
            candidate = unquote(qs[key][0])

            if candidate.startswith(("http://", "https://")):
                return candidate

    return href


def _unwrap_google_url(href: str) -> str:
    href = html.unescape(unwrap(href or ""))

    if href.startswith("/url?"):
        href = "https://www.google.com" + href

    parsed = urlparse(href)
    qs = parse_qs(parsed.query)

    for key in ("q", "url"):
        if key in qs and qs[key]:
            candidate = unquote(qs[key][0])

            if candidate.startswith(("http://", "https://")):
                return candidate

    return href


def _strip_html(value: str) -> str:
    if not value:
        return ""

    return BeautifulSoup(html.unescape(value), "html.parser").get_text(" ", strip=True)


def _parse_rss_items(xml_bytes: bytes, provider: str, limit: int, validator, unwrap_url=lambda x: x) -> list[SearchResult]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    results: list[SearchResult] = []

    for item in root.findall(".//item"):
        title = _strip_html(item.findtext("title", ""))
        link = item.findtext("link", "") or ""
        snippet = _strip_html(item.findtext("description", ""))
        href = unwrap_url(link)

        if validator(title, href):
            results.append(SearchResult(title=title, url=href, snippet=snippet, provider=provider))

        if len(results) >= limit:
            break

    return results


def _site_filters(query: str) -> list[str]:
    sites: list[str] = []

    for match in re.finditer(r"(?:^|\s)site:([^\s]+)", query or "", flags=re.I):
        domain = match.group(1).strip().strip('"\'()[]{}')
        domain = domain.replace("*.", "").lower()

        if domain:
            sites.append(domain)

    return sites


def _host(url: str) -> str:
    try:
        host = urlparse(url or "").netloc.lower()
    except Exception:
        return ""

    if host.startswith("www."):
        host = host[4:]

    return host


def _matches_site_filter(url: str, site: str) -> bool:
    host = _host(url)
    site = (site or "").lower().lstrip(".")

    if site.startswith("www."):
        site = site[4:]

    return bool(host and site and (host == site or host.endswith("." + site)))


class GoogleProvider(SearchProvider):
    name = "google"

    def search(self, query: str, limit: int) -> list[SearchResult]:
        endpoint = "https://www.google.com/search"
        num = max(10, min(20, limit * 3))

        try:
            response = self.session.get(
                endpoint,
                params={
                    "q": query,
                    "num": num,
                    "hl": "pt-BR",
                    "gl": "br",
                    "pws": "0",
                },
                timeout=self.timeout,
            )
            self.last_status = f"HTTP {response.status_code} ({len(response.text)} bytes)"

            if response.status_code in {429, 503}:
                self.last_status = f"bloqueado/limite HTTP {response.status_code}"
                self._debug(query, 0)
                return []

            response.raise_for_status()

        except Exception as exc:
            self.last_status = f"erro: {exc}"
            self._debug(query, 0)
            return []

        time.sleep(self.sleep)

        lower_text = response.text.lower()
        final_url = str(response.url).lower()

        if "/sorry/" in final_url or "unusual traffic" in lower_text or "nossos sistemas detectaram tráfego incomum" in lower_text:
            self.last_status = "bloqueado/captcha"
            self._debug(query, 0)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        results: list[SearchResult] = []
        seen: set[str] = set()

        containers = soup.select("div.g, div.MjjYud, div.SoaBEf, div[data-sokoban-container]")

        if not containers:
            containers = soup.select("div")

        for item in containers:
            parsed = self._parse_google_item(item)

            if not parsed:
                continue

            key = parsed.url.split("#", 1)[0].rstrip("/").lower()

            if key in seen:
                continue

            seen.add(key)
            results.append(parsed)

            if len(results) >= limit:
                break

        if not results:
            results = self._fallback_links(soup, limit)

        self._debug(query, len(results))
        return results

    def _parse_google_item(self, item) -> SearchResult | None:
        heading = item.select_one("h3")

        if not heading:
            return None

        link = heading.find_parent("a")

        if not link:
            link = item.select_one("a[href]")

        if not link:
            return None

        title = heading.get_text(" ", strip=True)
        href = _unwrap_google_url(link.get("href", ""))

        if not self._valid_result(title, href):
            return None

        text = item.get_text(" ", strip=True)
        snippet = text.replace(title, " ", 1)
        snippet = re.sub(r"\s+", " ", snippet).strip()

        return SearchResult(title=title[:160], url=href, snippet=snippet[:500], provider=self.name)

    def _fallback_links(self, soup: BeautifulSoup, limit: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        seen: set[str] = set()

        for link in soup.select("a[href]"):
            href = _unwrap_google_url(link.get("href", ""))
            title = link.get_text(" ", strip=True)

            if not title:
                h3 = link.select_one("h3")
                title = h3.get_text(" ", strip=True) if h3 else ""

            if not self._valid_result(title, href):
                continue

            if len(title) < 4:
                continue

            if re.search(r"^(imagens|videos|vídeos|notícias|noticias|maps|shopping|entrar|configura|fazer login)$", title, re.I):
                continue

            key = href.split("#", 1)[0].rstrip("/").lower()

            if key in seen:
                continue

            seen.add(key)
            results.append(SearchResult(title=title[:160], url=href, snippet="", provider=self.name))

            if len(results) >= limit:
                break

        return results


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

        results = _parse_rss_items(response.content, self.name, limit, self._valid_result, _unwrap_bing_url)

        if not results and response.text:
            self.last_status = f"RSS sem itens ({len(response.text)} bytes)"

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


class YahooProvider(SearchProvider):
    name = "yahoo"

    def search(self, query: str, limit: int) -> list[SearchResult]:
        results = self._search_rss(query, limit)

        if results:
            self._debug(query, len(results))
            return results

        results = self._search_html(query, limit)
        self._debug(query, len(results))
        return results

    def _search_rss(self, query: str, limit: int) -> list[SearchResult]:
        endpoint = "https://search.yahoo.com/rss"

        try:
            response = self.session.get(endpoint, params={"p": query}, timeout=self.timeout)
            self.last_status = f"RSS HTTP {response.status_code} ({len(response.text)} bytes)"
            response.raise_for_status()
        except Exception as exc:
            self.last_status = f"RSS erro: {exc}"
            return []

        return _parse_rss_items(response.content, self.name, limit, self._valid_result, _unwrap_yahoo_url)

    def _search_html(self, query: str, limit: int) -> list[SearchResult]:
        endpoint = "https://search.yahoo.com/search"

        try:
            response = self.session.get(endpoint, params={"p": query}, timeout=self.timeout)
            self.last_status = f"HTML HTTP {response.status_code} ({len(response.text)} bytes)"
            response.raise_for_status()
        except Exception as exc:
            self.last_status = f"HTML erro: {exc}"
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        results: list[SearchResult] = []
        seen: set[str] = set()

        for item in soup.select("div#web li, .algo, .dd"):
            link = item.select_one("h3 a[href]") or item.select_one("a[href]")

            if not link:
                continue

            title = link.get_text(" ", strip=True)
            href = _unwrap_yahoo_url(link.get("href", ""))
            snippet_el = item.select_one(".compText, .fc-falcon, p")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            key = href.split("#", 1)[0].rstrip("/").lower()

            if key in seen or not self._valid_result(title, href):
                continue

            seen.add(key)
            results.append(SearchResult(title=title, url=href, snippet=snippet, provider=self.name))

            if len(results) >= limit:
                break

        return results


class MojeekProvider(SearchProvider):
    name = "mojeek"

    def search(self, query: str, limit: int) -> list[SearchResult]:
        endpoint = "https://www.mojeek.com/search"

        try:
            response = self.session.get(endpoint, params={"q": query}, timeout=self.timeout)
            self.last_status = f"HTTP {response.status_code} ({len(response.text)} bytes)"
            response.raise_for_status()
        except Exception as exc:
            self.last_status = f"erro: {exc}"
            self._debug(query, 0)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        results: list[SearchResult] = []
        seen: set[str] = set()

        for item in soup.select("li, .result, .results-standard .r"):
            link = item.select_one("h2 a[href], h3 a[href], a[href]")

            if not link:
                continue

            title = link.get_text(" ", strip=True)
            href = unwrap(link.get("href", ""))

            if href.startswith("/"):
                href = "https://www.mojeek.com" + href

            snippet_el = item.select_one("p, .s, .desc")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            key = href.split("#", 1)[0].rstrip("/").lower()

            if key in seen or not self._valid_result(title, href):
                continue

            seen.add(key)
            results.append(SearchResult(title=title[:160], url=href, snippet=snippet[:500], provider=self.name))

            if len(results) >= limit:
                break

        self._debug(query, len(results))
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
        provider_names = [
            p.strip().lower()
            for p in os.getenv("RADAR_PROVIDERS", "google,duckduckgo,bing,yahoo,mojeek,searxng").split(",")
            if p.strip()
        ]
        self.last_status = ""
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": os.getenv("RADAR_USER_AGENT", USER_AGENT),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
            }
        )
        available: dict[str, SearchProvider] = {
            "google": GoogleProvider(self.session, self.connect_timeout, self.timeout, self.sleep, debug),
            "duckduckgo": DuckDuckGoProvider(self.session, self.connect_timeout, self.timeout, self.sleep, debug),
            "bing": BingProvider(self.session, self.connect_timeout, self.timeout, self.sleep, debug),
            "yahoo": YahooProvider(self.session, self.connect_timeout, self.timeout, self.sleep, debug),
            "mojeek": MojeekProvider(self.session, self.connect_timeout, self.timeout, self.sleep, debug),
            "searxng": SearxProvider(self.session, self.connect_timeout, self.timeout, self.sleep, debug, os.getenv("RADAR_SEARX_URL", "")),
        }
        self.providers = [available[name] for name in provider_names if name in available]

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        seen: set[str] = set()
        merged: list[SearchResult] = []
        statuses: list[str] = []
        per_provider_limit = max(3, min(limit, 8))
        site_filters = _site_filters(query)

        for provider in self.providers:
            results = provider.search(query, per_provider_limit)
            statuses.append(f"{provider.name}: {provider.last_status}")

            for result in results:
                if site_filters and not any(_matches_site_filter(result.url, site) for site in site_filters):
                    if self.debug:
                        print(f"[debug-search] descartado por site:{','.join(site_filters)} -> {result.url[:120]}")
                    continue

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
