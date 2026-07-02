from __future__ import annotations

from datetime import date, datetime

from radar.v2_models import ProspectV2


CNAE_BONUS = [
    (("69",), 9, "CNAE estratégico: jurídico/contábil"),
    (("86",), 8, "CNAE estratégico: saúde humana"),
    (("85",), 8, "CNAE estratégico: educação"),
    (("70",), 8, "CNAE estratégico: consultoria/sedes"),
    (("62", "63"), 7, "CNAE estratégico: TI/serviços digitais"),
    (("71",), 7, "CNAE estratégico: engenharia/arquitetura"),
    (("72",), 7, "CNAE estratégico: P&D científico"),
    (("73",), 6, "CNAE estratégico: publicidade/pesquisa"),
    (("74",), 6, "CNAE estratégico: serviços profissionais"),
    (("47",), 6, "CNAE estratégico: comércio varejista"),
    (("87", "88"), 6, "CNAE estratégico: atividades residenciais"),
    (("80",), 5, "CNAE estratégico: segurança/vigilância"),
    (("81",), 5, "CNAE estratégico: serviços para edifícios"),
    (("46",), 5, "CNAE estratégico: atacado"),
    (("41", "42", "43"), 5, "CNAE estratégico: construção civil"),
    (("49",), 4, "CNAE estratégico: transporte terrestre"),
    (("52",), 4, "CNAE estratégico: logística"),
    (tuple(f"{n:02d}" for n in range(10, 29)), 4, "CNAE estratégico: indústria"),
    (("55",), 3, "CNAE estratégico: alojamento"),
    (("56",), 3, "CNAE estratégico: alimentação"),
    (("50",), 3, "CNAE estratégico: transporte aquaviário"),
]


def clamp(value: int, maximum: int) -> int:
    return max(0, min(maximum, int(value)))


def parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def months_since(value: str) -> int | None:
    opened = parse_date(value)
    if not opened:
        return None
    today = date.today()
    return max(0, (today.year - opened.year) * 12 + today.month - opened.month)


def d1_fonte(prospect: ProspectV2, motivos: list[str]) -> int:
    score = 0
    fontes = set(prospect.fontes or [])

    if prospect.cnpj and not prospect.cnpj_invalido and not prospect.empresa_inativa:
        score = max(score, 40)
        motivos.append("CNPJ confirmado na Receita Federal")
    if "indeed_vaga" in fontes or "catho_vaga" in fontes or "infojobs_vaga" in fontes:
        score = max(score, 35)
        motivos.append("Vaga encontrada em job board público")
    if "google_maps" in fontes:
        score = max(score, 30)
        motivos.append("Empresa confirmada no Google Maps")
    if prospect.linkedin:
        score = max(score, 25)
        motivos.append("Perfil LinkedIn encontrado")
    if "instagram_hashtag" in fontes or prospect.instagram:
        score = max(score, 20)
        motivos.append("Menção pública em Instagram")
    if not score and fontes:
        score = 10
        motivos.append("Fonte indireta ou lista genérica")

    if len(fontes) >= 3:
        score += 10
        motivos.append("Confirmada em 3+ fontes distintas")
    elif len(fontes) >= 2:
        score += 5
        motivos.append("Confirmada em 2 fontes distintas")

    if prospect.nome_invalido:
        score -= 15
    if prospect.empresa_inativa:
        score -= 30
    if prospect.fonte_indireta:
        score -= 20

    return clamp(score, 40)


def d2_intencao(prospect: ProspectV2, motivos: list[str]) -> int:
    score = 0

    if prospect.tem_vaga_ativa:
        dias = prospect.vaga_publicada_ha_dias
        if dias <= 3:
            score += 50
            motivos.append(f"Vaga publicada há {dias} dias — janela crítica")
        elif dias <= 14:
            score += 40
            motivos.append(f"Vaga publicada há {dias} dias")
        elif dias <= 30:
            score += 30
            motivos.append(f"Vaga publicada há {dias} dias")
        else:
            score += 15
            motivos.append("Vaga antiga encontrada")

    if prospect.tem_post_crescimento:
        score += 20
        motivos.append("Post público de crescimento ou nova sede")
    if prospect.tem_novo_cnpj_filial:
        score += 15
        motivos.append("Abertura de filial detectada")

    cnae = (prospect.cnae_codigo or "").replace(".", "").replace("-", "")[:2]
    for prefixes, bonus, label in CNAE_BONUS:
        if cnae in prefixes:
            score += bonus
            motivos.append(label)
            break

    return clamp(score, 50)


def d3_porte(prospect: ProspectV2, motivos: list[str]) -> int:
    funcionarios = int(prospect.funcionarios_estimados or 0)
    porte = (prospect.porte_receita or "").upper()

    if funcionarios >= 50:
        motivos.append("Porte estimado: 50+ funcionários")
        return 30
    if funcionarios >= 20:
        motivos.append("Porte estimado: 20–49 funcionários")
        return 25
    if funcionarios >= 10:
        motivos.append("Porte estimado: 10–19 funcionários")
        return 20
    if funcionarios >= 5:
        motivos.append("Porte estimado: 5–9 funcionários")
        return 15
    if funcionarios >= 2:
        motivos.append("Porte estimado: 2–4 funcionários")
        return 10

    if "MEDIO" in porte or "MÉDIO" in porte:
        motivos.append("Porte MEDIO declarado na Receita")
        return 22
    if "EPP" in porte:
        motivos.append("EPP declarado na Receita")
        return 15
    if porte == "ME":
        motivos.append("ME declarado na Receita")
        return 8

    motivos.append("Porte desconhecido")
    return 5


