from __future__ import annotations

from datetime import date, timedelta

from radar.v2_models import ProspectV2


REVISIT_DAYS = {
    5: 1,
    4: 7,
    3: 30,
    2: 60,
    1: 120,
}


def apply_cadence(prospect: ProspectV2) -> ProspectV2:
    days = REVISIT_DAYS.get(prospect.nivel_maturidade, 120)
    revisit = date.today() + timedelta(days=days)
    prospect.revisitar_em = revisit.isoformat()

    if prospect.nivel_maturidade == 5:
        prospect.cadencia_canal = "whatsapp" if prospect.whatsapp or prospect.telefone else "email" if prospect.email else "pesquisa"
        prospect.proximo_contato_em = date.today().isoformat()
        prospect.proxima_acao = "Abordar hoje, no máximo amanhã. Revisitar em 1 dia se não houver resposta."
    elif prospect.nivel_maturidade == 4:
        prospect.cadencia_canal = "whatsapp" if prospect.whatsapp or prospect.telefone else "email" if prospect.email else "pesquisa"
        prospect.proximo_contato_em = date.today().isoformat()
        prospect.proxima_acao = "Preparar abordagem e contatar nos próximos 7 dias."
    elif prospect.nivel_maturidade == 3:
        prospect.cadencia_canal = "monitoramento"
        prospect.proxima_acao = "Não abordar ainda. Monitorar sinais e recalcular na revisita."
    elif prospect.nivel_maturidade == 2:
        prospect.cadencia_canal = "revisita"
        prospect.proxima_acao = "Pipeline frio. Manter catalogado e recalcular em 60 dias."
    else:
        prospect.cadencia_canal = "catalogado"
        prospect.proxima_acao = "Catalogado. Aguardar sinal público que mude o nível."

    return prospect
