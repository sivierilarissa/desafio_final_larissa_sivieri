# Evidências — Fase 3: carga e idempotência

## Código

Em `etl/carga.py`, `carregar_dados` aplica UPSERTs parametrizados (`INSERT ... ON CONFLICT ... DO UPDATE`) por `cursor.executemany`, dentro de uma transação e na ordem `produtos`, `clientes`, `pedidos`, `itens_pedido`. A reconciliação é executada antes do commit; se houver divergência, a exceção cancela a transação.

## Teste automatizado

`tests/test_reconciliacao.py::test_idempotencia_da_carga_mantem_contagens` chama `carregar_dados` duas vezes com os mesmos dados e compara as contagens retornadas. O teste grava no PostgreSQL local configurado, executa dois UPSERTs e não limpa as tabelas; use apenas o banco de desenvolvimento do projeto. Os números esperados são valores de referência do desafio. O teste passou na execução completa da suíte: **13 passed in 0.48s**.

## Duas execuções manuais

Comando usado nas duas execuções, sem limpar as tabelas:

```bash
python3 -m etl.main --carregar
```

O progresso página a página foi omitido. A tabela abaixo é um resumo das contagens reportadas ao final de cada execução, não uma transcrição literal do terminal:

| Tabela | Após a 1ª carga | Após a 2ª carga |
|---|---:|---:|
| `clientes` | 1.000 | 1.000 |
| `produtos` | 12 | 12 |
| `pedidos` | 5.000 | 5.000 |
| `itens_pedido` | 12.455 | 12.455 |

As duas execuções concluíram a reconciliação e confirmaram a transação.

## Conferência independente no `psql`

Após uma execução bem-sucedida em 22/11/2026 às 19:16, um `SELECT COUNT(*)` em cada tabela retornou a saída literal:

```text
    tabela    | registros
--------------+-----------
 clientes     |      1000
 produtos     |        12
 pedidos      |      5000
 itens_pedido |     12455
(4 rows)
```
