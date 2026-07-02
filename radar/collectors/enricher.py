from __future__ import annotations

import json
import re
import time
import urllib.request

from radar.v2_models import ProspectV2


def enrich_with_brasilapi(prospect: ProspectV2, sleep_seconds: float = 1.0) -> ProspectV2:
    cnpj = re.sub(r"\D+", "", prospect.cnpj or "")
    if len(cnpj) != 14:
        return prospect

    time.sleep(sleep_seconds)
    try:
        with urllib.request.urlopen(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}", timeout=20) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return prospect

    prospect.nome_empresa = prospect.nome_empresa or data.get("nome_fantasia") or data.get("razao_social") or prospect.nome_empresa
    prospect.cnae_codigo = prospect.cnae_codigo or str(data.get("cnae_fiscal") or "")
    prospect.cnae_descricao = prospect.cnae_descricao or data.get("cnae_fiscal_descricao") or ""
    prospect.porte_receita = prospect.porte_receita or data.get("porte") or ""
    prospect.capital_social = prospect.capital_social or float(data.get("capital_social") or 0)
    prospect.data_abertura = prospect.data_abertura or data.get("data_inicio_atividade") or ""
    prospect.email = prospect.email or data.get("email") or ""
    prospect.telefone = prospect.telefone or data.get("ddd_telefone_1") or ""
    prospect.fontes = list(dict.fromkeys([*prospect.fontes, "brasilapi_cnpj"]))
    prospect.raw["brasilapi"] = data
    return prospect
