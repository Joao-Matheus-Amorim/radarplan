# Radar PME Saúde v4

Radar local de inteligência comercial para gerar leads qualificados de plano de saúde PME com custo zero.

A ideia não é juntar lista fria. O sistema busca sinais públicos, pontua oportunidades e exporta uma fila diária com motivo claro para contato.

## O que a v4 faz

- Prospecta automaticamente candidatos em fontes públicas usando buscas web.
- Trabalha com múltiplas frentes: vagas, contadores, nichos locais, crescimento público e parceiros indiretos.
- Deduplica empresas.
- Extrai telefone, e-mail, WhatsApp e sinais comerciais do conteúdo encontrado.
- Calcula score por regras.
- Gera motivo comercial e abordagem inicial.
- Exporta `exports/fila_do_dia.csv` para o vendedor trabalhar.
- Tem camada opcional de IA local via Ollama, sem depender de API paga.

## Instalação no Windows PowerShell

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Primeiro uso

```powershell
python main.py init
python main.py prospectar --cidade "Niterói" --uf RJ --fila 30
```

Saídas geradas:

```text
exports/resultados_prospeccao_bruta.csv
exports/fila_do_dia.csv
radar.sqlite3
```

## Comandos úteis

```powershell
python main.py prospectar --cidade "Niterói" --uf RJ --fila 30
python main.py prospectar-vagas --cidade "Niterói" --uf RJ --cargo "recepcionista"
python main.py prospectar-contadores --cidade "Niterói" --uf RJ
python main.py prospectar-nichos --cidade "Niterói" --uf RJ --nicho "clínica odontológica"
python main.py prospectar-crescimento --cidade "Niterói" --uf RJ
python main.py prospectar-parceiros --cidade "Niterói" --uf RJ
python main.py fila --limit 30
```

## IA local opcional

A IA não é obrigatória. O sistema funciona sem ela.

Se quiser usar IA local, instale o Ollama e rode um modelo:

```powershell
ollama run llama3.2
```

Depois:

```powershell
python main.py prospectar --cidade "Niterói" --uf RJ --fila 30 --ia
```

A IA local melhora resumo, classificação e abordagem. Se não estiver disponível, o sistema cai automaticamente para regras fixas.

## Filosofia

O sistema precisa responder uma pergunta por lead:

> Por que essa empresa deve ser contatada hoje?

Sem resposta clara, o lead não entra na fila principal.
