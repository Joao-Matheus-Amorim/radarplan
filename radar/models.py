from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Lead:
    source: str
    name: str
    city: str
    uf: str
    url: str = ""
    title: str = ""
    snippet: str = ""
    segment: str = ""
    phone: str = ""
    whatsapp: str = ""
    email: str = ""
    score: int = 0
    priority: str = ""
    reason: str = ""
    approach: str = ""
    status: str = "novo"
    tags: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def row(self) -> dict[str, Any]:
        return {
            "prioridade": self.priority,
            "score": self.score,
            "tipo_lead": self.source,
            "empresa": self.name,
            "titulo": self.title,
            "segmento": self.segment,
            "cidade": self.city,
            "uf": self.uf,
            "telefone": self.phone,
            "whatsapp": self.whatsapp,
            "email": self.email,
            "site": self.url,
            "url_origem": self.url,
            "motivo": self.reason,
            "abordagem": self.approach,
            "tags": "; ".join(self.tags),
            "evidencias": " | ".join(self.evidence[:5]),
            "status": self.status,
            "created_at": self.created_at,
        }
