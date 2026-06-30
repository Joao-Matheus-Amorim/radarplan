from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from radar.models import Lead
from radar.text_utils import clean_name, emails, phones


GOOGLE_IMPORT_SOURCE = "google_import"

REGION_ALIASES = {
    "piabeta": [
        "Piabetá",
        "Piabeta",
        "Magé",
        "Mage",
        "Fragoso",
        "Vila Inhomirim",
        "Raiz da Serra",
        "Pau Grande",
    ],
    "mage": [
        "Magé",
        "Mage",
        "Piabetá",
        "Piabeta",
        "Fragoso",
        "Vila Inhomirim",
        "Raiz da Serra",
        "Pau Grande",
    ],
}

SEGMENT_ALIASES = {
    "clínica odontológica": [
        "dentista",
        "odontologia",
        "odonto",
        "odontológica",
        "odontologica",
        "clínica odontológica",
        "clinica odontologica",
        "consultório odontológico",
        "consultorio odontologico",
        "clínica dentária",
        "clinica dentaria",
        "ortodontia",
        "implante",
        "prótese",
        "protese",
    ],
    "clínica médica": [
        "clínica",
        "clinica",
        "médico",
        "medico",
        "saúde",
        "saude",
        "consultório",
        "consultorio",
        "consulta",
        "hospital",
    ],
    "laboratório": [
        "laboratório",
        "laboratorio",
        "exames",
        "análises clínicas",
        "analises clinicas",
        "coleta",
    ],
    "escritório contábil": [
        "contabilidade",
        "contador",
        "contábil",
        "contabil",
        "escritório contábil",
        "escritorio contabil",
    ],
    "escritório de advocacia": [
        "advocacia",
        "advogado",
        "advogada",
        "jurídico",
        "juridico",
        "escritório de advocacia",
        "escritorio de advocacia",
    ],
    "empresa de engenharia": [
        "engenharia",
        "engenheiro",
        "obras",
        "construção",
        "construcao",
        "projetos",
    ],
    "agência de marketing": [
        "marketing",
        "publicidade",
        "propaganda",
        "social media",
        "design",
        "agência",
        "agencia",
    ],
    "escola particular": [
        "escola",
        "colégio",
        "colegio",
        "creche",
        "berçário",
        "bercario",
        "educação infantil",
        "educacao infantil",
    ],
    "clínica veterinária": [
        "veterinária",
        "veterinaria",
        "pet",
        "banho e tosa",
        "animal",
    ],
    "clínica de fisioterapia": [
        "fisioterapia",
        "pilates",
        "reabilitação",
        "reabilitacao",
        "fisio",
    ],
    "medicina do trabalho": [
        "medicina do trabalho",
        "ocupacional",
        "aso",
        "admissional",
        "demissional",
        "segurança do trabalho",
        "seguranca do trabalho",
    ],
}

BLOCKED_DOMAINS = (
    "google.com",
    "google.com.br",
    "gstatic.com",
    "googleusercontent.com",
    "youtube.com",
    "youtu.be",
    "support.google.com",
    "accounts.google.com",
    "policies.google.com",
    "maps.google.com",
)

DIRECTORY_DOMAINS = (
    "doctoralia.com.br",
    "guiamais.com.br",
    "apontador.com.br",
    "solutudo.com.br",
    "guiafacil.com",
    "telelistas.net",
    "cnpj.biz",
    "econodata.com.br",
)

SOCIAL_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
)

UI_NOISE = (
    "fazer login",
    "login",
    "imagens",
    "notícias",
    "noticias",
    "shopping",
    "maps",
    "vídeos",
    "videos",
    "ferramentas",
    "todos",
    "mais",
    "rotas",
    "ligar",
    "salvar",
    "compartilhar",
    "avaliar",
    "ver por fora",
    "sugerir uma alteração",
    "sugerir uma alteracao",
    "é proprietário desta empresa?",
    "e proprietario desta empresa?",
    "pedir ao gemini",
)

BUSINESS_WORDS = (
    "clínica",
    "clinica",
    "odonto",
    "odontologia",
    "dentista",
    "laboratório",
    "laboratorio",
    "company",
    "saúde",
    "saude",
    "consultório",
    "consultorio",
    "contabilidade",
    "advocacia",
    "escola",
    "colégio",
    "colegio",
    "prórir",
    "prorir",
)


