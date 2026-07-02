from __future__ import annotations

import argparse
import json
from pathlib import Path

from radar.admin_client import post_to_admin
from radar.approach_builder import build_approach
from radar.cadence import apply_cadence
from radar.collectors.cnpj_collector import collect_from_csv
from radar.collectors.jobs_collector import collect_indeed_rss
from radar.collectors.maps_collector import collect_places
from radar.collectors.social_collector import collect_social_signals
from radar.deduplicator import dedupe_prospects
from radar.normalizer import normalize_prospect, to_admin_payload
from radar.scorer import score_prospect
from radar.validator import validate_prospect


def load_city_population(cidade: str, uf: str) -> int:
    path = Path("data/cidades.json")
    if not path.exists():
        path = Path("data/cidades.example.json")
    if not path.exists():
        return 0

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0

    for item in data.get("praças", data.get("pracas", [])):
        if str(item.get("cidade", "")).lower() == cidade.lower() and str(item.get("uf", "")).upper() == uf.upper():
            return int(item.get("populacao") or 0)
    return 0


def build_pipeline(args: argparse.Namespace):
    prospects = []
    population = load_city_population(args.praca, args.uf)

    if args.fonte in ("todas", "cnpj") and args.cnpj_csv:
        prospects.extend(collect_from_csv(args.cnpj_csv, args.praca, args.uf, args.limite))

    if args.fonte in ("todas", "vagas"):
        prospects.extend(collect_indeed_rss(args.segmento, args.praca, args.uf, min(args.limite, 50)))

    if args.fonte in ("todas", "maps"):
        prospects.extend(collect_places(args.segmento, args.praca, args.uf, min(args.limite, 30)))

    if args.fonte in ("todas", "social"):
        prospects.extend(collect_social_signals(args.segmento, args.praca, args.uf, min(args.limite, 30), args.debug))

    for prospect in prospects:
        prospect.cidade_populacao = prospect.cidade_populacao or population
        prospect.consulta_usada = prospect.consulta_usada or f"{args.segmento} {args.praca} {args.uf}"

    prospects = [normalize_prospect(item) for item in prospects]
    prospects = dedupe_prospects(prospects)

    processed = []
    for prospect in prospects:
        prospect = validate_prospect(prospect)
        prospect = score_prospect(prospect)
        prospect = apply_cadence(prospect)
        prospect = build_approach(prospect)
        processed.append(prospect)

    return sorted(processed, key=lambda item: item.score_total, reverse=True)[: args.limite]


def export_outputs(prospects, json_path: str):
    path = Path(json_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([to_admin_payload(item) for item in prospects], ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run(args: argparse.Namespace) -> int:
    prospects = build_pipeline(args)
    output = export_outputs(prospects, args.json_saida)

    print(f"[radar-v2] prospectos processados: {len(prospects)}")
    print(f"[radar-v2] JSON: {output}")

    for index, prospect in enumerate(prospects[:10], start=1):
        print("")
        print(f"[{index}] {prospect.nome_empresa} | score={prospect.score_total}/200 | nível={prospect.nivel_maturidade} {prospect.nivel_label}")
        print(f"Próxima ação: {prospect.proxima_acao}")
        print(f"Revisitar em: {prospect.revisitar_em}")

    if args.sync_admin and not args.dry_run:
        post_to_admin(prospects, args.praca, args.uf, args.segmento, f"{args.segmento} {args.praca} {args.uf}", args.admin_url, args.import_secret)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Radarplan Motor V2 — inteligência comercial com score 0 a 200.")
    parser.add_argument("--praca", required=True, help="Cidade ou praça alvo.")
    parser.add_argument("--uf", default="RJ")
    parser.add_argument("--segmento", required=True)
    parser.add_argument("--fonte", choices=["todas", "cnpj", "vagas", "maps", "social"], default="todas")
    parser.add_argument("--limite", type=int, default=100)
    parser.add_argument("--cnpj-csv", default="", help="CSV local já filtrado/baixado da base pública de CNPJ.")
    parser.add_argument("--json-saida", default="exports/motor_output.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sync-admin", action="store_true")
    parser.add_argument("--admin-url", default="")
    parser.add_argument("--import-secret", default="")
    parser.add_argument("--debug", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
