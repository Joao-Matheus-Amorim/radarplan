from __future__ import annotations

from urllib.parse import urlparse

from radar.models import Lead
from radar.text_utils import norm


def reason(lead: Lead) -> str:
    if lead.source == "contadores":
        return "Escritório contábil pode indicar clientes PME; bom canal de parceria."
    if lead.source == "vagas":
        if "sem_plano_citado" in lead.tags:
            return "Empresa aparece contratando; sem plano de saúde citado no contexto coletado."
        return "Empresa aparece contratando, indicando movimento de equipe."
    if lead.source == "crescimento":
        return "Há sinal público de crescimento, expansão, inauguração ou contratação."
    if lead.source == "parceiros":
        return "Possível parceiro indireto com acesso a empresas em contratação, folha ou crescimento."
    return f"Empresa de nicho local prioritário ({lead.segment}) com presença pública coletada."


def approach(lead: Lead) -> str:
    if lead.source == "contadores":
        return f"Olá, tudo bem? Vi que a {lead.name} atua com contabilidade em {lead.city}. Trabalho com planos de saúde PME e estou fechando parcerias com escritórios contábeis da região. Quando algum cliente precisar de plano para sócios ou funcionários, você me indica, eu faço a cotação e atendimento, e se fechar você recebe pela indicação. Sem custo e sem trabalho operacional para o escritório."
    if lead.source == "vagas":
        return f"Olá, tudo bem? Vi que vocês estão contratando em {lead.city}. Como candidatos costumam comparar benefícios antes de aceitar proposta, notei que o contexto coletado não destaca plano de saúde. Consigo simular opções PME para deixar a proposta mais competitiva. Posso te mandar uma comparação rápida?"
    if lead.source == "crescimento":
        return f"Olá, tudo bem? Vi um sinal de crescimento ou expansão da {lead.name} em {lead.city}. Nessa fase, muitas empresas revisam benefícios para contratar e reter melhor. Consigo simular planos PME para equipes pequenas e médias. Quer que eu envie uma comparação?"
    if lead.source == "parceiros":
        return f"Olá, tudo bem? Vi que a {lead.name} atua com {lead.segment} em {lead.city}. Estou buscando parceiros que atendem empresas em fase de contratação ou crescimento. Quando algum cliente precisar de plano PME, eu cuido da cotação e atendimento, e você participa pela indicação. Podemos conversar?"
    return f"Olá, tudo bem? Vi a {lead.name} em {lead.city} e estou levantando empresas do segmento {lead.segment} para simulação de plano de saúde PME. Consigo comparar opções para equipes pequenas e médias sem compromisso. Quer que eu te mande uma simulação?"


def score(lead: Lead) -> Lead:
    tags = set(lead.tags)
    points = 0
    if lead.source == "contadores":
        points += 45 + (25 if lead.phone else 0) + (18 if "folha_pagamento" in tags else 0) + (14 if "abertura_empresa" in tags else 0)
    elif lead.source == "vagas":
        points += 35 + (30 if "sem_plano_citado" in tags else 0) + (10 if "beneficios_basicos" in tags else 0) + (15 if lead.phone else 0)
    elif lead.source == "nichos":
        points += 30 + (25 if lead.phone else 0) + (14 if "sinal_equipe" in tags else 0) + (18 if "sinal_contratacao" in tags else 0)
    elif lead.source == "crescimento":
        points += 53 + (20 if lead.phone else 0)
    elif lead.source == "parceiros":
        points += 35 + (25 if lead.phone else 0)
    points += 5 if lead.url else 0
    points += 5 if lead.city else 0
    if not lead.phone and not lead.email:
        points -= 15
    if any(bad in norm(lead.name) for bad in ["concurso", "prefeitura", "wikipedia"]):
        points -= 40
    lead.score = max(0, min(100, points))
    lead.priority = "ligar hoje" if lead.score >= 85 else "validar manualmente" if lead.score >= 70 else "enriquecer" if lead.score >= 50 else "baixo"
    lead.reason = reason(lead)
    lead.approach = approach(lead)
    return lead


def dedupe(leads: list[Lead]) -> list[Lead]:
    seen: set[str] = set()
    out: list[Lead] = []
    for lead in leads:
        domain = urlparse(lead.url).netloc.replace("www.", "")
        key = norm(f"{lead.name}|{lead.city}|{lead.phone or domain}")
        if key not in seen:
            seen.add(key)
            out.append(lead)
    return out
