"""Especificações das transformações para as armadilhas A1 a A6."""

from datetime import date
from decimal import Decimal

import pytest

from etl.transformacao import (
    ConflitoPedidoError,
    EstadoInvalidoError,
    calcular_divergencias_financeiras,
    contar_emails_ausentes,
    converter_data_pedido,
    converter_datas_pedidos,
    converter_valores_pedidos,
    padronizar_estados,
    remover_pedidos_duplicados,
)


def test_a1_conta_emails_ausentes_sem_alterar_clientes():
    clientes = [
        {"id": 1, "email": None},
        {"id": 2, "email": "ana@example.com"},
    ]

    resultado = contar_emails_ausentes(clientes)

    assert resultado == 1
    assert clientes[0]["email"] is None


def test_a2_padroniza_estado_em_maiusculas_e_conta_alteracoes():
    clientes = [
        {"id": 1, "estado": "mg"},
        {"id": 2, "estado": "SP"},
    ]

    resultado, corrigidos = padronizar_estados(clientes)

    assert [cliente["estado"] for cliente in resultado] == ["MG", "SP"]
    assert corrigidos == 1
    assert clientes[0]["estado"] == "mg"  # a entrada original é preservada


def test_a2_rejeita_estado_que_nao_seja_duas_letras_ascii():
    clientes = [
        {"id": 1, "estado": "1!"},
        {"id": 2, "estado": "éS"},
    ]

    with pytest.raises(EstadoInvalidoError) as erro:
        padronizar_estados(clientes)

    assert len(erro.value.problemas) == 2


def test_a3_converte_os_dois_formatos_de_data_e_conta_datas_com_barras():
    pedidos = [
        {"id": 1, "data_pedido": "2026-02-19"},
        {"id": 2, "data_pedido": "19/02/2026"},
    ]

    resultado, datas_com_barras = converter_datas_pedidos(pedidos)

    assert [pedido["data_pedido"] for pedido in resultado] == [
        date(2026, 2, 19),
        date(2026, 2, 19),
    ]
    assert datas_com_barras == 1
    assert pedidos[1]["data_pedido"] == "19/02/2026"


def test_a4_converte_valor_com_virgula_para_decimal_e_conta_ocorrencias():
    pedidos = [
        {"id": 1, "valor_total": "125,84"},
        {"id": 2, "valor_total": 94.34},
    ]

    resultado, valores_com_virgula = converter_valores_pedidos(pedidos)

    assert [pedido["valor_total"] for pedido in resultado] == [
        Decimal("125.84"),
        Decimal("94.34"),
    ]
    assert valores_com_virgula == 1
    assert pedidos[0]["valor_total"] == "125,84"


def test_a5_remove_repeticao_identica_e_conta_duplicados():
    pedido = {"id": 10, "status": "entregue"}
    pedidos = [pedido, pedido.copy(), {"id": 11, "status": "aberto"}]

    unicos, duplicados = remover_pedidos_duplicados(pedidos)

    assert unicos == [pedido, {"id": 11, "status": "aberto"}]
    assert duplicados == 1


def test_a6_calcula_soma_dos_itens_e_sinaliza_divergencia():
    pedidos = [
        {
            "id": 1,
            "valor_total": "10,00",
            "itens": [{"quantidade": 2, "preco_unitario": 5.00}],
        },
        {
            "id": 2,
            "valor_total": "11,00",
            "itens": [{"quantidade": 2, "preco_unitario": 5.00}],
        },
    ]

    resultado, divergentes = calcular_divergencias_financeiras(pedidos)

    assert [pedido["valor_itens"] for pedido in resultado] == [
        Decimal("10.00"),
        Decimal("10.00"),
    ]
    assert [pedido["divergente"] for pedido in resultado] == [False, True]
    assert divergentes == 1
    assert "valor_itens" not in pedidos[0]  # a entrada original é preservada


def test_a3_data_inexistente_gera_erro():
    with pytest.raises(ValueError):
        converter_data_pedido("31/02/2026")


def test_a5_mesmo_id_com_conteudo_diferente_sinaliza_conflito():
    pedidos = [
        {"id": 10, "status": "entregue"},
        {"id": 10, "status": "cancelado"},
    ]

    with pytest.raises(ConflitoPedidoError) as erro:
        remover_pedidos_duplicados(pedidos)

    assert erro.value.conflitos[0]["id"] == 10
    assert erro.value.conflitos[0]["campos_diferentes"] == ["status"]


def test_a6_limite_da_tolerancia_e_valor_total_preservado():
    itens = [{"quantidade": 2, "preco_unitario": 5.00}]
    pedidos = [
        {"id": 1, "valor_total": "10,01", "itens": itens},
        {"id": 2, "valor_total": "10,02", "itens": itens},
    ]

    resultado, divergentes = calcular_divergencias_financeiras(pedidos)

    assert [pedido["divergente"] for pedido in resultado] == [False, True]
    assert divergentes == 1
    assert resultado[1]["valor_total"] == "10,02"
