from __future__ import annotations

import argparse
from pathlib import Path

from radar.core import DEFAULT_SOURCES, add_feedback, export_csv, init_project, prospectar, run_and_export
from radar.fetcher import Fetcher
from radar.google_importer import import_google_file
from radar.sources import qualify_result
from radar.text_utils import emails, phones


def _parse_sources(value: str | None) -> list[str] | None:
    if not value:
        return None

    sources: list[str] = []

    for item in value.split(","):
        item = item.strip()

        if item:
            sources.append(item)

    return sources or None


def _cmd_init() -> None:
    init_project()
    print("Radar PME Saúde v4 inicializado.")


def _cmd_sources() -> None:
    print("Fontes disponíveis:")

    for source in DEFAULT_SOURCES:
        print(f"- {source}")

    print("- google_import")


def _cmd_search_test(args: argparse.Namespace) -> None:
    query = " ".join(args.query)
    fetcher = Fetcher(debug=True)
    results = fetcher.search(query, args.limit)

    print(f"Query usada: {query}")
    print(f"Resultados encontrados: {len(results)}")

    for index, result in enumerate(results, 1):
        print(f"{index}. [{result.provider}] {result.title}\n   {result.url}\n   {result.snippet[:180]}")

    if fetcher.last_status:
        print(f"Status: {fetcher.last_status}")


def _cmd_lead_test(args: argparse.Namespace) -> None:
    query = " ".join(args.query)
    fetcher = Fetcher(debug=True)
    results = fetcher.search(query, args.limit)

    print(f"Query usada: {query}")
    print(f"Suspeitos encontrados: {len(results)}")

    approved = 0
    rejected = 0

    for index, result in enumerate(results, 1):
        page_text = fetcher.text(result.url)
        full_text = f"{result.title} {result.snippet} {page_text}"

        quality = qualify_result(
            result=result,
            city=args.cidade,
            uf=args.uf,
            segment=args.segmento,
            source=args.source,
            full_text=full_text,
        )

        status = "APROVADO" if quality["accepted"] else "REJEITADO"

        if quality["accepted"]:
            approved += 1
        else:
            rejected += 1

        print("")
        print(f"[{index}] {status} | score={quality['score']}")
        print(f"Nome: {result.title}")
        print(f"URL: {result.url}")
        print(f"Motivos: {', '.join(quality['reasons'])}")

        found_phones = phones(full_text)
        found_emails = emails(full_text)

        if found_phones:
            print(f"Telefones: {', '.join(found_phones[:3])}")

        if found_emails:
            print(f"E-mails: {', '.join(found_emails[:3])}")

    print("")
    print(f"Resumo: {approved} aprovados, {rejected} rejeitados")


def _cmd_prospectar(args: argparse.Namespace) -> None:
    sources = _parse_sources(args.sources)
    raw, final, count = run_and_export(args.cidade, args.uf, sources, args.por_fonte, args.fila, args.ia, args.debug)

    print(f"Prospecção bruta: {raw}")
    print(f"Fila do dia: {final} ({count} leads)")


def _cmd_fonte(args: argparse.Namespace) -> None:
    leads = prospectar(args.cidade, args.uf, [args.tipo], args.limite, args.ia, args.debug)
    path = export_csv(leads, f"exports/{args.tipo}_{args.cidade}_{args.uf}.csv")

    print(f"Exportado: {path} ({len(leads)} leads)")


