from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

FIELDS = ["data", "empresa", "telefone", "tipo_lead", "status", "observacao", "mes_reajuste", "proxima_acao"]


def init_project() -> None:
    Path("data").mkdir(exist_ok=True)
    Path("exports").mkdir(exist_ok=True)
    feedback = Path("data/feedback.csv")
    if not feedback.exists():
        with feedback.open("w", newline="", encoding="utf-8-sig") as file:
            csv.DictWriter(file, fieldnames=FIELDS).writeheader()


def add_feedback(empresa: str, status: str, telefone: str = "", tipo: str = "", obs: str = "", mes_reajuste: str = "", proxima_acao: str = "") -> Path:
    init_project()
    path = Path("data/feedback.csv")
    with path.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writerow({
            "data": datetime.now().isoformat(timespec="seconds"),
            "empresa": empresa,
            "telefone": telefone,
            "tipo_lead": tipo,
            "status": status,
            "observacao": obs,
            "mes_reajuste": mes_reajuste,
            "proxima_acao": proxima_acao,
        })
    return path
