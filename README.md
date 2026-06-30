# Radar PME Saúde v4.1

Radar local de inteligência comercial para gerar leads qualificados de plano de saúde PME com custo zero.

O sistema busca sinais públicos, pontua oportunidades e exporta uma fila diária com motivo claro para contato.

## O que mudou na v4.1

A busca deixou de depender de uma única fonte. O motor agora usa um roteador com fallback:

1. DuckDuckGo HTML.
2. Bing HTML.
3. SearXNG opcional, se `RADAR_SEARX_URL` estiver configurado.

Se um provedor voltar zero, o próximo é testado automaticamente. O comando `--debug` mostra o status de cada provedor.

## Fontes comerciais

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

## Testar o motor de busca

```powershell
python main.py search-test '"clínica odontológica" "Niterói" "WhatsApp"'
```

Com diagnóstico:

```powershell
python main.py prospectar --cidade "Niterói" --uf RJ --por-fonte 20 --fila 30 --debug
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

## SearXNG opcional

Se você tiver uma instância SearXNG pública ou própria:

```powershell
$env:RADAR_SEARX_URL="https://sua-instancia-searxng.com"
python main.py search-test '"contador" "Niterói" "WhatsApp"'
```

Sem essa variável, o sistema ignora SearXNG e usa DuckDuckGo + Bing.

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
