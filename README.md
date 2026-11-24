# ETL Verdejar

Pipeline em Python que extrai clientes e pedidos de uma API HTTP local e produtos de um CSV, trata seis inconsistências conhecidas e carrega os dados no PostgreSQL com reconciliação e testes automatizados.

| | |
|---|---|
| **Linguagem** | Python 3.14.10 (`.venv`) |
| **Banco** | PostgreSQL 18.6 local, database `verdejar` |
| **Dependências** | `requests` 2.32.5, `psycopg[binary]` 3.2.13, `pytest` (dev) |
| **Carga** | UPSERT em transação única, idempotente |
| **Testes** | 13 testes, 13 passando |

```text
API REST + CSV → extração → brutos/ (JSON) → transformação → carga (UPSERT) → reconciliação
```

## Resultado em resumo

- Origem e PostgreSQL coincidem: 1.000 clientes, 12 produtos, 5.000 pedidos únicos (de 5.100 recebidos) e 12.455 itens. A soma de `valor_itens` é R$ 311.228,75 nos dois lados.
- Duas cargas consecutivas produziram as mesmas contagens.
- Os contadores são calculados dinamicamente; valores fixos aparecem apenas nos testes, como referência do desafio.

## Como executar

**Pré-requisitos:** Python 3.14 (`python3.14` no PATH; o `python3` do sistema pode ser outra versão), PostgreSQL com o banco `verdejar` e o `insumos/schema.sql` aplicados (passo 1) e a API rodando.

### 1. Banco (uma vez, se ainda não existir)

Na raiz do projeto. O `schema.sql` usa `CREATE TABLE IF NOT EXISTS`, então reaplicá-lo é seguro; o `CREATE DATABASE` falha se o banco já existir.

```bash
psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE verdejar;"
psql -h localhost -p 5432 -U postgres -d verdejar -f insumos/schema.sql
```

### 2. Ambiente (raiz do projeto)

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

`requirements.txt` lista as dependências necessárias para executar o ETL. `requirements-dev.txt` inclui essas dependências e acrescenta `pytest`, usado para rodar os testes.

### 3. API (terminal 1, pasta `insumos/`)

O `--dados` padrão da API é relativo à pasta atual, por isso o `cd`.

```bash
cd insumos
python3 api_verdejar.py
```

### 4. ETL (terminal 2, raiz do projeto)

```bash
source .venv/bin/activate
python -m etl.main              # só extrai e transforma; não grava no banco
```

Para carregar no PostgreSQL, informe a senha por variável de ambiente (nada de credenciais no repositório):

```bash
read -s "VERDEJAR_DB_PASSWORD?Senha do PostgreSQL: "   # sintaxe do zsh
echo
export VERDEJAR_DB_PASSWORD
python -m etl.main --carregar
unset VERDEJAR_DB_PASSWORD
```

**Variáveis de conexão.** Host, porta, banco e usuário têm padrão; a senha não. Sem `VERDEJAR_DB_PASSWORD`, o Psycopg/libpq procura `~/.pgpass` (ou o arquivo indicado em `PGPASSFILE`).

| Variável | Padrão |
|---|---|
| `VERDEJAR_DB_HOST` | `localhost` |
| `VERDEJAR_DB_PORT` | `5432` |
| `VERDEJAR_DB_NAME` | `verdejar` |
| `VERDEJAR_DB_USER` | `postgres` |
| `VERDEJAR_DB_PASSWORD` | sem padrão |

> O Python 3.9.6 do sistema no Mac usa LibreSSL 2.8.3 e faz o `urllib3` v2 emitir um aviso. Por isso o projeto foi testado com o Python 3.14.10 do Homebrew, dentro da `.venv`.

## Estrutura

```text
.
├── etl/
│   ├── extracao.py        # API paginada, gravação em brutos/, leitura do CSV
│   ├── transformacao.py   # funções puras das armadilhas A1–A6
│   ├── carga.py           # UPSERT, transação e reconciliação
│   └── main.py            # orquestração (flag --carregar)
├── tests/                 # pytest: transformação e reconciliação
├── insumos/               # API, schema.sql e dados de origem
├── evidencias/            # contrato de dados e evidências por fase
├── brutos/                # snapshots JSON da extração (fora do Git)
├── consultas_validacao.sql
├── COMO_USEI_IA.md
└── requirements.txt, requirements-dev.txt
```

## Extração

Percorre todas as páginas da API (`page_size=50`), valida status HTTP, estrutura da resposta e totais de paginação, e confere que recebeu todos os registros. Antes de transformar, grava uma cópia fiel em `brutos/` (nome com data e hora, nunca sobrescreve). Produtos vêm de `insumos/dados/produtos.csv`.

## Transformação

