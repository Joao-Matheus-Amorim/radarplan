from __future__ import annotations

import argparse
from radar.core import DEFAULT_SOURCES, add_feedback, export_csv, init_project, prospectar, run_and_export


def main():
    parser = argparse.ArgumentParser(description="Radar PME Saúde v4")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")
    sub.add_parser("sources")

    p = sub.add_parser("prospectar")
    p.add_argument("--cidade", required=True)
    p.add_argument("--uf", required=True)
    p.add_argument("--sources", help="vagas,contadores,nichos,crescimento,parceiros")
    p.add_argument("--por-fonte", type=int, default=20)
    p.add_argument("--fila", type=int, default=30)
    p.add_argument("--ia", action="store_true")

    p = sub.add_parser("fonte")
    p.add_argument("tipo", choices=DEFAULT_SOURCES)
    p.add_argument("--cidade", required=True)
    p.add_argument("--uf", required=True)
    p.add_argument("--limite", type=int, default=30)
    p.add_argument("--ia", action="store_true")

    p = sub.add_parser("feedback")
    p.add_argument("--empresa", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--telefone", default="")
    p.add_argument("--tipo", default="")
    p.add_argument("--obs", default="")
    p.add_argument("--mes-reajuste", default="")
    p.add_argument("--proxima-acao", default="")

    args = parser.parse_args()
    if args.cmd == "init":
        init_project()
        print("Radar PME Saúde v4 inicializado.")
    elif args.cmd == "sources":
        print("Fontes disponíveis:")
        for source in DEFAULT_SOURCES:
            print(f"- {source}")
    elif args.cmd == "prospectar":
        sources = args.sources.split(",") if args.sources else None
        raw, final, count = run_and_export(args.cidade, args.uf, sources, args.por_fonte, args.fila, args.ia)
        print(f"Prospecção bruta: {raw}")
        print(f"Fila do dia: {final} ({count} leads)")
    elif args.cmd == "fonte":
        leads = prospectar(args.cidade, args.uf, [args.tipo], args.limite, args.ia)
        path = export_csv(leads, f"exports/{args.tipo}_{args.cidade}_{args.uf}.csv")
        print(f"Exportado: {path} ({len(leads)} leads)")
    elif args.cmd == "feedback":
        path = add_feedback(args.empresa, args.status, args.telefone, args.tipo, args.obs, args.mes_reajuste, args.proxima_acao)
        print(f"Feedback registrado em {path}")


if __name__ == "__main__":
    main()
