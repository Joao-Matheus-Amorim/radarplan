from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen

from radar.models import Lead


def enhance_ai(lead: Lead) -> Lead:
    endpoint = os.getenv("RADAR_IA_ENDPOINT", "http://localhost:11434/api/generate")
    prompt = f"Resuma a oportunidade comercial B2B em 1 frase e gere abordagem curta. Não invente dados. Retorne JSON com resumo e abordagem. Lead: {lead.row()}"
    try:
        payload = json.dumps({"model": os.getenv("RADAR_IA_MODEL", "llama3.1:8b"), "prompt": prompt, "stream": False}).encode()
        request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
        response = json.loads(urlopen(request, timeout=25).read().decode()).get("response", "")
        start, end = response.find("{"), response.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(response[start:end + 1])
            lead.reason = data.get("resumo", lead.reason)[:500]
            lead.approach = data.get("abordagem", lead.approach)[:1200]
            lead.tags.append("ia_local")
    except Exception:
        lead.tags.append("ia_indisponivel")
    return lead
