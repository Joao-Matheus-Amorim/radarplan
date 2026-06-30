from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse, parse_qs, unquote

PHONE_RE = re.compile(r"(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\s?)?\d{4}[-.\s]?\d{4}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.lower().split())


def has_any(text: str, terms: list[str]) -> bool:
    low = norm(text)
    return any(norm(term) in low for term in terms)


def clean_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip(" -|•\n\t")
    parts = [p.strip() for p in re.split(r"[|•]", value) if p.strip()] or [value]
    block = ["linkedin", "gupy", "indeed", "glassdoor", "facebook", "instagram", "google"]
    for part in parts:
        if len(part) > 2 and not any(b in norm(part) for b in block):
            return part[:120]
    return (value or "Empresa não identificada")[:120]


def phones(text: str) -> list[str]:
    out: list[str] = []
    for match in PHONE_RE.findall(text or ""):
        phone = re.sub(r"\s+", " ", match).strip()
        digits = re.sub(r"\D", "", phone)
        if 10 <= len(digits) <= 13 and phone not in out:
            out.append(phone)
    return out[:5]


def emails(text: str) -> list[str]:
    out: list[str] = []
    for email in EMAIL_RE.findall(text or ""):
        if email.lower() not in [x.lower() for x in out]:
            out.append(email)
    return out[:5]


def unwrap(url: str) -> str:
    parsed = urlparse(url or "")
    qs = parse_qs(parsed.query)
    for key in ("uddg", "url", "u"):
        if key in qs and qs[key]:
            return unquote(qs[key][0])
    return url or ""