| | Armadilha | Tratamento | Contador |
|---|---|---|---:|
| A1 | E-mail nulo | Cliente preservado, e-mail continua `NULL` | 81 |
| A2 | Estado em minúsculas | Convertido para maiúsculas | 151 |
| A3 | Data em `DD/MM/AAAA` | Aceita os dois formatos e converte para `date` | 1.037 |
| A4 | `valor_total` com vírgula | Convertido para `Decimal` com duas casas | 1.255 |
| A5 | Pedido duplicado | Mantém a primeira ocorrência; mesmo ID com conteúdo diferente é conflito e interrompe | 100 |
| A6 | Total diverge dos itens | `valor_itens` calculado; `valor_total` preservado; divergente se a diferença for maior que R$ 0,01 | 238 |

A3, A4 e A6 são contados sobre os 5.000 pedidos únicos. A diferença de R$ 819,00 entre as somas de `valor_total` e `valor_itens` vem da origem e é preservada; não é erro do ETL.

### Conferência independente

Uma recontagem independente dos snapshots em `brutos/`, usando `json` e `Decimal` da biblioteca padrão e sem importar código de `etl/`, confirmou os contadores e totais apresentados acima. Não foram encontrados conflitos entre pedidos repetidos.

## Carga e idempotência

`carregar_dados` aplica UPSERTs (`INSERT ... ON CONFLICT ... DO UPDATE`) em `produtos`, `clientes`, `pedidos` e `itens_pedido`, nessa ordem, dentro de uma única transação. Se qualquer etapa falhar, nada é gravado. Todas as consultas são parametrizadas (`%s` + `executemany`); nenhum dado é concatenado ao SQL.

**Por que UPSERT.** Repetir a carga atualiza as chaves existentes em vez de duplicá-las e permite aplicar correções vindas da origem. Alternativas descartadas:

- `ON CONFLICT DO NOTHING`: manteria valores antigos quando chegasse uma correção.
- Limpar ou truncar as tabelas antes da carga: apagaria todos os registros antes da reposição.

**Limite.** O UPSERT não remove linhas que sumiram da origem (por exemplo, um item antigo de um pedido que passou a ter menos itens). A garantia de contagens iguais vale para execuções repetidas com o mesmo conjunto de dados.

## Reconciliação

Executada dentro da transação, logo após os UPSERTs. Uma divergência cancela a carga.

| Medida | Origem | PostgreSQL | Resultado |
|---|---:|---:|---|
| Clientes | 1.000 | 1.000 | confere |
| Produtos | 12 | 12 | confere |
| Pedidos únicos | 5.000 | 5.000 | confere |
| Itens de pedido | 12.455 | 12.455 | confere |
| Pedidos divergentes | 238 | 238 | confere |
| Soma de `valor_itens` | R$ 311.228,75 | R$ 311.228,75 | diferença R$ 0,00 |

Contagens exigem igualdade exata; a soma de `valor_itens` tem tolerância de R$ 0,01.

### Evidência de duas execuções

Duas execuções seguidas de `python -m etl.main --carregar` em 22/11/2026, sem limpar as tabelas. Resumo das linhas finais que o ETL imprimiu em cada uma; os contadores A1–A6 também foram idênticos e coincidem com a tabela da Transformação. Em ambas, `diferenca=0.00` e a transação foi confirmada. Detalhes em [`evidencias/EVIDENCIAS_FASE_3.md`](evidencias/EVIDENCIAS_FASE_3.md).

| Execução | Clientes | Produtos | Pedidos | Itens | Divergentes | `valor_itens` (origem = destino) |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 1.000 | 12 | 5.000 | 12.455 | 238 | R$ 311.228,75 |
| 2 | 1.000 | 12 | 5.000 | 12.455 | 238 | R$ 311.228,75 |

Snapshots brutos de cada execução, em `brutos/`:

| Execução | Clientes | Pedidos |
|---|---|---|
| 1 | `clientes_20261122T165612891525-0300.json` | `pedidos_20261122T165613028338-0300.json` |
| 2 | `clientes_20261122T165613462191-0300.json` | `pedidos_20261122T165613595687-0300.json` |

## Consultas de validação

Em `consultas_validacao.sql`:

```bash
psql -h localhost -p 5432 -U postgres -d verdejar -f consultas_validacao.sql
```

Retornou 10 linhas de vendas mensais, 1 de conferência, 5 de pedidos por estado e 238 pedidos divergentes.

**Definição de "vendas".** Soma de `pedidos.valor_total`: valor bruto informado pela origem, incluindo pedidos divergentes e todos os status, inclusive cancelados. Não é receita líquida. `valor_itens` serve para detectar divergências, não entra no total.

### Vendas por mês

| Mês | Total de vendas |
|---|---:|
| 2026-01 | R$ 30.449,02 |
| 2026-02 | R$ 33.923,86 |
| 2026-03 | R$ 30.678,70 |
| 2026-04 | R$ 31.253,96 |
| 2026-05 | R$ 30.890,02 |
| 2026-06 | R$ 31.627,73 |
| 2026-07 | R$ 32.796,17 |
| 2026-08 | R$ 29.328,04 |
| 2026-09 | R$ 29.995,71 |
| 2026-10 | R$ 31.104,54 |
| **Soma dos meses** | **R$ 312.047,75** |
| **Soma geral de `pedidos.valor_total`** | **R$ 312.047,75** |

