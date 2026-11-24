"""Orquestra o ETL Verdejar: extração, transformação e, com --carregar, carga."""

import argparse
import logging
from decimal import Decimal
from typing import Any, Dict

from etl.extracao import (
    ErroExtracao,
    extrair_todas_paginas,
    ler_produtos_csv,
    salvar_json_bruto,
)
from etl.transformacao import (
    ConflitoPedidoError,
    EstadoInvalidoError,
    calcular_divergencias_financeiras,
    contar_emails_ausentes,
    converter_datas_pedidos,
    converter_valores_pedidos,
    padronizar_estados,
    remover_pedidos_duplicados,
)


logger = logging.getLogger(__name__)


def executar_etl() -> Dict[str, Any]:
    """Extrai e transforma clientes, produtos e pedidos, sem gravar no banco."""
    clientes_brutos = extrair_todas_paginas("clientes")
    arquivo_clientes = salvar_json_bruto("clientes", clientes_brutos)

    pedidos_brutos = extrair_todas_paginas("pedidos")
    arquivo_pedidos = salvar_json_bruto("pedidos", pedidos_brutos)

    produtos = ler_produtos_csv()

    emails_ausentes = contar_emails_ausentes(clientes_brutos)
    clientes, estados_corrigidos = padronizar_estados(clientes_brutos)

    # As métricas de datas, valores e divergências devem usar pedidos únicos.
    pedidos_unicos, duplicados = remover_pedidos_duplicados(pedidos_brutos)
    pedidos_com_datas, datas_ddmmaaaa = converter_datas_pedidos(pedidos_unicos)
    pedidos_com_valores, valores_com_virgula = converter_valores_pedidos(
        pedidos_com_datas
    )
    pedidos, divergentes = calcular_divergencias_financeiras(pedidos_com_valores)

    total_itens = sum(len(pedido["itens"]) for pedido in pedidos)
    soma_valor_total = sum(
        (pedido["valor_total"] for pedido in pedidos), Decimal("0.00")
    )
    soma_valor_itens = sum(
        (pedido["valor_itens"] for pedido in pedidos), Decimal("0.00")
    )

    metricas = {
        "clientes": len(clientes),
        "emails_ausentes": emails_ausentes,
        "estados_corrigidos": estados_corrigidos,
        "produtos": len(produtos),
        "pedidos_recebidos": len(pedidos_brutos),
        "pedidos_unicos": len(pedidos_unicos),
        "pedidos_duplicados": duplicados,
        "datas_ddmmaaaa": datas_ddmmaaaa,
        "valores_com_virgula": valores_com_virgula,
        "itens_pedido": total_itens,
        "pedidos_divergentes": divergentes,
        "soma_valor_total": soma_valor_total,
        "soma_valor_itens": soma_valor_itens,
        "diferenca_financeira": soma_valor_total - soma_valor_itens,
    }

    logger.info("Cópia bruta de clientes: %s", arquivo_clientes)
    logger.info("Cópia bruta de pedidos: %s", arquivo_pedidos)
    logger.info("Resumo dos dados extraídos e transformados:")
    for nome, valor in metricas.items():
        logger.info("  %s: %s", nome, valor)
    logger.info("Extração e transformação concluídas.")

    return {
        "clientes": clientes,
        "produtos": produtos,
        "pedidos": pedidos,
        "metricas": metricas,
        "arquivos_brutos": {
            "clientes": arquivo_clientes,
            "pedidos": arquivo_pedidos,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL do Projeto Verdejar")
    parser.add_argument(
        "--carregar",
        action="store_true",
        help="grava no PostgreSQL usando UPSERT",
    )
    argumentos = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        dados = executar_etl()
    except (ErroExtracao, ConflitoPedidoError, EstadoInvalidoError) as erro:
        logger.error("ETL interrompido: %s", erro)
        raise SystemExit(1) from None

    if argumentos.carregar:
        from etl.carga import ErroReconciliacao, carregar_dados

        try:
            contagens = carregar_dados(dados)
        except ErroReconciliacao as erro:
            logger.error("ETL interrompido: %s", erro)
            raise SystemExit(1) from None
        logger.info("Contagens no PostgreSQL após a carga: %s", contagens)
    else:
        logger.info("Nenhum dado foi carregado no banco.")


if __name__ == "__main__":
    main()
