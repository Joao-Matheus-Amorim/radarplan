from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from radar.exporter import export_csv
from radar.fetcher import Fetcher, SearchResult
from radar.google_importer import lead_fingerprint
from radar.models import Lead
from radar.text_utils import clean_name, emails, phones


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
    "instagram.com",
    "facebook.com",
    "linkedin.com",
)

DOMAIN_NAME_HINTS = {
    "odontocompany": "OdontoCompany",
    "sorriabem": "Sorria Bem",
    "espacosaudeodonto": "Espaço Saúde Odonto",
    "odontologiapiabeta": "Odontologia Piabetá",
    "prorir": "Clínica Prórir",
    "dentpopodonto": "Dent Pop Odonto",
}


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

    return host


def _pretty_domain_name(url: str) -> str:
    label = _domain_label(url)

    if not label:
        return ""

    return DOMAIN_NAME_HINTS.get(label, label.replace("-", " ").replace("_", " ").title())


def _is_directory(url: str) -> bool:
    host = _host(url)
    return any(host == domain or host.endswith("." + domain) for domain in DIRECTORY_DOMAINS)


def _is_social(url: str) -> bool:
    host = _host(url)
    return any(host == domain or host.endswith("." + domain) for domain in SOCIAL_DOMAINS)



def _dedupe_words_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name or "").strip()

    replacements = {
        "Sorria Bem Sorria Bem": "Sorria Bem",
        "OdontoCompany OdontoCompany": "OdontoCompany",
        "Espa?o Sa?de Espa?o Sa?de": "Espa?o Sa?de",
        "Cl?nica Pr?rir Cl?nica Pr?rir": "Cl?nica Pr?rir",
        "Odontologia Piabet? Odontologia Piabet?": "Odontologia Piabet?",
    }

    for bad, good in replacements.items():
        name = name.replace(bad, good)

    return name.strip()


def _clean_result_name(title: str, url: str, cidade: str) -> str:
    title = clean_name(title or "")
    title = re.sub(r"\s+-\s*$", "", title).strip()
    title = re.sub(r"\s+\|\s+.*$", "", title).strip()

    low = title.lower()
    host_name = _pretty_domain_name(url)

    generic_titles = {
        cidade.lower(),
        "piabetá",
        "piabeta",
        "magé",
        "mage",
        "magé - piabetá",
        "mage - piabeta",
    }

    if low in generic_titles and host_name:
        title = f"{host_name} {title}".strip()

    if "odontocompany" in _host(url) and "odontocompany" not in low:
        title = f"OdontoCompany {title}".strip()

    if "sorriabem.com.br" in _host(url) and "sorria" not in low:
        title = f"Sorria Bem {title}".strip()

    if "espacosaudeodonto.com.br" in _host(url) and "espaço saúde" not in low and "espaco saude" not in low:
        title = f"Espaço Saúde {title}".strip()

    if not title and host_name:
        title = host_name

    return _dedupe_words_name(title)[:120]


def _score_result(result: SearchResult, segmento: str) -> tuple[int, str, list[str]]:
    text = f"{result.title} {result.snippet} {result.url}".lower()
    score = 60
    reasons = ["google_browser"]
    tags = ["google_browser"]

    if result.url:
        score += 10
        tags.append("url_encontrada")

    found_phones = phones(text)
    found_emails = emails(text)

    if found_phones or found_emails:
        score += 15
        reasons.append("contato_encontrado")
        tags.append("contato_encontrado")

    if _is_directory(result.url):
        score -= 10
        reasons.append("diretorio")
        tags.append("lead_indireto")
    elif _is_social(result.url):
        score += 5
        reasons.append("rede_social")
        tags.append("rede_social")
    else:
        score += 15
        reasons.append("site_direto")
        tags.append("lead_direto")

    segment_terms = [
        segmento.lower(),
        "odonto",
        "odontologia",
        "dentista",
        "clínica",
        "clinica",
        "laboratório",
        "laboratorio",
        "contabilidade",
        "advocacia",
    ]

    if any(term and term in text for term in segment_terms):
        score += 10
        reasons.append("segmento_confirmado")
        tags.append("segmento_confirmado")

    return min(score, 135), ", ".join(reasons), tags


def _result_to_lead(result: SearchResult, cidade: str, uf: str, segmento: str) -> Lead:
    text = f"{result.title} {result.snippet} {result.url}"
    found_phones = phones(text)
    found_emails = emails(text)
    phone = found_phones[0] if found_phones else ""
    email = found_emails[0] if found_emails else ""
    name = _clean_result_name(result.title, result.url, cidade)
    score, reason, tags = _score_result(result, segmento)
    priority = "alta" if score >= 85 else "media" if score >= 65 else "baixa"
    fingerprint = lead_fingerprint(name, cidade, uf, result.url, phone, "")

    return Lead(
        source="google_browser",
        name=name,
        city=cidade,
        uf=uf,
        url=result.url,
        title=result.title[:160],
        snippet=result.snippet[:500],
        segment=segmento,
        phone=phone,
        whatsapp=phone,
        email=email,
        score=score,
        priority=priority,
        reason=reason,
        approach="Validar o lead do Google e abordar como empresa local com possível demanda por plano/benefício.",
        tags=[
            "google_browser",
            segmento,
            f"local:{cidade}",
            f"fingerprint:{fingerprint}",
        ] + tags,
        evidence=[
            f"provider: {result.provider}",
            f"fingerprint: {fingerprint}",
            result.snippet[:500],
        ],
        raw={
            "provider": result.provider,
            "fingerprint": fingerprint,
            "query_source": "google_leads",
        },
    )


