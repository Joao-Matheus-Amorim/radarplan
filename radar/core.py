from __future__ import annotations

import csv, json, os, re, time, unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs, unquote
from urllib.request import Request, urlopen
import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; RadarPMESaude/4.0)"
DEFAULT_SOURCES = ["vagas", "contadores", "nichos", "crescimento", "parceiros"]
CARGOS = ["recepcionista", "analista administrativo", "vendedor", "enfermeiro", "técnico", "coordenador", "desenvolvedor", "auxiliar administrativo", "analista de rh"]
NICHOS = ["clínica odontológica", "clínica médica", "laboratório", "escritório contábil", "escritório de advocacia", "empresa de engenharia", "agência de marketing", "escola particular", "transportadora", "empresa de segurança", "clínica veterinária", "clínica de fisioterapia"]
PARCEIROS = ["contador", "consultoria de RH", "agência de recrutamento", "BPO financeiro", "medicina do trabalho", "clínica ocupacional", "segurança do trabalho"]
CRESCIMENTO = ["estamos contratando", "nova unidade", "nova filial", "inauguração", "nosso time cresceu", "bem-vindos ao time", "expansão", "nova sede", "trabalhe conosco"]
SAUDE = ["plano de saúde", "assistência médica", "convênio médico", "seguro saúde", "plano médico", "assistência odontológica", "plano odontológico", "benefício saúde", "auxílio saúde"]
BENEFICIO_FRACO = ["vale transporte", "vale alimentação", "vale refeição", "bonificação", "comissão", "cesta básica", "ajuda de custo", "benefício flexível"]
PHONE_RE = re.compile(r"(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\s?)?\d{4}[-.\s]?\d{4}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())


def has_any(text: str, terms: list[str]) -> bool:
    low = norm(text)
    return any(norm(t) in low for t in terms)


def clean_name(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip(" -|•\n\t")
    parts = [p.strip() for p in re.split(r"[|•]", s) if p.strip()] or [s]
    block = ["linkedin", "gupy", "indeed", "glassdoor", "facebook", "instagram", "google"]
    for p in parts:
        if len(p) > 2 and not any(b in norm(p) for b in block):
            return p[:120]
    return (s or "Empresa não identificada")[:120]


def phones(text: str) -> list[str]:
    out = []
    for m in PHONE_RE.findall(text or ""):
        p = re.sub(r"\s+", " ", m).strip()
        d = re.sub(r"\D", "", p)
        if 10 <= len(d) <= 13 and p not in out:
            out.append(p)
    return out[:5]


def emails(text: str) -> list[str]:
    out = []
    for e in EMAIL_RE.findall(text or ""):
        if e.lower() not in [x.lower() for x in out]:
            out.append(e)
    return out[:5]


def unwrap(url: str) -> str:
    parsed = urlparse(url or "")
    qs = parse_qs(parsed.query)
    for k in ("uddg", "url", "u"):
        if k in qs and qs[k]:
            return unquote(qs[k][0])
    return url or ""


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
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def row(self) -> dict:
        return {"prioridade": self.priority, "score": self.score, "tipo_lead": self.source, "empresa": self.name, "titulo": self.title, "segmento": self.segment, "cidade": self.city, "uf": self.uf, "telefone": self.phone, "whatsapp": self.whatsapp, "email": self.email, "site": self.url, "url_origem": self.url, "motivo": self.reason, "abordagem": self.approach, "tags": "; ".join(self.tags), "evidencias": " | ".join(self.evidence[:5]), "status": self.status, "created_at": self.created_at}


class Fetcher:
    def __init__(self, timeout: int = 15, sleep: float = 0.7):
        self.timeout, self.sleep = timeout, sleep
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def search(self, query: str, limit: int = 10) -> list[tuple[str, str, str]]:
        try:
            r = self.session.get("https://duckduckgo.com/html/?" + urlencode({"q": query}), timeout=self.timeout)
            r.raise_for_status()
        except Exception:
            return []
        time.sleep(self.sleep)
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for item in soup.select(".result"):
            link = item.select_one("a.result__a") or item.select_one("a")
            if not link: continue
            title = link.get_text(" ", strip=True)
            url = unwrap(link.get("href", ""))
            sn = item.select_one(".result__snippet")
            snippet = sn.get_text(" ", strip=True) if sn else ""
            if title and url: out.append((title, url, snippet))
            if len(out) >= limit: break
        return out

    def text(self, url: str) -> str:
        try:
            r = self.session.get(url, timeout=self.timeout)
            if r.status_code >= 400 or "pdf" in r.headers.get("content-type", "").lower(): return ""
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg"]): tag.decompose()
            return soup.get_text(" ", strip=True)[:20000]
        except Exception:
            return ""


def queries(source: str, city: str, uf: str) -> list[tuple[str, str]]:
    q = []
    if source == "vagas":
        for c in CARGOS:
            q += [(f'site:gupy.io "{c}" "{city}" {uf} "benefícios"', c), (f'"{c}" "{city}" "CLT" "benefícios" "vaga"', c), (f'"{c}" "{city}" "vale transporte" "vaga"', c)]
    elif source == "contadores":
        q = [(f'"escritório contábil" "{city}" "WhatsApp"', "escritório contábil"), (f'"contabilidade" "{city}" "abertura de empresa"', "escritório contábil"), (f'"contabilidade" "{city}" "folha de pagamento"', "escritório contábil"), (f'"contador" "{city}" "departamento pessoal"', "escritório contábil")]
    elif source == "nichos":
        for n in NICHOS: q += [(f'"{n}" "{city}" "WhatsApp"', n), (f'"{n}" "{city}" "equipe"', n), (f'"{n}" "{city}" "trabalhe conosco"', n)]
    elif source == "crescimento":
        q = [(f'"{t}" "{city}" empresa {uf}', "sinal de crescimento") for t in CRESCIMENTO]
    elif source == "parceiros":
        for p in PARCEIROS: q += [(f'"{p}" "{city}" "empresas"', p), (f'"{p}" "{city}" "WhatsApp"', p)]
    return q


def collect_source(source: str, city: str, uf: str, limit: int, fetcher: Fetcher) -> list[Lead]:
    leads = []
    for query, segment in queries(source, city, uf):
        for title, url, snippet in fetcher.search(query, 5):
            full = f"{title} {snippet} {fetcher.text(url)}"
            ph, em = phones(full), emails(full)
            tags = [source, segment]
            if source == "vagas":
                tags.append("contratando")
                if not has_any(full, SAUDE): tags.append("sem_plano_citado")
                if has_any(full, BENEFICIO_FRACO): tags.append("beneficios_basicos")
            if source == "contadores":
                tags.append("parceria")
                if has_any(full, ["folha de pagamento", "departamento pessoal"]): tags.append("folha_pagamento")
                if has_any(full, ["abertura de empresa", "abrir empresa", "legalização"]): tags.append("abertura_empresa")
            if source == "nichos":
                if has_any(full, ["equipe", "nosso time", "colaboradores"]): tags.append("sinal_equipe")
                if has_any(full, ["trabalhe conosco", "vagas", "carreira"]): tags.append("sinal_contratacao")
            leads.append(Lead(source, clean_name(title), city, uf, url, title[:160], snippet[:500], segment, ph[0] if ph else "", ph[0] if ph else "", em[0] if em else "", tags=tags, evidence=[snippet[:240]]))
            if len(leads) >= limit: return leads
    return leads


def reason(lead: Lead) -> str:
    if lead.source == "contadores": return "Escritório contábil pode indicar clientes PME; bom canal de parceria."
    if lead.source == "vagas": return "Empresa aparece contratando; sem plano citado no contexto coletado." if "sem_plano_citado" in lead.tags else "Empresa aparece contratando, indicando movimento de equipe."
    if lead.source == "crescimento": return "Há sinal público de crescimento, expansão, inauguração ou contratação."
    if lead.source == "parceiros": return "Possível parceiro indireto com acesso a empresas em contratação, folha ou crescimento."
    return f"Empresa de nicho local prioritário ({lead.segment}) com presença pública coletada."


def approach(lead: Lead) -> str:
    if lead.source == "contadores": return f"Olá, tudo bem? Vi que a {lead.name} atua com contabilidade em {lead.city}. Trabalho com planos de saúde PME e estou fechando parcerias com escritórios contábeis da região. Quando algum cliente precisar de plano para sócios ou funcionários, você me indica, eu faço a cotação e atendimento, e se fechar você recebe pela indicação. Sem custo e sem trabalho operacional para o escritório."
    if lead.source == "vagas": return f"Olá, tudo bem? Vi que vocês estão contratando em {lead.city}. Como candidatos costumam comparar benefícios antes de aceitar proposta, notei que o contexto coletado não destaca plano de saúde. Consigo simular opções PME para deixar a proposta mais competitiva. Posso te mandar uma comparação rápida?"
    if lead.source == "crescimento": return f"Olá, tudo bem? Vi um sinal de crescimento ou expansão da {lead.name} em {lead.city}. Nessa fase, muitas empresas revisam benefícios para contratar e reter melhor. Consigo simular planos PME para equipes pequenas e médias. Quer que eu envie uma comparação?"
    if lead.source == "parceiros": return f"Olá, tudo bem? Vi que a {lead.name} atua com {lead.segment} em {lead.city}. Estou buscando parceiros que atendem empresas em fase de contratação ou crescimento. Quando algum cliente precisar de plano PME, eu cuido da cotação e atendimento, e você participa pela indicação. Podemos conversar?"
    return f"Olá, tudo bem? Vi a {lead.name} em {lead.city} e estou levantando empresas do segmento {lead.segment} para simulação de plano de saúde PME. Consigo comparar opções para equipes pequenas e médias sem compromisso. Quer que eu te mande uma simulação?"


def score(lead: Lead) -> Lead:
    s = 0; tags = set(lead.tags)
    if lead.source == "contadores": s += 45 + (25 if lead.phone else 0) + (18 if "folha_pagamento" in tags else 0) + (14 if "abertura_empresa" in tags else 0)
    elif lead.source == "vagas": s += 35 + (30 if "sem_plano_citado" in tags else 0) + (10 if "beneficios_basicos" in tags else 0) + (15 if lead.phone else 0)
    elif lead.source == "nichos": s += 30 + (25 if lead.phone else 0) + (14 if "sinal_equipe" in tags else 0) + (18 if "sinal_contratacao" in tags else 0)
    elif lead.source == "crescimento": s += 53 + (20 if lead.phone else 0)
    elif lead.source == "parceiros": s += 35 + (25 if lead.phone else 0)
    s += 5 if lead.url else 0; s += 5 if lead.city else 0
    if not lead.phone and not lead.email: s -= 15
    if any(b in norm(lead.name) for b in ["concurso", "prefeitura", "wikipedia"]): s -= 40
    lead.score = max(0, min(100, s))
    lead.priority = "ligar hoje" if lead.score >= 85 else "validar manualmente" if lead.score >= 70 else "enriquecer" if lead.score >= 50 else "baixo"
    lead.reason = reason(lead); lead.approach = approach(lead)
    return lead


def dedupe(leads: list[Lead]) -> list[Lead]:
    seen, out = set(), []
    for lead in leads:
        domain = urlparse(lead.url).netloc.replace("www.", "")
        key = norm(f"{lead.name}|{lead.city}|{lead.phone or domain}")
        if key not in seen:
            seen.add(key); out.append(lead)
    return out


def enhance_ai(lead: Lead) -> Lead:
    endpoint = os.getenv("RADAR_IA_ENDPOINT", "http://localhost:11434/api/generate")
    prompt = f"Resuma a oportunidade comercial B2B em 1 frase e gere abordagem curta. Não invente dados. Retorne JSON com resumo e abordagem. Lead: {lead.row()}"
    try:
        payload = json.dumps({"model": os.getenv("RADAR_IA_MODEL", "llama3.1:8b"), "prompt": prompt, "stream": False}).encode()
        req = Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
        response = json.loads(urlopen(req, timeout=25).read().decode()).get("response", "")
        a, b = response.find("{"), response.rfind("}")
        if a >= 0 and b > a:
            data = json.loads(response[a:b+1]); lead.reason = data.get("resumo", lead.reason)[:500]; lead.approach = data.get("abordagem", lead.approach)[:1200]; lead.tags.append("ia_local")
    except Exception:
        lead.tags.append("ia_indisponivel")
    return lead


def export_csv(leads: list[Lead], path: str | Path) -> Path:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(leads[0].row().keys()) if leads else ["prioridade", "score", "tipo_lead", "empresa", "motivo", "abordagem"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); [w.writerow(lead.row()) for lead in leads]
    return path


def prospectar(city: str, uf: str, sources: list[str] | None = None, per_source: int = 20, use_ai: bool = False) -> list[Lead]:
    fetcher = Fetcher(); leads = []
    for source in sources or DEFAULT_SOURCES:
        source = source.strip().lower()
        if source not in DEFAULT_SOURCES: continue
        print(f"[radar] Coletando fonte: {source}")
        chunk = collect_source(source, city, uf, per_source, fetcher)
        print(f"[radar] {source}: {len(chunk)} candidatos")
        leads.extend(chunk)
    leads = sorted([score(x) for x in dedupe(leads)], key=lambda x: x.score, reverse=True)
    if use_ai:
        print("[radar] IA local solicitada; se Ollama não estiver ativo, segue sem quebrar.")
        leads = [enhance_ai(x) for x in leads]
    return leads


def run_and_export(city: str, uf: str, sources: list[str] | None = None, per_source: int = 20, fila: int = 30, use_ai: bool = False) -> tuple[str, str, int]:
    leads = prospectar(city, uf, sources, per_source, use_ai)
    raw = export_csv(leads, "exports/resultados_prospeccao_bruta.csv")
    final = export_csv(leads[:fila], "exports/fila_do_dia.csv")
    return str(raw), str(final), len(leads[:fila])


def init_project() -> None:
    Path("data").mkdir(exist_ok=True); Path("exports").mkdir(exist_ok=True)
    feedback = Path("data/feedback.csv")
    if not feedback.exists():
        with feedback.open("w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=["data", "empresa", "telefone", "tipo_lead", "status", "observacao", "mes_reajuste", "proxima_acao"]).writeheader()


def add_feedback(empresa: str, status: str, telefone: str = "", tipo: str = "", obs: str = "", mes_reajuste: str = "", proxima_acao: str = "") -> Path:
    init_project(); path = Path("data/feedback.csv")
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["data", "empresa", "telefone", "tipo_lead", "status", "observacao", "mes_reajuste", "proxima_acao"])
        w.writerow({"data": datetime.now().isoformat(timespec="seconds"), "empresa": empresa, "telefone": telefone, "tipo_lead": tipo, "status": status, "observacao": obs, "mes_reajuste": mes_reajuste, "proxima_acao": proxima_acao})
    return path
