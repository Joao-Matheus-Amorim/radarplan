from __future__ import annotations

import re

from radar.deduplicator import make_fingerprint
from radar.v2_models import ProspectV2


def only_digits(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def normalize_phone(value: str) -> str:
    digits = only_digits(value)
    if digits.startswith("55") and len(digits) > 11:
        digits = digits[2:]
    return digits


def normalize_prospect(prospect: ProspectV2) -> ProspectV2:
    prospect.uf = (prospect.uf or "RJ").upper()[:2]
    prospect.telefone = normalize_phone(prospect.telefone)
    prospect.whatsapp = normalize_phone(prospect.whatsapp or prospect.telefone)
    prospect.cnpj = only_digits(prospect.cnpj)
    prospect.fontes = list(dict.fromkeys([item for item in prospect.fontes if item]))
    prospect.tags = list(dict.fromkeys([item for item in prospect.tags if item]))
    prospect.fingerprint = prospect.fingerprint or make_fingerprint(
        prospect.nome_empresa, prospect.cidade, prospect.telefone or prospect.whatsapp, prospect.cnpj
    )
    prospect.raw.setdefault("normalizado", True)
    return prospect


def to_admin_payload(prospect: ProspectV2) -> dict:
    data = prospect.to_dict()
    data.update({
        "score": prospect.score_total,
        "score_total": prospect.score_total,
        "score_d1_fonte": prospect.score_d1_fonte,
        "score_d2_intencao": prospect.score_d2_intencao,
        "score_d3_porte": prospect.score_d3_porte,
        "score_d4_contato": prospect.score_d4_contato,
        "score_d5_timing": prospect.score_d5_timing,
        "score_d6_concorrencia": prospect.score_d6_concorrencia,
        "telefone_publico": prospect.telefone,
        "email_publico": prospect.email,
        "fonte_url": prospect.site_url or prospect.instagram or prospect.linkedin,
        "consulta_google": prospect.consulta_usada,
        "score_motivos": " | ".join(prospect.score_motivos),
        "evidencias": prospect.evidencias,
        "tags": prospect.tags,
        "raw": prospect.to_dict(),
    })
    return data
