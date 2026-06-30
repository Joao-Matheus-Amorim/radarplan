from __future__ import annotations

import html
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from bs4 import BeautifulSoup

from radar.fetcher import SearchResult


BLOCKED_HOSTS = (
    "google.com",
    "google.com.br",
    "gstatic.com",
    "googleusercontent.com",
    "accounts.google.com",
    "support.google.com",
    "policies.google.com",
    "webcache.googleusercontent.com",
    "googleadservices.com",
    "doubleclick.net",
)


def _clean(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _host(url: str) -> str:
    try:
        host = urlparse(url or "").netloc.lower()
    except Exception:
        return ""

    if host.startswith("www."):
        host = host[4:]

    return host


def _unwrap_google_url(url: str) -> str:
    url = html.unescape(url or "")

    if url.startswith("/url?"):
        url = "https://www.google.com" + url

    if url.startswith("//"):
        url = "https:" + url

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    for key in ("q", "url"):
        if key in qs and qs[key]:
            target = unquote(qs[key][0])

            if target.startswith(("http://", "https://")):
                return target

    return url


def _valid_result(title: str, url: str) -> bool:
    if not title or not url.startswith(("http://", "https://")):
        return False

    host = _host(url)

    if not host:
        return False

    if any(host == blocked or host.endswith("." + blocked) for blocked in BLOCKED_HOSTS):
        return False

    if "/search?" in url or "/preferences" in url or "/settings" in url:
        return False

    return True


def _is_blocked_page(body_text: str) -> bool:
    body_text = (body_text or "").lower()

    blocked_terms = (
        "não sou um robô",
        "nao sou um robo",
        "não sou robô",
        "nao sou robo",
        "tráfego incomum",
        "trafego incomum",
        "unusual traffic",
        "captcha",
        "our systems have detected",
    )

    return any(term in body_text for term in blocked_terms)


class GoogleBrowserProvider:
    name = "google_browser"

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.last_status = ""

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            self.last_status = f"playwright não instalado: {exc}"
            return []

        profile_dir = Path(os.getenv("RADAR_GOOGLE_BROWSER_PROFILE", "data/google_browser_profile"))
        profile_dir.mkdir(parents=True, exist_ok=True)

        url = (
            "https://www.google.com/search"
            f"?q={quote_plus(query)}"
            "&hl=pt-BR&gl=br&pws=0&filter=0"
        )

        results: list[SearchResult] = []
        seen: set[str] = set()

        with sync_playwright() as p:
            context = None

            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=False,
                    locale="pt-BR",
                    viewport={"width": 1366, "height": 900},
                )

                page = context.pages[0] if context.pages else context.new_page()

                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3500)
                self._accept_google_consent(page)

                body_text = self._safe_body_text(page)

                if _is_blocked_page(body_text):
                    if os.getenv("RADAR_CAPTCHA_MANUAL", "0") == "1":
                        print("")
                        print("[google-browser] O Google pediu captcha.")
                        print("[google-browser] Resolva na janela do navegador.")
                        print("[google-browser] NÃO feche a janela.")
                        print("[google-browser] Depois volte aqui e pressione ENTER.")
                        input()

                        if page.is_closed():
                            self.last_status = "janela fechada durante captcha"
                            return []

                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=45000)
                            page.wait_for_timeout(3500)
                        except Exception as exc:
                            self.last_status = f"falha ao recarregar após captcha: {exc}"
                            return []

                        body_text = self._safe_body_text(page)

                        if _is_blocked_page(body_text):
                            self.last_status = "captcha ainda ativo"
                            return []
                    else:
                        self.last_status = "captcha/bloqueio no navegador"
                        return []

                html_text = page.content()

                if os.getenv("RADAR_GOOGLE_SAVE_HTML", "0") == "1":
                    Path("data").mkdir(exist_ok=True)
                    Path("data/google_browser_debug.html").write_text(html_text, encoding="utf-8", errors="ignore")

                soup = BeautifulSoup(html_text, "html.parser")

                for item in soup.select("div.g, div.MjjYud, div.tF2Cxc, div.SoaBEf, div[data-sokoban-container], li"):
                    item_text = _clean(item.get_text(" ", strip=True)).lower()

                    if self._is_ad_text(item_text):
                        continue

                    parsed = self._parse_item(item)

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
                    for link in soup.select("a[href]"):
                        href = _unwrap_google_url(link.get("href", ""))
                        title = _clean(link.get_text(" ", strip=True))

                        if not title:
                            h3 = link.select_one("h3")
                            title = _clean(h3.get_text(" ", strip=True)) if h3 else ""

                        link_text = _clean(link.get_text(" ", strip=True)).lower()
                        parent_text = _clean(link.parent.get_text(" ", strip=True)).lower() if link.parent else ""

                        if self._is_ad_text(link_text) or self._is_ad_text(parent_text):
                            continue

                        if not _valid_result(title, href):
                            continue

                        key = href.split("#", 1)[0].rstrip("/").lower()

                        if key in seen:
                            continue

                        seen.add(key)
                        results.append(SearchResult(title=title[:160], url=href, snippet="", provider=self.name))

                        if len(results) >= limit:
                            break

                self.last_status = f"browser resultados={len(results)}"

            except Exception as exc:
                self.last_status = f"erro navegador: {exc}"
                return []

            finally:
                if context is not None:
                    try:
                        context.close()
                    except Exception:
                        pass

        return results[:limit]

    def _safe_body_text(self, page) -> str:
        try:
            if page.is_closed():
                return ""

            return page.locator("body").inner_text(timeout=8000)
        except Exception:
            return ""

    def _accept_google_consent(self, page) -> None:
        labels = (
            "Aceitar tudo",
            "Concordo",
            "I agree",
            "Accept all",
            "Reject all",
            "Rejeitar tudo",
        )

        for label in labels:
            try:
                locator = page.get_by_text(label, exact=True)

                if locator.count() > 0:
                    locator.first.click(timeout=1500)
                    page.wait_for_timeout(1000)
                    return
            except Exception:
                pass

    def _is_ad_text(self, text: str) -> bool:
        text = (text or "").lower()

        return (
            "resultado patrocinado" in text
            or "patrocinado" in text
            or "minha central de anúncios" in text
            or "minha central de anuncios" in text
        )

    def _parse_item(self, item) -> SearchResult | None:
        h3 = item.select_one("h3")
        link = h3.find_parent("a") if h3 else None

        if not link:
            link = item.select_one("a[href]")

        if not link:
            return None

        url = _unwrap_google_url(link.get("href", ""))
        title = _clean(h3.get_text(" ", strip=True)) if h3 else _clean(link.get_text(" ", strip=True))

        if not _valid_result(title, url):
            return None

        snippet = _clean(item.get_text(" ", strip=True))

        if title and title in snippet:
            snippet = snippet.replace(title, " ", 1).strip()

        return SearchResult(
            title=title[:160],
            url=url,
            snippet=snippet[:500],
            provider=self.name,
        )