def _dedupe(leads: list[Lead]) -> list[Lead]:
    best: dict[str, Lead] = {}
    order: list[str] = []

    for lead in leads:
        fingerprint = ""

        if isinstance(lead.raw, dict):
            fingerprint = str(lead.raw.get("fingerprint", ""))

        key = fingerprint or lead.url or f"{lead.name}|{lead.city}|{lead.uf}"

        if key not in best:
            best[key] = lead
            order.append(key)
            continue

        current = best[key]

        if (lead.score, bool(lead.phone), bool(lead.url)) > (current.score, bool(current.phone), bool(current.url)):
            best[key] = lead

    return [best[key] for key in order]


def _cache_path(query: str, limit: int) -> Path:
    cache_dir = Path("data/google_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(f"{query}|{limit}".encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{digest}.json"


def _load_cache(query: str, limit: int) -> list[SearchResult] | None:
    path = _cache_path(query, limit)

    if not path.exists():
        return None

    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    return [
        SearchResult(
            title=str(row.get("title", "")),
            url=str(row.get("url", "")),
            snippet=str(row.get("snippet", "")),
            provider=str(row.get("provider", "google_browser")),
        )
        for row in rows
    ]


def _save_cache(query: str, limit: int, results: list[SearchResult]) -> None:
    path = _cache_path(query, limit)
    rows = [
        {
            "title": result.title,
            "url": result.url,
            "snippet": result.snippet,
            "provider": result.provider,
        }
        for result in results
    ]
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def build_queries(cidade: str, uf: str, segmento: str, query: str, extra: bool) -> list[str]:
    if query:
        return [query]

    base = f"{segmento} {cidade} {uf}"

    if not extra:
        return [base]

    segmento_n = segmento.lower()
    queries = [base]

    if "odonto" in segmento_n or "dent" in segmento_n:
        queries += [
            f"dentista {cidade} {uf}",
            f"odontologia {cidade} {uf}",
        ]
    elif "clínica" in segmento_n or "clinica" in segmento_n:
        queries += [
            f"clínica médica {cidade} {uf}",
            f"consultório médico {cidade} {uf}",
        ]
    elif "laboratório" in segmento_n or "laboratorio" in segmento_n:
        queries += [
            f"laboratório exames {cidade} {uf}",
        ]

    return list(dict.fromkeys(queries))


def run(args: argparse.Namespace) -> int:
    os.environ["RADAR_PROVIDERS"] = "google_browser"
    os.environ.setdefault("RADAR_CAPTCHA_MANUAL", "1")
    os.environ.setdefault("RADAR_GOOGLE_BROWSER_PROFILE", "data/google_browser_profile")
    os.environ.setdefault("RADAR_SLEEP", "2")

    fetcher = Fetcher(debug=args.debug)
    queries = build_queries(args.cidade, args.uf, args.segmento, args.query, args.extra)
    all_results: list[SearchResult] = []

    for index, query in enumerate(queries, start=1):
        cached = None if args.no_cache else _load_cache(query, args.limite)

        if cached is not None:
            results = cached
            print(f"[google-leads] cache: {query} ({len(results)} resultados)")
        else:
            print(f"[google-leads] buscando: {query}")
            results = fetcher.search(query, args.limite)
            print(f"[google-leads] status: {fetcher.last_status}")

            if results:
                _save_cache(query, args.limite, results)

        all_results.extend(results)

        if index < len(queries):
            print(f"[google-leads] pausa {args.pausa}s")
            time.sleep(args.pausa)

    leads = _dedupe([
        _result_to_lead(result, args.cidade, args.uf, args.segmento)
        for result in all_results
    ])

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    export_csv(leads, saida)

    fila_leads = [lead for lead in leads if not _is_directory(lead.url)]
    fila = Path(args.fila)
    fila.parent.mkdir(parents=True, exist_ok=True)
    export_csv(fila_leads[: args.fila_limite], fila)

    print(f"Resultados Google: {len(all_results)}")
    print(f"Leads únicos: {len(leads)}")
    print(f"CSV: {saida}")
    print(f"Fila: {fila}")

    fila_leads = [lead for lead in leads if not _is_directory(lead.url)]

    for i, lead in enumerate(fila_leads[: args.fila_limite], start=1):
        print("")
        print(f"[{i}] {lead.name} | score={lead.score} | prioridade={lead.priority}")
        print(f"Segmento: {lead.segment}")
        print(f"Cidade: {lead.city}/{lead.uf}")

        if lead.phone:
            print(f"Telefone: {lead.phone}")

        print(f"URL: {lead.url}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Prospecta leads via Google Browser em modo lento/cacheado.")
    parser.add_argument("--cidade", required=True)
    parser.add_argument("--uf", default="RJ")
    parser.add_argument("--segmento", required=True)
    parser.add_argument("--query", default="", help="Query manual. Se vazia, usa segmento+cidade+uf.")
    parser.add_argument("--limite", type=int, default=10)
    parser.add_argument("--saida", default="exports/google_leads.csv")
    parser.add_argument("--fila", default="exports/fila_do_dia.csv")
    parser.add_argument("--fila-limite", type=int, default=10)
    parser.add_argument("--pausa", type=int, default=120)
    parser.add_argument("--extra", action="store_true", help="Faz queries extras. Use com cuidado para não chamar captcha.")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
