from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any


@dataclass
class ProspectV2:
    nome_empresa: str
    cidade: str
    uf: str = "RJ"
    segmento: str = ""
    cnpj: str = ""
    cnae_codigo: str = ""
    cnae_descricao: str = ""
    funcionarios_estimados: int = 0
    porte_receita: str = ""
    capital_social: float = 0.0
    data_abertura: str = ""
    situacao_cadastral: str = ""
    tem_vaga_ativa: bool = False
    vaga_titulo: str = ""
    vaga_publicada_ha_dias: int = 999
    tem_post_crescimento: bool = False
    post_crescimento_texto: str = ""
    tem_novo_cnpj_filial: bool = False
    telefone: str = ""
    whatsapp: str = ""
    email: str = ""
    site_url: str = ""
    instagram: str = ""
    linkedin: str = ""
    fontes: list[str] = field(default_factory=list)
    consulta_usada: str = ""
    cidade_populacao: int = 0
    coletado_em: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    score_total: int = 0
    score_d1_fonte: int = 0
    score_d2_intencao: int = 0
    score_d3_porte: int = 0
    score_d4_contato: int = 0
    score_d5_timing: int = 0
    score_d6_concorrencia: int = 0
    score_motivos: list[str] = field(default_factory=list)
    nivel_maturidade: int = 1
    nivel_label: str = "CATALOGADO"
    prioridade: str = "baixa"
    revisitar_em: str = ""
    abordagem: str = ""
    proxima_acao: str = ""
    fingerprint: str = ""
    nome_invalido: bool = False
    cnpj_invalido: bool = False
    telefone_invalido: bool = False
    empresa_inativa: bool = False
    fonte_indireta: bool = False
    cadencia_dia: int = 0
    cadencia_canal: str = ""
    ultimo_contato_em: str = ""
    proximo_contato_em: str = ""
    origem: str = "radarplan_motor_v2"
    status: str = "Novo"
    observacao_interna: str = ""
    convertido_lead_id: int | None = None
    historico_score: list[dict[str, Any]] = field(default_factory=list)
    evidencias: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScoreResult:
    total: int
    d1: int
    d2: int
    d3: int
    d4: int
    d5: int
    d6: int
    motivos: list[str]
    nivel: int
    nivel_label: str
    prioridade: str
    revisitar_em: date
