from __future__ import annotations

import os
import re
import unicodedata

from radar.config import BENEFICIO_FRACO, CARGOS, CRESCIMENTO, NICHOS, PARCEIROS, SAUDE
from radar.fetcher import Fetcher
from radar.models import Lead
from radar.text_utils import clean_name, emails, has_any, phones


MAGE_PIABETA_REGION = [
    "Piabetá",
    "Magé",
    "Fragoso",
    "Vila Inhomirim",
    "Raiz da Serra",
    "Pau Grande",
    "Santo Aleixo",
    "Parada Angélica",
    "Jardim Nazareno",
    "Parque Caçula",
    "Bongaba",
    "Guia de Pacobaíba",
    "Mauá",
    "Suruí",
]


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.lower().strip()


def region_terms(city: str) -> list[str]:
    city_n = _norm(city)
    if city_n in {"mage", "piabeta", "vila inhomirim", "fragoso", "raiz da serra", "pau grande"}:
        terms = [city]
        for place in MAGE_PIABETA_REGION:
            if _norm(place) != city_n:
                terms.append(place)
        return terms
    return [city]


def queries(source: str, city: str, uf: str) -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = []
    places = region_terms(city)
    if source == "vagas":
        for place in places:
            for cargo in CARGOS:
                items += [
                    (f'site:gupy.io "{cargo}" "{place}" {uf} "benefícios"', cargo, place),
                    (f'"{cargo}" "{place}" {uf} "CLT" "benefícios" "vaga"', cargo, place),
                    (f'"{cargo}" "{place}" {uf} "vale transporte" "vaga"', cargo, place),
                ]
    elif source == "contadores":
        for place in places:
            items += [
                (f'"escritório contábil" "{place}" {uf} "WhatsApp"', "escritório contábil", place),
                (f'"contabilidade" "{place}" {uf} "abertura de empresa"', "escritório contábil", place),
                (f'"contabilidade" "{place}" {uf} "folha de pagamento"', "escritório contábil", place),
                (f'"contador" "{place}" {uf} "departamento pessoal"', "escritório contábil", place),
            ]
    elif source == "nichos":
        for place in places:
            for nicho in NICHOS:
                items += [
                    (f'"{nicho}" "{place}" {uf} "WhatsApp"', nicho, place),
                    (f'"{nicho}" "{place}" {uf} "equipe"', nicho, place),
                    (f'"{nicho}" "{place}" {uf} "trabalhe conosco"', nicho, place),
                ]
    elif source == "crescimento":
        for place in places:
            items += [(f'"{term}" "{place}" empresa {uf}', "sinal de crescimento", place) for term in CRESCIMENTO]
    elif source == "parceiros":
        for place in places:
            for parceiro in PARCEIROS:
                items += [
                    (f'"{parceiro}" "{place}" {uf} "empresas"', parceiro, place),
                    (f'"{parceiro}" "{place}" {uf} "WhatsApp"', parceiro, place),
                ]
    return items


def _is_local_result(city: str, uf: str, text: str, url: str) -> bool:
    strict = os.getenv("RADAR_STRICT_CITY", "1") == "1"
    if not strict:
        return True

    haystack = _norm(f"{text} {url}")
    places = [_norm(place) for place in region_terms(city)]
    uf_l = _norm(uf)

    for place in places:
        if place and place in haystack:
            return True
        if place and place.replace(" ", "-") in haystack:
            return True
    if uf_l == "rj" and re.search(r"\b(?:21|\+55\s*21)\b", haystack):
        return True
    return False


def _matched_place(city: str, text: str, url: str) -> str:
    haystack = _norm(f"{text} {url}")
    for place in region_terms(city):
        place_n = _norm(place)
        if place_n in haystack or place_n.replace(" ", "-") in haystack:
            return place
    return city


def collect_source(source: str, city: str, uf: str, limit: int, fetcher: Fetcher) -> list[Lead]:
    leads: list[Lead] = []
    max_queries = int(os.getenv("RADAR_MAX_QUERIES_PER_SOURCE", "16"))
    search_limit = int(os.getenv("RADAR_RESULTS_PER_QUERY", "5"))

    for query, segment, place_query in queries(source, city, uf)[:max_queries]:
        if fetcher.debug:
            print(f"[radar] query {source}: {query}")
        for result in fetcher.search(query, limit=search_limit):
            page_text = fetcher.text(result.url)
            full = f"{result.title} {result.snippet} {page_text}"
            if not _is_local_result(city, uf, full, result.url):
                if fetcher.debug:
                    print(f"[radar] descartado fora da região: {result.title[:90]}")
                continue
            found_phones = phones(full)
            found_emails = emails(full)
            place_found = _matched_place(city, full, result.url)
            tags = [source, segment, f"local:{place_found}", f"busca:{result.provider or 'desconhecido'}", "local_confirmado"]
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
                city=place_found,
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
                raw={"query": query, "provider": result.provider, "place_query": place_query},
            ))
            if len(leads) >= limit:
                return leads
    return leads
