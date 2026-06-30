from __future__ import annotations

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
                (f'"{cargo}" "{city}" "CLT" "benefícios" "vaga"', cargo),
                (f'"{cargo}" "{city}" "vale transporte" "vaga"', cargo),
            ]
    elif source == "contadores":
        items = [
            (f'"escritório contábil" "{city}" "WhatsApp"', "escritório contábil"),
            (f'"contabilidade" "{city}" "abertura de empresa"', "escritório contábil"),
            (f'"contabilidade" "{city}" "folha de pagamento"', "escritório contábil"),
            (f'"contador" "{city}" "departamento pessoal"', "escritório contábil"),
        ]
    elif source == "nichos":
        for nicho in NICHOS:
            items += [
                (f'"{nicho}" "{city}" "WhatsApp"', nicho),
                (f'"{nicho}" "{city}" "equipe"', nicho),
                (f'"{nicho}" "{city}" "trabalhe conosco"', nicho),
            ]
    elif source == "crescimento":
        items = [(f'"{term}" "{city}" empresa {uf}', "sinal de crescimento") for term in CRESCIMENTO]
    elif source == "parceiros":
        for parceiro in PARCEIROS:
            items += [
                (f'"{parceiro}" "{city}" "empresas"', parceiro),
                (f'"{parceiro}" "{city}" "WhatsApp"', parceiro),
            ]
    return items


def collect_source(source: str, city: str, uf: str, limit: int, fetcher: Fetcher) -> list[Lead]:
    leads: list[Lead] = []
    for query, segment in queries(source, city, uf):
        for result in fetcher.search(query, limit=5):
            full = f"{result.title} {result.snippet} {fetcher.text(result.url)}"
            found_phones = phones(full)
            found_emails = emails(full)
            tags = [source, segment]
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
                raw={"query": query},
            ))
            if len(leads) >= limit:
                return leads
    return leads