def _cmd_importar_google(args: argparse.Namespace) -> None:
    input_path = Path(args.arquivo)

    if not input_path.exists():
        raise SystemExit(f"Arquivo não encontrado: {input_path}")

    leads = import_google_file(
        path=input_path,
        city=args.cidade,
        uf=args.uf,
        segment=args.segmento,
        limit=args.limite,
        debug=args.debug,
    )

    output_path = export_csv(leads, args.saida)
    fila_leads = leads[: args.fila]
    fila_path = export_csv(fila_leads, args.fila_saida)

    print(f"Arquivo importado: {input_path}")
    print(f"Leads extraídos: {len(leads)}")
    print(f"CSV importado: {output_path}")
    print(f"Fila do dia: {fila_path} ({len(fila_leads)} leads)")

    if args.debug:
        for index, lead in enumerate(fila_leads, 1):
            fingerprint = ""

            if isinstance(lead.raw, dict):
                fingerprint = str(lead.raw.get("fingerprint", ""))

            print("")
            print(f"[{index}] {lead.name} | score={lead.score} | prioridade={lead.priority}")
            print(f"Segmento: {lead.segment}")
            print(f"Cidade: {lead.city}/{lead.uf}")

            if lead.phone:
                print(f"Telefone: {lead.phone}")

            if lead.url:
                print(f"URL: {lead.url}")

            if fingerprint:
                print(f"Fingerprint: {fingerprint}")


def _cmd_feedback(args: argparse.Namespace) -> None:
    path = add_feedback(
        args.empresa,
        args.status,
        args.telefone,
        args.tipo,
        args.obs,
        args.mes_reajuste,
        args.proxima_acao,
    )

    print(f"Feedback registrado em {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Radar PME Saúde v4")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")
    sub.add_parser("sources")

    p = sub.add_parser("search-test")
    p.add_argument("query", nargs="+", help="Query de busca. Pode vir quebrada em várias palavras.")
    p.add_argument("--limit", type=int, default=5)

    p = sub.add_parser("lead-test")
    p.add_argument("query", nargs="+", help="Query de busca. Pode vir quebrada em várias palavras.")
    p.add_argument("--cidade", required=True)
    p.add_argument("--uf", required=True)
    p.add_argument("--segmento", required=True)
    p.add_argument("--source", default="manual")
    p.add_argument("--limit", type=int, default=10)

    p = sub.add_parser("prospectar")
    p.add_argument("--cidade", required=True)
    p.add_argument("--uf", required=True)
    p.add_argument("--sources", help="vagas,contadores,nichos,crescimento,parceiros")
    p.add_argument("--por-fonte", type=int, default=20)
    p.add_argument("--fila", type=int, default=30)
    p.add_argument("--ia", "--ai", dest="ia", action="store_true")
    p.add_argument("--debug", action="store_true")

    p = sub.add_parser("fonte")
    p.add_argument("tipo", choices=DEFAULT_SOURCES)
    p.add_argument("--cidade", required=True)
    p.add_argument("--uf", required=True)
    p.add_argument("--limite", type=int, default=30)
    p.add_argument("--ia", "--ai", dest="ia", action="store_true")
    p.add_argument("--debug", action="store_true")

    p = sub.add_parser("importar-google", help="Importa TXT/HTML copiado do Google e transforma em leads com fingerprint.")
    p.add_argument("arquivo", help="Arquivo .txt, .html ou .htm salvo/copiado do Google.")
    p.add_argument("--cidade", required=True)
    p.add_argument("--uf", required=True)
    p.add_argument("--segmento", required=True)
    p.add_argument("--limite", type=int, default=100)
    p.add_argument("--fila", type=int, default=30)
    p.add_argument("--saida", default="exports/google_importado.csv")
    p.add_argument("--fila-saida", default="exports/fila_do_dia.csv")
    p.add_argument("--debug", action="store_true")

    p = sub.add_parser("feedback")
    p.add_argument("--empresa", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--telefone", default="")
    p.add_argument("--tipo", default="")
    p.add_argument("--obs", default="")
    p.add_argument("--mes-reajuste", default="")
    p.add_argument("--proxima-acao", default="")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == "init":
        _cmd_init()
    elif args.cmd == "sources":
        _cmd_sources()
    elif args.cmd == "search-test":
        _cmd_search_test(args)
    elif args.cmd == "lead-test":
        _cmd_lead_test(args)
    elif args.cmd == "prospectar":
        _cmd_prospectar(args)
    elif args.cmd == "fonte":
        _cmd_fonte(args)
    elif args.cmd == "importar-google":
        _cmd_importar_google(args)
    elif args.cmd == "feedback":
        _cmd_feedback(args)


if __name__ == "__main__":
    main()
