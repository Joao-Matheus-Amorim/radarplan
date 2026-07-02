from __future__ import annotations

import csv
from pathlib import Path

from radar.v2_models import ProspectV2


def collect_from_csv(path: str | Path, cidade: str, uf: str, limit: int = 100) -> list[ProspectV2]:
    source = Path(path)
    if not source.exists():
        return []

    prospects: list[ProspectV2] = []
    with source.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")
        for row in reader:
            row_city = (row.get("municipio") or row.get("cidade") or "").strip().lower()
            row_uf = (row.get("uf") or "").strip().upper()
            if cidade and row_city and row_city != cidade.lower():
                continue
            if uf and row_uf and row_uf != uf.upper():
                continue

            prospects.append(ProspectV2(
                nome_empresa=row.get("nome_fantasia") or row.get("razao_social") or row.get("nome_empresa") or "Prospecto sem nome",
                cnpj=row.get("cnpj") or "",
                segmento=row.get("segmento") or row.get("cnae_descricao") or "",
                cnae_codigo=row.get("cnae_codigo") or row.get("cnae_principal") or "",
                cnae_descricao=row.get("cnae_descricao") or "",
                cidade=cidade,
                uf=uf,
                telefone=row.get("telefone") or "",
                email=row.get("email") or "",
                data_abertura=row.get("data_abertura") or row.get("data_inicio_atividade") or "",
                porte_receita=row.get("porte") or row.get("porte_receita") or "",
                capital_social=float(str(row.get("capital_social") or 0).replace(",", ".") or 0),
                situacao_cadastral=row.get("situacao_cadastral") or "",
                fontes=["cnpj_receita"],
                raw={"cnpj_csv": row},
            ))
            if len(prospects) >= limit:
                break
    return prospects