@dataclass
class Candidate:
    name: str
    url: str
    title: str
    snippet: str
    source_hint: str


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _slug(value: str) -> str:
    value = _norm(value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")


def _digits(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def _host(url: str) -> str:
    try:
        host = urlparse(url or "").netloc.lower()
    except Exception:
        return ""

    if host.startswith("www."):
        host = host[4:]

    return host


def _domain_label(url: str) -> str:
    host = _host(url)

    if not host:
        return ""

    parts = host.split(".")

    if len(parts) >= 3 and parts[-2] in {"com", "org", "net"}:
        return parts[-3]

    if len(parts) >= 2:
        return parts[-2]

    return parts[0]


def _unwrap_url(url: str) -> str:
    url = html.unescape((url or "").strip())

    if not url:
        return ""

    if url.startswith("/url?"):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        target = query.get("q") or query.get("url")

        if target:
            return unquote(target[0])

    if "google.com/url?" in url:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        target = query.get("q") or query.get("url")

        if target:
            return unquote(target[0])

    if url.startswith("//"):
        return "https:" + url

    return url


def _is_usable_url(url: str) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False

    host = _host(url)

    if not host:
        return False

    if any(domain == host or host.endswith("." + domain) for domain in BLOCKED_DOMAINS):
        return False

    return True


def _line_clean(value: str) -> str:
    value = html.unescape(value or "")
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _segment_terms(segment: str) -> list[str]:
    segment_n = _norm(segment)

    for key, aliases in SEGMENT_ALIASES.items():
        if _norm(key) == segment_n:
            return aliases

    return [segment]


def _city_terms(city: str) -> list[str]:
    key = _slug(city)
    terms = REGION_ALIASES.get(key, [city]) + [city]
    output: list[str] = []
    seen: set[str] = set()

    for term in terms:
        term = str(term).strip()

        if not term:
            continue

        term_key = _norm(term)

        if term_key in seen:
            continue

        seen.add(term_key)
        output.append(term)

    return output


def _has_any(text: str, terms: list[str]) -> bool:
    text_n = _norm(text)
    return any(_norm(term) in text_n for term in terms if term)


def _has_local_evidence(text: str, city: str, uf: str) -> bool:
    text_n = _norm(text)

    if _has_any(text, _city_terms(city)):
        return True

    uf_n = _norm(uf)

    return bool(uf_n and re.search(rf"\b{re.escape(uf_n)}\b", text_n)) and "rio de janeiro" in text_n


def _has_segment_evidence(text: str, segment: str) -> bool:
    return _has_any(text, _segment_terms(segment))


def _is_noise_line(value: str) -> bool:
    value_n = _norm(value)

    if not value_n or len(value_n) < 3:
        return True

    if value_n in {_norm(item) for item in UI_NOISE}:
        return True

    if len(value_n) > 220:
        return True

    return False


def _looks_like_business_name(value: str, city: str, segment: str) -> bool:
    value = _line_clean(value)
    value_n = _norm(value)

    if _is_noise_line(value):
        return False

    if re.search(r"\(\d{2}\)\s*\d", value):
        return False

    if len(value) < 4 or len(value) > 120:
        return False

    if any(word in value_n for word in BUSINESS_WORDS):
        return True

    if _has_any(value, _segment_terms(segment)):
        return True

    if _has_any(value, _city_terms(city)):
        return True

    return False


def _clean_title(value: str, url: str = "") -> str:
    value = _line_clean(value)
    value = re.sub(r"^(Facebook|Instagram|LinkedIn)\s*[-·:]+\s*", "", value, flags=re.I)
    value = re.sub(r"\s+-\s+Pesquisa Google$", "", value, flags=re.I)
    value = re.sub(r"\s+\|\s+.*$", "", value)
    value = re.sub(r"\s+·\s+.*$", "", value)

    host = _host(url)

    if host and _norm(value) in {"magé", "mage", "piabetá", "piabeta", "rj"}:
        value = _domain_label(url) or value

    if "odontocompany" in host and "odontocompany" not in _norm(value):
        value = f"OdontoCompany {value}".strip()

    return clean_name(value)


def _extract_address(text: str, city: str, uf: str) -> str:
    compact = _line_clean(text)
    patterns = [
        r"Endere[cç]o:\s*(.{8,180})",
        r"\b(R\.|Rua|Av\.|Avenida|Estrada|Rodovia|Travessa)\s+.{5,160}",
    ]

    for pattern in patterns:
        match = re.search(pattern, compact, flags=re.I)

        if not match:
            continue

        value = match.group(1) if match.lastindex else match.group(0)
        value = re.split(r"\s+(Telefone|Horário|Horario|Como chegar|Rotas|Site)\s*:", value, maxsplit=1, flags=re.I)[0]
        value = _line_clean(value)

        if value:
            return value[:180]

    if _has_any(compact, _city_terms(city)):
        return f"{city} - {uf}"

    return ""


def lead_fingerprint(name: str, city: str, uf: str, url: str = "", phone: str = "", address: str = "") -> str:
    name_s = _slug(name)
    city_s = _slug(city)
    uf_s = _slug(uf)
    host = _host(url)
    phone_d = _digits(phone)
    address_s = _slug(address)

    if phone_d and len(phone_d) >= 8:
        base = f"phone:{phone_d[-10:]}"
    elif host and not any(domain == host or host.endswith("." + domain) for domain in DIRECTORY_DOMAINS):
        base = f"domain:{host}"
    elif address_s:
        base = f"addr:{name_s}|{address_s}|{city_s}|{uf_s}"
    else:
        base = f"name:{name_s}|{city_s}|{uf_s}"

    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    return f"{base}|{digest}"


def _score_candidate(candidate: Candidate, city: str, uf: str, segment: str) -> tuple[int, list[str], list[str]]:
    text = f"{candidate.name} {candidate.title} {candidate.snippet} {candidate.url}"
    host = _host(candidate.url)
    score = 35
    reasons = ["google_importado"]
    tags = ["google_importado"]

    if _has_local_evidence(text, city, uf):
        score += 30
        reasons.append("local_confirmado")
        tags.append("local_confirmado")
    else:
        score -= 20
        reasons.append("local_fraco")
        tags.append("local_fraco")

    if _has_segment_evidence(text, segment):
        score += 20
        reasons.append("segmento_confirmado")
        tags.append("segmento_confirmado")
    else:
        score -= 10
        reasons.append("segmento_fraco")
        tags.append("segmento_fraco")

    found_phones = phones(text)
    found_emails = emails(text)

    if found_phones or found_emails:
        score += 20
        reasons.append("contato_encontrado")
        tags.append("contato_encontrado")
    else:
        tags.append("contato_nao_extraido")

    if candidate.url:
        score += 10
        tags.append("url_encontrada")

    if any(domain == host or host.endswith("." + domain) for domain in DIRECTORY_DOMAINS):
        score -= 5
        reasons.append("diretorio")
        tags.append("lead_indireto")
    elif any(domain == host or host.endswith("." + domain) for domain in SOCIAL_DOMAINS):
        score += 5
        tags.append("rede_social")
    elif host:
        score += 10
        tags.append("lead_direto")

    return score, reasons, tags


def _candidate_to_lead(candidate: Candidate, city: str, uf: str, segment: str) -> Lead | None:
    name = _clean_title(candidate.name or candidate.title, candidate.url)

    if not name:
        return None

    text = f"{name} {candidate.title} {candidate.snippet} {candidate.url}"
    found_phones = phones(text)
    found_emails = emails(text)
    phone = found_phones[0] if found_phones else ""
    email = found_emails[0] if found_emails else ""
    address = _extract_address(text, city, uf)
    score, reasons, tags = _score_candidate(candidate, city, uf, segment)
    fingerprint = lead_fingerprint(name, city, uf, candidate.url, phone, address)

    priority = "alta" if score >= 80 else "media" if score >= 60 else "baixa"
    reason = ", ".join(reasons)

    lead_tags = [
        GOOGLE_IMPORT_SOURCE,
        segment,
        f"local:{city}",
        f"fingerprint:{fingerprint}",
    ] + tags

    evidence = [
        f"fonte: {candidate.source_hint}",
        f"fingerprint: {fingerprint}",
        "qualidade: " + reason,
    ]

    if address:
        evidence.append(f"endereco: {address}")

    if candidate.snippet:
        evidence.append(candidate.snippet[:500])

    return Lead(
        source=GOOGLE_IMPORT_SOURCE,
        name=name,
        city=city,
        uf=uf,
        url=candidate.url,
        title=(candidate.title or name)[:160],
        snippet=(candidate.snippet or "")[:500],
        segment=segment,
        phone=phone,
        whatsapp=phone,
        email=email,
        score=score,
        priority=priority,
        reason=reason,
        approach="Validar dados do Google e abordar como empresa local com possível demanda por plano/benefício.",
        tags=lead_tags,
        evidence=evidence,
        raw={
            "provider": "google_manual",
            "source_hint": candidate.source_hint,
            "quality_score": score,
            "fingerprint": fingerprint,
            "address": address,
        },
    )


def _html_to_text(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")

    for tag in soup(["script", "style", "svg", "noscript"]):
        tag.decompose()

    return html.unescape(soup.get_text("\n", strip=True))


def _extract_html_candidates(raw: str, city: str, uf: str, segment: str) -> list[Candidate]:
    soup = BeautifulSoup(raw, "html.parser")

    for tag in soup(["script", "style", "svg", "noscript"]):
        tag.decompose()

    candidates: list[Candidate] = []

    for anchor in soup.find_all("a"):
        href = _unwrap_url(anchor.get("href") or "")

        if not _is_usable_url(href):
            continue

        title = _line_clean(anchor.get_text(" ", strip=True))

        if not title or _is_noise_line(title):
            continue

        parent_text = ""
        parent = anchor

        for _ in range(5):
            if not parent.parent:
                break

            parent = parent.parent
            parent_text = _line_clean(parent.get_text(" ", strip=True))

            if len(parent_text) >= 80:
                break

        context = parent_text or title

        if not _has_local_evidence(context, city, uf) and not _has_segment_evidence(context, segment):
            continue

        candidates.append(Candidate(title, href, title, context[:700], "html_anchor"))

    return candidates


def _extract_url_candidates(text: str, city: str, segment: str) -> list[Candidate]:
    lines = [_line_clean(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    url_pattern = re.compile(r"https?://[^\s<>\"]+")
    candidates: list[Candidate] = []

    for index, line in enumerate(lines):
        urls = url_pattern.findall(line)

        if not urls:
            continue

        before = lines[max(0, index - 4):index]
        after = lines[index + 1:index + 5]
        context = " ".join(before + [line] + after)

        for raw_url in urls:
            url = _unwrap_url(raw_url).rstrip(").,;")

            if not _is_usable_url(url):
                continue

            title = ""

            for previous in reversed(before):
                if _looks_like_business_name(previous, city, segment):
                    title = previous
                    break

            if not title:
                title = _domain_label(url) or url

            candidates.append(Candidate(title, url, title, context[:700], "texto_url"))

    return candidates


def _extract_line_candidates(text: str, city: str, uf: str, segment: str) -> list[Candidate]:
    lines = [_line_clean(line) for line in text.splitlines()]
    lines = [line for line in lines if line and not _is_noise_line(line)]
    candidates: list[Candidate] = []

    for index, line in enumerate(lines):
        if not _looks_like_business_name(line, city, segment):
            continue

        before = lines[max(0, index - 2):index]
        window = lines[index:index + 7]
        context = " ".join(before + window)

        if not _has_local_evidence(context, city, uf) and not _has_segment_evidence(context, segment):
            continue

        url = ""

        for item in window:
            match = re.search(r"https?://[^\s<>\"]+", item)

            if not match:
                continue

            maybe_url = _unwrap_url(match.group(0).rstrip(").,;"))

            if _is_usable_url(maybe_url):
                url = maybe_url
                break

        candidates.append(Candidate(line, url, line, context[:700], "texto_linha"))

    return candidates


def _read_file(path: str | Path) -> tuple[str, bool]:
    file_path = Path(path)
    raw = file_path.read_text(encoding="utf-8", errors="ignore")
    head = raw[:1200].lower()
    is_html = file_path.suffix.lower() in {".html", ".htm"} or "<html" in head or "<!doctype html" in head
    return raw, is_html


def _dedupe_leads(leads: list[Lead]) -> list[Lead]:
    seen: set[str] = set()
    output: list[Lead] = []

    for lead in leads:
        fingerprint = str(lead.raw.get("fingerprint", "")) if isinstance(lead.raw, dict) else ""

        if not fingerprint:
            fingerprint = lead_fingerprint(lead.name, lead.city, lead.uf, lead.url, lead.phone, "")

        if fingerprint in seen:
            continue

        seen.add(fingerprint)
        output.append(lead)

    return output


def import_google_file(
    path: str | Path,
    city: str,
    uf: str,
    segment: str,
    limit: int = 100,
    debug: bool = False,
) -> list[Lead]:
    raw, is_html = _read_file(path)
    candidates: list[Candidate] = []

    if is_html:
        candidates.extend(_extract_html_candidates(raw, city, uf, segment))
        text = _html_to_text(raw)
    else:
        text = raw

    candidates.extend(_extract_url_candidates(text, city, segment))
    candidates.extend(_extract_line_candidates(text, city, uf, segment))

    min_score = int(__import__("os").getenv("RADAR_GOOGLE_IMPORT_MIN_SCORE", "45"))
    leads: list[Lead] = []

    for candidate in candidates:
        lead = _candidate_to_lead(candidate, city, uf, segment)

        if not lead:
            continue

        if lead.score < min_score:
            if debug:
                print(f"[google-import] rejeitado score={lead.score}: {lead.name}")
            continue

        leads.append(lead)

        if debug:
            print(f"[google-import] lead score={lead.score}: {lead.name} -> {lead.url or 'sem_url'}")

        if len(leads) >= limit:
            break

    return _dedupe_leads(leads)[:limit]
