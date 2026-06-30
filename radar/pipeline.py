from __future__ import annotations

from radar.ai import enhance_ai
from radar.config import DEFAULT_SOURCES
from radar.exporter import export_csv
from radar.fetcher import Fetcher
from radar.scoring import dedupe, score
from radar.sources import collect_source


def prospectar(city: str, uf: str, sources: list[str] | None = None, per_source: int = 20, use_ai: bool = False, debug: bool = False):
    fetcher = Fetcher(debug=debug)
    leads = []
    for source in sources or DEFAULT_SOURCES:
        source = source.strip().lower()
        if source not in DEFAULT_SOURCES:
            continue
        print(f"[radar] Coletando fonte: {source}")
        chunk = collect_source(source, city, uf, per_source, fetcher)
        print(f"[radar] {source}: {len(chunk)} candidatos")
        if debug and not chunk:
            print(f"[debug-search] Último status: {fetcher.last_status or 'sem resposta registrada'}")
        leads.extend(chunk)
    leads = sorted([score(lead) for lead in dedupe(leads)], key=lambda lead: lead.score, reverse=True)
    if use_ai:
        print("[radar] IA local solicitada; se Ollama não estiver ativo, segue sem quebrar.")
        leads = [enhance_ai(lead) for lead in leads]
    return leads


def run_and_export(city: str, uf: str, sources: list[str] | None = None, per_source: int = 20, fila: int = 30, use_ai: bool = False, debug: bool = False):
    leads = prospectar(city, uf, sources, per_source, use_ai, debug)
    raw = export_csv(leads, "exports/resultados_prospeccao_bruta.csv")
    final = export_csv(leads[:fila], "exports/fila_do_dia.csv")
    return str(raw), str(final), len(leads[:fila])
