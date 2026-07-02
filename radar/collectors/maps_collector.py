from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from radar.v2_models import ProspectV2


def collect_places(segmento: str, cidade: str, uf: str, limit: int = 20) -> list[ProspectV2]:
    key = os.environ.get("GOOGLE_PLACES_KEY", "")
    if not key:
        return []

    query = f"{segmento} {cidade} {uf}"
    params = urllib.parse.urlencode({"query": query, "key": key})
    url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?{params}"

    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return []

    prospects: list[ProspectV2] = []
    for item in payload.get("results", [])[:limit]:
        prospects.append(ProspectV2(
            nome_empresa=item.get("name") or "Empresa Google Maps",
            cidade=cidade,
            uf=uf,
            segmento=segmento,
            site_url=item.get("website") or "",
            telefone=item.get("formatted_phone_number") or "",
            fontes=["google_maps"],
            consulta_usada=query,
            evidencias=[{"tipo": "maps", "titulo": item.get("name"), "endereco": item.get("formatted_address"), "forca": 30}],
            tags=["google_maps"],
            raw={"google_maps": item},
        ))
    return prospects
