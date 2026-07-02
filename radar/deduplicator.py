from __future__ import annotations

import hashlib
import re
import unicodedata

from radar.v2_models import ProspectV2


STOPWORDS = {
    "ltda", "me", "epp", "sa", "s", "a", "eireli", "sas", "sociedade",
    "empresa", "comercio", "comércio", "servicos", "serviços", "industria",
    "indústria", "the", "de", "da", "do", "dos", "das",
}


def normalize_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [word for word in text.split() if word not in STOPWORDS]
    return "".join(words)


def make_fingerprint(nome_empresa: str, cidade: str, telefone: str = "", cnpj: str = "") -> str:
    cnpj_digits = re.sub(r"\D+", "", cnpj or "")
    if cnpj_digits:
        source = f"cnpj:{cnpj_digits}"
    else:
        source = f"{normalize_key(nome_empresa)}|{normalize_key(cidade)}|{re.sub(r'\\D+', '', telefone or '')}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:32]


def merge_prospect(base: ProspectV2, incoming: ProspectV2) -> ProspectV2:
    for field_name in (
        "cnpj", "segmento", "cnae_codigo", "cnae_descricao", "telefone", "whatsapp",
        "email", "site_url", "instagram", "linkedin", "data_abertura", "porte_receita",
    ):
        if not getattr(base, field_name) and getattr(incoming, field_name):
            setattr(base, field_name, getattr(incoming, field_name))

    base.funcionarios_estimados = max(base.funcionarios_estimados or 0, incoming.funcionarios_estimados or 0)
    base.capital_social = max(base.capital_social or 0, incoming.capital_social or 0)
    base.fontes = list(dict.fromkeys([*base.fontes, *incoming.fontes]))
    base.evidencias = [*base.evidencias, *incoming.evidencias]
    base.tags = list(dict.fromkeys([*base.tags, *incoming.tags]))
    base.raw.setdefault("variacoes_nome", [])
    if incoming.nome_empresa and incoming.nome_empresa != base.nome_empresa:
        base.raw["variacoes_nome"].append(incoming.nome_empresa)
    return base


def dedupe_prospects(prospects: list[ProspectV2]) -> list[ProspectV2]:
    by_key: dict[str, ProspectV2] = {}
    order: list[str] = []

    for prospect in prospects:
        prospect.fingerprint = prospect.fingerprint or make_fingerprint(
            prospect.nome_empresa, prospect.cidade, prospect.telefone or prospect.whatsapp, prospect.cnpj
        )
        key = prospect.fingerprint

        if key not in by_key:
            by_key[key] = prospect
            order.append(key)
            continue

        by_key[key] = merge_prospect(by_key[key], prospect)

    return [by_key[key] for key in order]
