# Evidências — Fase 4: testes e reconciliação

## Testes automatizados

- `tests/test_transformacao.py`: 10 testes cobrindo A1–A6, estado inválido, data inexistente, conflito de duplicados e limite da tolerância financeira.
- `tests/test_reconciliacao.py`: 3 testes para contagens e valores após a carga, idempotência e soma mensal.

O teste de idempotência grava no PostgreSQL local configurado: executa dois UPSERTs, sem limpar as tabelas. Os números esperados são valores de referência do desafio; use apenas o banco de desenvolvimento do projeto.

Execução na raiz do projeto, após a carga, com a `.venv` ativa:

```text
(.venv) $ python -m pytest -v -p no:cacheprovider
============================= test session starts ==============================
platform darwin -- Python 3.14.10, pytest-8.4.2, pluggy-1.7.0 -- /Users/larissasivieri/Documents/Larissa/bootcamp_compass/desafio_final/.venv/bin/python
rootdir: /Users/larissasivieri/Documents/Larissa/bootcamp_compass/desafio_final
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

## Reconciliação após a carga

`etl/carga.py` compara os dados transformados com o PostgreSQL. A soma de `valor_itens` admite diferença máxima de R$ 0,01.

| Comparação | Origem | PostgreSQL | Resultado |
|---|---:|---:|---|
| Clientes | 1.000 | 1.000 | confere |
| Produtos | 12 | 12 | confere |
| Pedidos únicos | 5.000 | 5.000 | confere |
| Itens de pedido | 12.455 | 12.455 | confere |
| Pedidos divergentes | 238 | 238 | confere |
| Soma de `valor_itens` | R$ 311.228,75 | R$ 311.228,75 | diferença R$ 0,00 |

## Consultas de validação

`consultas_validacao.sql` contém as consultas de vendas mensais, pedidos por estado e pedidos divergentes. Resultados observados:

- **Vendas por mês:** soma mensal de `valor_total` = soma geral, ambas R$ 312.047,75; `confere = t`. O teste automatizado compara os valores com igualdade exata.
- **Pedidos por estado:** MG 476, PR 974, RS 1.543, SC 1.127 e SP 880; total 5.000.
- **Pedidos divergentes:** 238 linhas.