def d4_contato(prospect: ProspectV2, motivos: list[str]) -> int:
    score = 0
    if prospect.whatsapp:
        score += 30
        motivos.append("WhatsApp público encontrado")
    elif prospect.telefone:
        score += 25
        motivos.append("Telefone direto encontrado")
    if prospect.email:
        score += 15
        motivos.append("Email direto encontrado")
    if prospect.instagram:
        score += 10
        motivos.append("Instagram público encontrado")
    if prospect.linkedin:
        score += 8
        motivos.append("LinkedIn público encontrado")
    if prospect.site_url and not (prospect.whatsapp or prospect.telefone or prospect.email):
        score += 5
        motivos.append("Site com possível formulário de contato")
    if prospect.telefone_invalido:
        score = 0
    return clamp(score, 40)


def d5_timing(prospect: ProspectV2, motivos: list[str]) -> int:
    months = months_since(prospect.data_abertura)
    if months is None:
        score = 5
        motivos.append("Data de abertura desconhecida")
    elif months <= 6:
        score = 30
        motivos.append("Empresa com 0 a 6 meses — janela crítica")
    elif months <= 12:
        score = 25
        motivos.append("Empresa com 7 a 12 meses")
    elif months <= 18:
        score = 18
        motivos.append("Empresa com 13 a 18 meses")
    elif months <= 36:
        score = 10
        motivos.append("Empresa com 19 a 36 meses")
    else:
        score = 3
        motivos.append("Empresa com mais de 36 meses")

    if prospect.tem_vaga_ativa and prospect.vaga_publicada_ha_dias <= 7:
        score += 5
        motivos.append("Vaga publicada nos últimos 7 dias")

    return clamp(score, 30)


def d6_concorrencia(prospect: ProspectV2, motivos: list[str]) -> int:
    populacao = int(prospect.cidade_populacao or 0)
    if not populacao:
        motivos.append("População desconhecida")
        return 5
    if populacao < 20_000:
        motivos.append("Cidade com menos de 20 mil habitantes")
        return 10
    if populacao <= 100_000:
        motivos.append("Cidade de 20 mil a 100 mil habitantes")
        return 7
    if populacao <= 500_000:
        motivos.append("Cidade de 100 mil a 500 mil habitantes")
        return 4
    motivos.append("Metrópole acima de 500 mil habitantes")
    return 1


def classify(score: int, has_moment_signal: bool) -> tuple[int, str, str]:
    if score >= 140 and has_moment_signal:
        return 5, "QUENTE AGORA", "critica"
    if score >= 110:
        return 4, "PREPARAR", "alta"
    if score >= 80:
        return 3, "MONITORAR", "media"
    if score >= 50:
        return 2, "PIPELINE FRIO", "baixa"
    return 1, "CATALOGADO", "nenhuma"


def score_prospect(prospect: ProspectV2) -> ProspectV2:
    motivos = list(prospect.score_motivos)

    prospect.score_d1_fonte = d1_fonte(prospect, motivos)
    prospect.score_d2_intencao = d2_intencao(prospect, motivos)
    prospect.score_d3_porte = d3_porte(prospect, motivos)
    prospect.score_d4_contato = d4_contato(prospect, motivos)
    prospect.score_d5_timing = d5_timing(prospect, motivos)
    prospect.score_d6_concorrencia = d6_concorrencia(prospect, motivos)

    prospect.score_total = sum([
        prospect.score_d1_fonte,
        prospect.score_d2_intencao,
        prospect.score_d3_porte,
        prospect.score_d4_contato,
        prospect.score_d5_timing,
        prospect.score_d6_concorrencia,
    ])

    has_moment_signal = (
        prospect.tem_vaga_ativa
        or prospect.tem_post_crescimento
        or prospect.tem_novo_cnpj_filial
        or (months_since(prospect.data_abertura) is not None and months_since(prospect.data_abertura) <= 6)
    )

    prospect.nivel_maturidade, prospect.nivel_label, prospect.prioridade = classify(prospect.score_total, has_moment_signal)

    if prospect.empresa_inativa:
        prospect.nivel_maturidade = min(prospect.nivel_maturidade, 2)
        prospect.nivel_label = "PIPELINE FRIO"
        prospect.prioridade = "baixa"

    if not prospect.tem_vaga_ativa and not prospect.tem_post_crescimento and months_since(prospect.data_abertura) not in (None,) and months_since(prospect.data_abertura) >= 120:
        prospect.nivel_maturidade = min(prospect.nivel_maturidade, 3)
        if prospect.nivel_maturidade == 3:
            prospect.nivel_label = "MONITORAR"
            prospect.prioridade = "media"

    prospect.score_motivos = list(dict.fromkeys(motivos))
    prospect.historico_score.append({
        "data": datetime.now().isoformat(timespec="seconds"),
        "score_total": prospect.score_total,
        "nivel": prospect.nivel_maturidade,
        "motivo_recalculo": "coleta_motor_v2",
        "d1": prospect.score_d1_fonte,
        "d2": prospect.score_d2_intencao,
        "d3": prospect.score_d3_porte,
        "d4": prospect.score_d4_contato,
        "d5": prospect.score_d5_timing,
        "d6": prospect.score_d6_concorrencia,
    })
    return prospect
