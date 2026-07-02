from __future__ import annotations

import re

from radar.v2_models import ProspectV2


def is_valid_cnpj(cnpj: str) -> bool:
    digits = re.sub(r"\D+", "", cnpj or "")
    if len(digits) != 14 or digits == digits[0] * 14:
        return False

    def calc_digit(base: str, weights: list[int]) -> str:
        total = sum(int(digit) * weight for digit, weight in zip(base, weights))
        mod = total % 11
        return "0" if mod < 2 else str(11 - mod)

    d1 = calc_digit(digits[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = calc_digit(digits[:12] + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return digits[-2:] == d1 + d2


def validate_prospect(prospect: ProspectV2) -> ProspectV2:
    name = (prospect.nome_empresa or "").strip()
    if not name or name.lower() in {"empresa", "loja", "comercio", "comércio"} or name.isdigit():
        prospect.nome_invalido = True
        prospect.score_motivos.append("Nome inválido ou genérico — não descartar, validar manualmente.")

    if prospect.cnpj and not is_valid_cnpj(prospect.cnpj):
        prospect.cnpj_invalido = True
        prospect.score_motivos.append("CNPJ inválido — zerar bônus de Receita, manter prospecto.")

    phone_digits = re.sub(r"\D+", "", prospect.telefone or prospect.whatsapp or "")
    if phone_digits and len(phone_digits) < 10:
        prospect.telefone_invalido = True
        prospect.score_motivos.append("Telefone com formato inválido — tentar outros canais.")

    if prospect.situacao_cadastral and prospect.situacao_cadastral.upper() != "ATIVA":
        prospect.empresa_inativa = True
        prospect.status = "Avaliar"
        prospect.score_motivos.append("Empresa não ativa na Receita — pipeline frio independente do restante.")

    if prospect.fontes and set(prospect.fontes).issubset({"diretorio", "doctoralia", "guiamais", "solutudo", "apontador"}):
        prospect.fonte_indireta = True
        prospect.score_motivos.append("Fonte indireta — validar existência antes de abordar.")

    return prospect
