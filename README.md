# Radar PME Saúde v4

Radar local de inteligência comercial para gerar leads qualificados de plano de saúde PME com custo zero.

O sistema busca sinais públicos, pontua oportunidades e exporta uma fila diária com motivo claro para contato.

## Fontes

- `vagas`: empresas contratando.
- `contadores`: parceiros de indicação.
- `nichos`: PMEs locais com chance de equipe.
- `crescimento`: expansão, inauguração, nova filial, time crescendo.
- `parceiros`: RH, recrutamento, BPO, medicina do trabalho e segurança do trabalho.

## Instalação

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py init
```

## Uso principal

```powershell
python main.py prospectar --cidade "Niterói" --uf RJ --por-fonte 20 --fila 30
```

Saídas:

```text
exports/resultados_prospeccao_bruta.csv
exports/fila_do_dia.csv
```

## Filtrar fontes

```powershell
python main.py prospectar --cidade "Niterói" --uf RJ --sources vagas,nichos --por-fonte 25 --fila 30
python main.py fonte contadores --cidade "Niterói" --uf RJ --limite 50
```

## IA local opcional

Com Ollama rodando:

```powershell
ollama run llama3.1:8b
python main.py prospectar --cidade "Niterói" --uf RJ --fila 30 --ia
```

Se a IA não estiver disponível, o sistema segue com regras fixas.

## Feedback comercial

```powershell
python main.py feedback --empresa "Clínica Exemplo" --status interessado --obs "Pediu cotação para 5 vidas"
python main.py feedback --empresa "Clínica Exemplo" --status tem_plano --mes-reajuste novembro --proxima-acao "retornar em outubro"
```

A pergunta central do projeto é: por que essa empresa deve ser contatada hoje?
