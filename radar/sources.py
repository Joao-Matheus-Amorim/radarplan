from __future__ import annotations

import os
import re

from radar.config import BENEFICIO_FRACO, CARGOS, CRESCIMENTO, NICHOS, PARCEIROS, SAUDE
from radar.fetcher import Fetcher
from radar.models import Lead
from radar.text_utils import clean_name, emails, has_any, phones


def queries(source: str, city: str, uf: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if source == "vagas":
        for cargo in CARGOS:
            items += [
                (f'site:gupy.io "{cargo}" "{city}" {uf} "benefícios"', cargo),
                (f'"{cargo}" "{city}" {uf} "CLT" "benefícios" "vaga"', cargo),
                (f'"{cargo}" "{city}" {uf} "vale transporte" "vaga"', cargo),
            ]
    elif source == "contadores":
        items = [
            (f'"escritório contábil" "{city}" {uf} "WhatsApp"', "escritório contábil"),
            (f'"contabilidade" "{city}" {uf} "abertura de empresa"', "escritório contábil"),
            (f'"contabilidade" "{city}" {uf} "folha de pagamento"', "escritório contábil"),
            (f'"contador" "{city}" {uf} "departamento pessoal"', "escritório contábil"),
        ]
    elif source == "nichos":
        for nicho in NICHOS:
            items += [
                (f'"{nicho}" "{city}" {uf} "WhatsApp"', nicho),
                (f'"{nicho}" "{city}" {uf} "equipe"', nicho),
                (f'"{nicho}" "{city}" {uf} "trabalhe conosco"', nicho),
            ]
    elif source == "crescimento":
        items = [(f'"{term}" "{city}" empresa {uf}', "sinal de crescimento") for term in CRESCIMENTO]
    elif source == "parceiros":
        for parceiro in PARCEIROS:
            items += [
                (f'"{parceiro}" "{city}" {uf} "empresas"', parceiro),
                (f'"{parceiro}" "{city}" {uf} "WhatsApp"', parceiro),
            ]
    return items


def _is_local_result(city: str, uf: str, text: str, url: str) -> bool:
    strict = os.getenv("RADAR_STRICT_CITY", "1") == "1"
    if not strict:
        return True

    haystack = f"{text} {url}".lower()
    city_l = city.lower()
    uf_l = uf.lower()

    if city_l in haystack:
        return True
    if f"/{city_l.replace(' ', '-')}" in haystack or city_l.replace(' ', '-') in haystack:
        return True
    if uf_l == "rj" and re.search(r"\b(?:21|\+55\s*21)\b", haystack):
        return True
    return False


def collect_source(source: str, city: str, uf: str, limit: int, fetcher: Fetcher) -> list[Lead]:
    leads: list[Lead] = []
    max_queries = int(os.getenv("RADAR_MAX_QUERIES_PER_SOURCE", "8"))
    search_limit = int(os.getenv("RADAR_RESULTS_PER_QUERY", "5"))

    for query, segment in queries(source, city, uf)[:max_queries]:
        if fetcher.debug:
            print(f"[radar] query {source}: {query}")
        for result in fetcher.search(query, limit=search_limit):
            page_text = fetcher.text(result.url)
            full = f"{result.title} {result.snippet} {page_text}"
            if not _is_local_result(city, uf, full, result.url):
                if fetcher.debug:
                    print(f"[radar] descartado fora da cidade: {result.title[:90]}")
                continue
            found_phones = phones(full)
            found_emails = emails(full)
            tags = [source, segment, f"busca:{result.provider or 'desconhecido'}", "local_confirmado"]
            if source == "vagas":
                tags.append("contratando")
                if not has_any(full, SAUDE):
                    tags.append("sem_plano_citado")
                if has_any(full, BENEFICIO_FRACO):
                    tags.append("beneficios_basicos")
            if source == "contadores":
                tags.append("parceria")
                if has_any(full, ["folha de pagamento", "departamento pessoal"]):
                    tags.append("folha_pagamento")
                if has_any(full, ["abertura de empresa", "abrir empresa", "legalização"]):
                    tags.append("abertura_empresa")
            if source == "nichos":
                if has_any(full, ["equipe", "nosso time", "colaboradores"]):
                    tags.append("sinal_equipe")
                if has_any(full, ["trabalhe conosco", "vagas", "carreira"]):
                    tags.append("sinal_contratacao")
            leads.append(Lead(
                source=source,
                name=clean_name(result.title),
                city=city,
                uf=uf,
                url=result.url,
                title=result.title[:160],
                snippet=result.snippet[:500],
                segment=segment,
                phone=found_phones[0] if found_phones else "",
                whatsapp=found_phones[0] if found_phones else "",
                email=found_emails[0] if found_emails else "",
                tags=tags,
                evidence=[result.snippet[:240]],
                raw={"query": query, "provider": result.provider},
            ))
            if len(leads) >= limit:
                return leads
    return leads
