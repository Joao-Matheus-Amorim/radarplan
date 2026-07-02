from __future__ import annotations

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from radar.v2_models import ProspectV2


def collect_indeed_rss(segmento: str, cidade: str, uf: str, limit: int = 25) -> list[ProspectV2]:
    query = urllib.parse.urlencode({"q": segmento, "l": cidade, "fromage": "7"})
    url = f"https://br.indeed.com/rss?{query}"

    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            xml_text = response.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    prospects: list[ProspectV2] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    for item in root.findall(".//item")[:limit]:
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        description = item.findtext("description") or ""
        company = title.split(" - ")[-1].strip() if " - " in title else title
        company = re.sub(r"\b(vaga|emprego|contrata[çc][aã]o)\b", "", company, flags=re.I).strip(" -|")

        prospects.append(ProspectV2(
            nome_empresa=company or title[:120] or "Empresa com vaga",
            cidade=cidade,
            uf=uf,
            segmento=segmento,
            tem_vaga_ativa=True,
            vaga_titulo=title[:160],
            vaga_publicada_ha_dias=7,
            fontes=["indeed_vaga"],
            consulta_usada=f"indeed rss {segmento} {cidade}",
            evidencias=[{"tipo": "hiring", "fonte": "indeed", "titulo": title, "fonte_url": link, "forca": 40}],
            tags=["intent:hiring", "vaga_publica"],
            raw={"indeed": {"title": title, "link": link, "description": description[:500]}},
        ))
    return prospects
