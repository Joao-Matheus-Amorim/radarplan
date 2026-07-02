from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from radar.text_utils import emails, phones


USER_AGENT = (
    "RadarPME/1.0 contato-local "
    "(lead enrichment; respeita sites públicos)"
)

CONTACT_PATHS = (
    "",
    "/contato",
    "/contatos",
    "/fale-conosco",
    "/sobre",
    "/quem-somos",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return

    fields = list(rows[0].keys())

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _base_url(url: str) -> str:
    parsed = urlparse(url or "")

    if not parsed.scheme or not parsed.netloc:
        return ""

    return f"{parsed.scheme}://{parsed.netloc}"


def _is_fetchable(url: str) -> bool:
    host = urlparse(url or "").netloc.lower()

    blocked = (
        "instagram.com",
        "facebook.com",
        "linkedin.com",
        "doctoralia.com.br",
    )

    return bool(url.startswith(("http://", "https://"))) and not any(
        host == domain or host.endswith("." + domain)
        for domain in blocked
    )


def _clean_text(value: str) -> str:
    value = value or ""
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _extract_whatsapp_links(soup: BeautifulSoup) -> list[str]:
    found: list[str] = []

    for link in soup.select("a[href]"):
        href = link.get("href", "")

        if "wa.me/" in href or "api.whatsapp.com" in href or "web.whatsapp.com" in href:
            digits = re.sub(r"\D+", "", href)

            if len(digits) >= 10:
                if digits.startswith("55") and len(digits) > 11:
                    digits = digits[2:]

                found.append(digits)

    return found


def _fetch_text(session: requests.Session, url: str) -> str:
    try:
        response = session.get(url, timeout=(5, 15), allow_redirects=True)

        if response.status_code >= 400:
            return ""

        content_type = response.headers.get("content-type", "").lower()

        if "pdf" in content_type or "image/" in content_type:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        link_text = " ".join(
            link.get("href", "")
            for link in soup.select("a[href]")
        )

        visible_text = soup.get_text(" ", strip=True)
        whatsapp_numbers = " ".join(_extract_whatsapp_links(soup))

        return _clean_text(f"{visible_text} {link_text} {whatsapp_numbers}")

    except Exception:
        return ""


def _candidate_urls(url: str) -> list[str]:
    base = _base_url(url)

    if not base:
        return []

    urls = []

    for path in CONTACT_PATHS:
        urls.append(urljoin(base, path))

    return list(dict.fromkeys(urls))


def _first_missing(row: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        value = (row.get(name) or "").strip()

        if value:
            return value

    return ""


def enrich_row(session: requests.Session, row: dict[str, str], debug: bool = False) -> dict[str, str]:
    url = _first_missing(row, ("site", "url_origem", "url"))

    if not _is_fetchable(url):
        row["enriquecido"] = "nao_fetchable"
        return row

    blob_parts: list[str] = []

    for candidate in _candidate_urls(url):
        if debug:
            print(f"[enrich] lendo: {candidate}")

        text = _fetch_text(session, candidate)

        if text:
            blob_parts.append(text)

        if len(" ".join(blob_parts)) >= 20000:
            break

    blob = " ".join(blob_parts)
    found_phones = phones(blob)
    found_emails = emails(blob)

    current_phone = (row.get("telefone") or "").strip()
    current_whatsapp = (row.get("whatsapp") or "").strip()
    current_email = (row.get("email") or "").strip()

    if not current_phone and found_phones:
        row["telefone"] = found_phones[0]

    if not current_whatsapp:
        whatsapp_hint = ""

        for phone in found_phones:
            if len(re.sub(r"\D+", "", phone)) >= 10:
                whatsapp_hint = phone
                break

        if whatsapp_hint:
            row["whatsapp"] = whatsapp_hint

    if not current_email and found_emails:
        row["email"] = found_emails[0]

    if found_phones or found_emails:
        row["enriquecido"] = "sim"
    else:
        row["enriquecido"] = "sem_contato_extra"

    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Enriquece leads já encontrados sem usar Google.")
    parser.add_argument("--entrada", default="exports/fila_do_dia.csv")
    parser.add_argument("--saida", default="exports/fila_enriquecida.csv")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    entrada = Path(args.entrada)
    saida = Path(args.saida)

    rows = _read_csv(entrada)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )

    enriched = []

    for index, row in enumerate(rows, start=1):
        empresa = row.get("empresa") or row.get("name") or "sem nome"
        print(f"[{index}/{len(rows)}] {empresa}")
        enriched.append(enrich_row(session, row, args.debug))

    _write_csv(saida, enriched)
    print(f"Arquivo gerado: {saida}")


if __name__ == "__main__":
    main()
