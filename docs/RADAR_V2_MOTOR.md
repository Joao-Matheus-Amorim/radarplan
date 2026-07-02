# Radarplan Motor V2

Contrato operacional do Radarplan Motor V2 para Maisa Valentim.

O Motor V2 mantém o `google_leads.py` atual funcionando e adiciona uma camada paralela para catalogar empresas públicas, captar sinais públicos de intenção, calcular score de 0 a 200, definir nível de maturidade e enviar prospectos enriquecidos para o admin do `blog-plano-saude`.

Regra central: o sistema nunca descarta um prospecto. Toda entrada é válida. O que muda é o score, o nível, a próxima ação e a data de revisita.

## Separação entre prospecto e lead

Prospecto público fica no Radar, em `/admin/radar`.

Lead real fica no CRM, em `/admin`.

A conversão de prospecto em lead só acontece por ação explícita do admin.

## Fontes públicas

O Motor V2 usa camadas de coleta gratuitas ou de baixo custo operacional:

1. Receita Federal / CNPJ público como base estrutural.
2. BrasilAPI para enriquecimento pontual de CNPJ.
3. Vagas públicas, como Indeed RSS, Catho e InfoJobs.
4. Google Maps / Places quando houver `GOOGLE_PLACES_KEY`.
5. Redes sociais públicas encontradas por busca.
6. Sites próprios, diretórios e notícias locais.

## Score de 0 a 200

O score total é a soma de seis dimensões:

- D1 Fonte primária: 0 a 40 pontos.
- D2 Sinal de intenção: 0 a 50 pontos.
- D3 Porte estimado: 0 a 30 pontos.
- D4 Contato disponível: 0 a 40 pontos.
- D5 Timing e urgência: 0 a 30 pontos.
- D6 Concorrência estimada: 0 a 10 pontos.

`score_total = D1 + D2 + D3 + D4 + D5 + D6`

O campo legado `score` enviado ao admin recebe o mesmo valor de `score_total`.

## Níveis de maturidade

- Nível 5, `QUENTE AGORA`: score >= 140 e pelo menos um sinal de momento ativo.
- Nível 4, `PREPARAR`: score entre 110 e 139.
- Nível 3, `MONITORAR`: score entre 80 e 109.
- Nível 2, `PIPELINE FRIO`: score entre 50 e 79.
- Nível 1, `CATALOGADO`: score abaixo de 50.

Sinal de momento ativo significa vaga ativa, post de crescimento, filial nova ou empresa com menos de 6 meses.

## Revisita

Todo prospecto recebe `revisitar_em`.

- Nível 5: revisitar em 1 dia.
- Nível 4: revisitar em 7 dias.
- Nível 3: revisitar em 30 dias.
- Nível 2: revisitar em 60 dias.
- Nível 1: revisitar em 120 dias.

Se um novo sinal público aparecer antes da revisita, o score é recalculado imediatamente e o histórico recebe o motivo do recálculo.

## Execução

```powershell
python motor.py --praca "Piabetá" --uf RJ --segmento "odontologia" --limite 50 --dry-run --debug
```

Com envio:

```powershell
$env:RADAR_ADMIN_URL="https://consultoriadesaude.vercel.app"
$env:RADAR_IMPORT_SECRET="<mesmo valor da Vercel>"
python motor.py --praca "Piabetá" --uf RJ --segmento "odontologia" --limite 50 --sync-admin
```
