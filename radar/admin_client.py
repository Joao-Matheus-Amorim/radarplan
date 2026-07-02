from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from radar.normalizer import to_admin_payload
from radar.v2_models import ProspectV2


def post_to_admin(prospects: list[ProspectV2], city: str, uf: str, segment: str, query: str, admin_url: str = "", import_secret: str = "") -> None:
    target = (admin_url or os.environ.get("RADAR_ADMIN_URL") or "").rstrip("/")
    secret = import_secret or os.environ.get("RADAR_IMPORT_SECRET") or ""

    if not target:
        print("[radar-v2] RADAR_ADMIN_URL ausente. Pulando envio.")
        return

    if not secret:
        print("[radar-v2] RADAR_IMPORT_SECRET ausente. Pulando envio.")
        return

    payload = {
        "source": "radarplan_motor_v2",
        "city": city,
        "uf": uf,
        "segment": segment,
        "query": query,
        "prospects": [to_admin_payload(prospect) for prospect in prospects],
    }

    request = urllib.request.Request(
        f"{target}/api/radar?action=import",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Radar-Secret": secret,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read().decode("utf-8", errors="replace")
            print(f"[radar-v2] enviado ao admin: HTTP {response.status} {body}")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(f"[radar-v2] falha HTTP {error.code}: {body}")
    except Exception as error:
        print(f"[radar-v2] falha ao enviar: {error}")
