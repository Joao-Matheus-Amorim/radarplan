from __future__ import annotations

import csv
from pathlib import Path

from radar.models import Lead


def export_csv(leads: list[Lead], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(leads[0].row().keys()) if leads else ["prioridade", "score", "tipo_lead", "empresa", "motivo", "abordagem"]
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead.row())
    return path
