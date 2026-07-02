from __future__ import annotations

from radar.v2_models import ProspectV2


def build_approach(prospect: ProspectV2) -> ProspectV2:
    empresa = prospect.nome_empresa or "sua empresa"
    cidade = prospect.cidade or "RJ"
    segmento = prospect.segmento or prospect.cnae_descricao or "empresas"

    if prospect.nivel_maturidade == 5 and prospect.tem_vaga_ativa:
        vaga = prospect.vaga_titulo or "uma vaga"
        prospect.abordagem = (
            f"Olá! Vi que a {empresa} está contratando para {vaga} em {cidade}. "
            "Empresas que estão crescendo geralmente precisam estruturar benefícios para a equipe nova. "
            "Trabalho com plano de saúde empresarial a partir de 2 vidas, com opções a partir de R$ 89 por vida. "
            "Posso fazer uma cotação sem compromisso para vocês?"
        )
        return prospect

    if prospect.nivel_maturidade >= 4 and prospect.tem_post_crescimento:
        prospect.abordagem = (
            f"Olá! Acompanho empresas de {cidade} e vi que a {empresa} está em expansão. "
            "Para equipes em crescimento, plano de saúde empresarial é um dos benefícios que mais ajuda na retenção. "
            "Posso apresentar opções rapidamente? Atendo a partir de 2 vidas, sem burocracia."
        )
        return prospect

    if prospect.data_abertura and prospect.score_d5_timing >= 18:
        prospect.abordagem = (
            f"Olá! A {empresa} está começando em {cidade}. Empresas que estruturam benefícios desde cedo "
            "conseguem contratar e reter melhor. Tenho plano de saúde empresarial a partir de 2 vidas e faço a cotação gratuitamente. "
            "Posso enviar uma simulação?"
        )
        return prospect

    if prospect.cnae_codigo and prospect.nivel_maturidade >= 3:
        prospect.abordagem = (
            f"Olá! Trabalho com planos de saúde empresariais para empresas de {segmento} em {cidade}. "
            f"Conheço bem as necessidades do setor e tenho opções personalizadas. Posso fazer uma cotação para a {empresa}? "
            "Atendo a partir de 2 vidas, sem compromisso."
        )
        return prospect

    prospect.abordagem = (
        f"Olá! Sou consultora de planos de saúde empresariais em {cidade}. "
        f"Gostaria de apresentar opções para a {empresa}. Posso fazer uma cotação gratuita? "
        "Atendo a partir de 2 vidas."
    )
    return prospect
