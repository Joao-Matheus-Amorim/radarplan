from radar.scorer import score_prospect
from radar.validator import validate_prospect
from radar.v2_models import ProspectV2


def test_hot_hiring_prospect_reaches_level_5():
    prospect = ProspectV2(
        nome_empresa="Clínica Odonto Piabetá",
        cidade="Piabetá",
        uf="RJ",
        cnpj="11222333000181",
        segmento="Saúde humana",
        cnae_codigo="86",
        funcionarios_estimados=8,
        data_abertura="2025-01-01",
        tem_vaga_ativa=True,
        vaga_titulo="Auxiliar de Consultório",
        vaga_publicada_ha_dias=2,
        whatsapp="21999990000",
        email="contato@exemplo.com.br",
        site_url="https://exemplo.com.br",
        fontes=["cnpj_receita", "indeed_vaga", "google_maps"],
        cidade_populacao=18000,
    )

    prospect = score_prospect(validate_prospect(prospect))

    assert prospect.score_total >= 140
    assert prospect.nivel_maturidade == 5
    assert prospect.nivel_label == "QUENTE AGORA"
