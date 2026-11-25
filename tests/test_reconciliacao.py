"""Testes de reconciliação após a carga no PostgreSQL."""

import json
from decimal import Decimal
from pathlib import Path

import psycopg

from etl.carga import (
    _parametros_conexao,
    carregar_dados,
    reconciliar_dados,
)
from etl.extracao import ler_produtos_csv
from etl.transformacao import (
    calcular_divergencias_financeiras,
    converter_datas_pedidos,
    converter_valores_pedidos,
    padronizar_estados,
    remover_pedidos_duplicados,
)


RAIZ_PROJETO = Path(__file__).resolve().parents[1]


def _ler_snapshot(recurso: str):
    arquivos = sorted((RAIZ_PROJETO / "brutos").glob(f"{recurso}_*.json"))
    if not arquivos:
        raise AssertionError(f"Não há snapshot bruto de {recurso} em brutos/")
    return json.loads(arquivos[-1].read_text(encoding="utf-8"))


def _dados_origem_transformados():
    """Monta os dados da carga a partir dos snapshots, sem chamar a API."""
    clientes_brutos = _ler_snapshot("clientes")
    pedidos_brutos = _ler_snapshot("pedidos")
    clientes, _ = padronizar_estados(clientes_brutos)
    pedidos_unicos, _ = remover_pedidos_duplicados(pedidos_brutos)
    pedidos_com_datas, _ = converter_datas_pedidos(pedidos_unicos)
    pedidos_com_valores, _ = converter_valores_pedidos(pedidos_com_datas)
    pedidos, _ = calcular_divergencias_financeiras(pedidos_com_valores)
    return {
        "clientes": clientes,
        "produtos": ler_produtos_csv(),
        "pedidos": pedidos,
    }


def _consulta_sql(nome: str) -> str:
    """Lê uma consulta identificada por comentário no arquivo SQL do projeto."""
    caminho = RAIZ_PROJETO / "consultas_validacao.sql"
    texto = caminho.read_text(encoding="utf-8")
    marcador = f"-- QUERY: {nome}"
    inicio_marcador = texto.find(marcador)
    if inicio_marcador < 0:
        raise AssertionError(f"Consulta {nome!r} não encontrada em {caminho}")

    inicio = texto.find("\n", inicio_marcador) + 1
    proxima = texto.find("\n-- QUERY:", inicio)
    trecho = texto[inicio:] if proxima < 0 else texto[inicio:proxima]
    return trecho.strip().rstrip(";").strip()


def test_reconciliacao_contagens_e_totais_apos_carga():
    dados = _dados_origem_transformados()

    with psycopg.connect(**_parametros_conexao()) as conexao:
        with conexao.cursor() as cursor:
            resultado = reconciliar_dados(dados, cursor)

    # Valores de referência do desafio.
    contagens_esperadas = {
        "clientes": 1000,
        "produtos": 12,
        "pedidos": 5000,
        "itens_pedido": 12455,
    }
    assert resultado["contagens_origem"] == contagens_esperadas
    assert resultado["contagens_destino"] == contagens_esperadas
    assert resultado["pedidos_divergentes_origem"] == 238
    assert resultado["pedidos_divergentes_destino"] == 238
    assert resultado["diferenca_valor_itens"] <= Decimal("0.01")
    assert resultado["soma_valor_itens_origem"] == Decimal("311228.75")
    assert resultado["soma_valor_itens_destino"] == Decimal("311228.75")


def test_idempotencia_da_carga_mantem_contagens():
    # Este teste grava no PostgreSQL configurado: faz dois UPSERTs e não limpa
    # as tabelas. Execute apenas no banco local de desenvolvimento do projeto.
    dados = _dados_origem_transformados()

    primeira_carga = carregar_dados(dados)
    segunda_carga = carregar_dados(dados)

    # Valores de referência do desafio.
    contagens_esperadas = {
        "produtos": 12,
        "clientes": 1000,
        "pedidos": 5000,
        "itens_pedido": 12455,
    }
    assert primeira_carga == contagens_esperadas
    assert segunda_carga == primeira_carga


def test_soma_vendas_mensais_bate_com_soma_geral():
    consulta_mensal = _consulta_sql("vendas_por_mes")

    with psycopg.connect(**_parametros_conexao()) as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(consulta_mensal)
            totais_mensais = [linha[1] for linha in cursor.fetchall()]
            cursor.execute("SELECT COALESCE(SUM(valor_total), 0.00) FROM pedidos")
            total_geral = cursor.fetchone()[0]

    soma_meses = sum(totais_mensais, Decimal("0.00"))
    assert soma_meses == total_geral
