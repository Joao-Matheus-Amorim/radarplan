from __future__ import annotations

from radar.fetcher import Fetcher
from radar.text_utils import emails, phones
from radar.v2_models import ProspectV2


SOCIAL_QUERIES = [
    'site:instagram.com "{segmento}" "{cidade}" "WhatsApp"',
    'site:instagram.com "{segmento}" "{cidade}" "contratando"',
    'site:facebook.com "{segmento}" "{cidade}" "vaga"',
    'site:linkedin.com/company "{segmento}" "{cidade}"',
    'site:linkedin.com/jobs "{segmento}" "{cidade}"',
]


def collect_social_signals(segmento: str, cidade: str, uf: str, limit: int = 20, debug: bool = False) -> list[ProspectV2]:
    fetcher = Fetcher(debug=debug)
    prospects: list[ProspectV2] = []

    for template in SOCIAL_QUERIES:
        query = template.format(segmento=segmento, cidade=cidade)
        results = fetcher.search(query, max(1, limit // len(SOCIAL_QUERIES)))
        for result in results:
            text = f"{result.title} {result.snippet} {result.url}"
            found_phones = phones(text)
            found_emails = emails(text)
            lower = text.lower()
            is_hiring = any(term in lower for term in ("contratando", "vaga", "trabalhe conosco", "hiring"))
            is_growth = any(term in lower for term in ("inauguração", "inauguracao", "nova unidade", "expansão", "expansao", "crescimento"))

            prospects.append(ProspectV2(
                nome_empresa=result.title[:120] or "Prospecto social",
                cidade=cidade,
                uf=uf,
                segmento=segmento,
                telefone=found_phones[0] if found_phones else "",
                whatsapp=found_phones[0] if found_phones else "",
                email=found_emails[0] if found_emails else "",
                instagram=result.url if "instagram.com" in result.url else "",
                linkedin=result.url if "linkedin.com" in result.url else "",
                tem_vaga_ativa=is_hiring,
                vaga_titulo=result.title[:160] if is_hiring else "",
                vaga_publicada_ha_dias=7 if is_hiring else 999,
                tem_post_crescimento=is_growth,
                post_crescimento_texto=result.snippet[:300] if is_growth else "",
                fontes=["instagram_hashtag" if "instagram.com" in result.url else "linkedin_empresa" if "linkedin.com" in result.url else "social_publico"],
                consulta_usada=query,
                evidencias=[{"tipo": "social", "fonte_url": result.url, "titulo": result.title, "texto": result.snippet[:300]}],
                tags=["social_publico"] + (["intent:hiring"] if is_hiring else []) + (["intent:growth"] if is_growth else []),
                raw={"social_result": {"provider": result.provider, "url": result.url, "snippet": result.snippet}},
            ))
    return prospects[:limit]