A consulta `conferencia_soma_vendas_mes` retornou soma mensal R$ 312.047,75, soma geral R$ 312.047,75, diferença R$ 0,00 e `confere = t`. O pytest repete essa comparação exigindo igualdade exata, pois os dois lados são `NUMERIC`.

### Pedidos por estado do cliente

| Estado | Pedidos |
|---|---:|
| MG | 476 |
| PR | 974 |
| RS | 1.543 |
| SC | 1.127 |
| SP | 880 |
| **Total** | **5.000** |

### Pedidos divergentes

238 pedidos com `divergente = TRUE`. Os cinco primeiros:

| Pedido | `valor_total` | `valor_itens` | Diferença |
|---:|---:|---:|---:|
| 1 | R$ 125,84 | R$ 130,84 | R$ 5,00 |
| 51 | R$ 26,58 | R$ 23,58 | R$ 3,00 |
| 71 | R$ 144,35 | R$ 134,35 | R$ 10,00 |
| 81 | R$ -1,84 | R$ 3,16 | R$ 5,00 |
| 106 | R$ 47,78 | R$ 44,78 | R$ 3,00 |

## Testes

```bash
python -m pytest -v -p no:cacheprovider
```

- `tests/test_transformacao.py` (10 testes): A1 a A6, estado inválido, data inexistente, conflito de pedido e limite da tolerância financeira.
- `tests/test_reconciliacao.py` (3 testes): reconciliação origem × PostgreSQL, idempotência e soma mensal.

**Antes de rodar.** `brutos/` está no `.gitignore`, então em um clone novo a pasta começa vazia. Com a API e o PostgreSQL no ar, rode antes `python -m etl.main --carregar`: ele gera os snapshots que os testes leem e carrega o banco. **Os testes de reconciliação usam o banco configurado:** o de idempotência faz dois UPSERTs e nenhum limpa as tabelas. Use apenas o banco local de desenvolvimento.

Saída real (o caminho local foi substituído por `<projeto>`):

```text
(.venv) $ python -m pytest -v -p no:cacheprovider
============================= test session starts ==============================
platform darwin -- Python 3.14.10, pytest-8.4.2, pluggy-1.7.0 -- <projeto>/.venv/bin/python
rootdir: <projeto>
collecting ... collected 13 items

tests/test_reconciliacao.py::test_reconciliacao_contagens_e_totais_apos_carga PASSED [  7%]
tests/test_reconciliacao.py::test_idempotencia_da_carga_mantem_contagens PASSED [ 15%]
tests/test_reconciliacao.py::test_soma_vendas_mensais_bate_com_soma_geral PASSED [ 23%]
tests/test_transformacao.py::test_a1_conta_emails_ausentes_sem_alterar_clientes PASSED [ 30%]
tests/test_transformacao.py::test_a2_padroniza_estado_em_maiusculas_e_conta_alteracoes PASSED [ 38%]
tests/test_transformacao.py::test_a2_rejeita_estado_que_nao_seja_duas_letras_ascii PASSED [ 46%]
tests/test_transformacao.py::test_a3_converte_os_dois_formatos_de_data_e_conta_datas_com_barras PASSED [ 53%]
tests/test_transformacao.py::test_a4_converte_valor_com_virgula_para_decimal_e_conta_ocorrencias PASSED [ 61%]
tests/test_transformacao.py::test_a5_remove_repeticao_identica_e_conta_duplicados PASSED [ 69%]
tests/test_transformacao.py::test_a6_calcula_soma_dos_itens_e_sinaliza_divergencia PASSED [ 76%]
tests/test_transformacao.py::test_a3_data_inexistente_gera_erro PASSED   [ 84%]
tests/test_transformacao.py::test_a5_mesmo_id_com_conteudo_diferente_sinaliza_conflito PASSED [ 92%]
tests/test_transformacao.py::test_a6_limite_da_tolerancia_e_valor_total_preservado PASSED [100%]

============================== 13 passed in 0.48s ==============================
```

## Limitações conhecidas

- O UPSERT não propaga remoções da origem (ver [Carga e idempotência](#carga-e-idempotência)).
- A extração não faz novas tentativas: a primeira falha de rede ou de resposta interrompe a execução com `ErroExtracao`.
- Os testes de reconciliação dependem de uma carga prévia e de snapshots em `brutos/`.

## Documentação relacionada

- [`evidencias/CONTRATO_DE_DADOS.md`](evidencias/CONTRATO_DE_DADOS.md): campos, tipos, nulabilidade e transformações.
- `evidencias/EVIDENCIAS_FASE_1.md`, `EVIDENCIAS_FASE_3.md` e `EVIDENCIAS_FASE_4_TESTES.md`: evidências por fase.
- [`COMO_USEI_IA.md`](COMO_USEI_IA.md): sugestões aceitas e rejeitadas e falhas encontradas no uso de IA.
