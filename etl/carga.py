"""Carga transacional dos dados transformados no PostgreSQL."""

import logging
import os
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Tuple

import psycopg

from etl.transformacao import converter_valor_monetario


logger = logging.getLogger(__name__)


def _parametros_conexao() -> Dict[str, Any]:
    """Lê a configuração do PostgreSQL do ambiente, sem credenciais no código."""
    parametros = {
        "host": os.environ.get("VERDEJAR_DB_HOST", "localhost"),
        "port": int(os.environ.get("VERDEJAR_DB_PORT", "5432")),
        "dbname": os.environ.get("VERDEJAR_DB_NAME", "verdejar"),
        "user": os.environ.get("VERDEJAR_DB_USER", "postgres"),
    }
    senha = os.environ.get("VERDEJAR_DB_PASSWORD")
    if senha:
        parametros["password"] = senha
    # Sem a variável, libpq/Psycopg pode usar ~/.pgpass ou PGPASSFILE.
    # Isso evita exigir senha no ambiente quando o usuário já configurou o arquivo.
    return parametros


def _data_cadastro(valor: Any, cliente_id: Any) -> date:
    """Converte cadastro_em, que chega do JSON no formato ISO, para date."""
    if isinstance(valor, date):
        return valor
    if not isinstance(valor, str):
        raise TypeError(f"cadastro_em inválido para o cliente {cliente_id!r}")
    try:
        return date.fromisoformat(valor)
    except ValueError as erro:
        raise ValueError(
            f"cadastro_em inválido para o cliente {cliente_id!r}: {valor!r}"
        ) from erro


def _linhas_produtos(produtos: Iterable[Dict[str, Any]]) -> List[Tuple[Any, ...]]:
    return [
        (
            int(produto["produto_id"]),
            produto["nome"],
            produto["categoria"],
            converter_valor_monetario(produto["preco_base"]),
        )
        for produto in produtos
    ]


def _linhas_clientes(clientes: Iterable[Dict[str, Any]]) -> List[Tuple[Any, ...]]:
    return [
        (
            int(cliente["id"]),
            cliente["nome"],
            cliente["email"],
            cliente["cidade"],
            cliente["estado"],
            _data_cadastro(cliente["cadastro_em"], cliente["id"]),
        )
        for cliente in clientes
    ]


def _linhas_pedidos(pedidos: Iterable[Dict[str, Any]]) -> List[Tuple[Any, ...]]:
    return [
        (
            int(pedido["id"]),
            int(pedido["cliente_id"]),
            pedido["data_pedido"],
            pedido["status"],
            pedido["valor_total"],
            pedido["valor_itens"],
            pedido["divergente"],
        )
        for pedido in pedidos
    ]


def _linhas_itens(pedidos: Iterable[Dict[str, Any]]) -> List[Tuple[Any, ...]]:
    linhas = []
    for pedido in pedidos:
        for linha, item in enumerate(pedido["itens"], start=1):
            linhas.append(
                (
                    int(pedido["id"]),
                    linha,
                    int(item["produto_id"]),
                    int(item["quantidade"]),
                    converter_valor_monetario(item["preco_unitario"]),
                )
            )
    return linhas


class ErroReconciliacao(ValueError):
    """Indica divergências entre contagens e valores da origem e destino."""


def reconciliar_dados(dados: Dict[str, Any], cursor: Any) -> Dict[str, Any]:
    """Compara contagens, divergências e soma de itens entre origem e destino."""
    pedidos_origem = dados["pedidos"]
    contagens_origem = {
        "clientes": len(dados["clientes"]),
        "produtos": len(dados["produtos"]),
        "pedidos": len(pedidos_origem),
        "itens_pedido": sum(len(pedido["itens"]) for pedido in pedidos_origem),
    }
    divergentes_origem = sum(
        1 for pedido in pedidos_origem if pedido["divergente"]
    )
    soma_origem = sum(
        (Decimal(str(pedido["valor_itens"])) for pedido in pedidos_origem),
        Decimal("0.00"),
    )

    cursor.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM clientes),
            (SELECT COUNT(*) FROM produtos),
            (SELECT COUNT(*) FROM pedidos),
            (SELECT COUNT(*) FROM itens_pedido),
            (SELECT COUNT(*) FROM pedidos WHERE divergente IS TRUE),
            (SELECT COALESCE(SUM(valor_itens), 0.00) FROM pedidos)
        """
    )
    (
        clientes_destino,
        produtos_destino,
        pedidos_destino,
        itens_destino,
        divergentes_destino,
        soma_destino,
    ) = cursor.fetchone()
    contagens_destino = {
        "clientes": clientes_destino,
        "produtos": produtos_destino,
        "pedidos": pedidos_destino,
        "itens_pedido": itens_destino,
    }
    soma_destino = Decimal(str(soma_destino))
    diferenca = abs(soma_origem - soma_destino)

    erros = [
        f"{tabela}: origem={contagem_origem}, destino={contagens_destino[tabela]}"
        for tabela, contagem_origem in contagens_origem.items()
        if contagem_origem != contagens_destino[tabela]
    ]
    if divergentes_origem != divergentes_destino:
        erros.append(
            "pedidos_divergentes: "
            f"origem={divergentes_origem}, destino={divergentes_destino}"
        )
    if diferenca > Decimal("0.01"):
        erros.append(
            f"soma_valor_itens: origem={soma_origem}, destino={soma_destino}, "
            f"diferença={diferenca}; tolerância=0.01"
        )
    if erros:
        raise ErroReconciliacao("; ".join(erros))

    return {
        "contagens_origem": contagens_origem,
        "contagens_destino": contagens_destino,
        "pedidos_divergentes_origem": divergentes_origem,
        "pedidos_divergentes_destino": divergentes_destino,
        "soma_valor_itens_origem": soma_origem,
        "soma_valor_itens_destino": soma_destino,
        "diferenca_valor_itens": diferenca,
    }


def carregar_dados(dados: Dict[str, Any]) -> Dict[str, int]:
    """Aplica UPSERTs parametrizados em uma transação única."""
    linhas_produtos = _linhas_produtos(dados["produtos"])
    linhas_clientes = _linhas_clientes(dados["clientes"])
    linhas_pedidos = _linhas_pedidos(dados["pedidos"])
    linhas_itens = _linhas_itens(dados["pedidos"])

    sql_produtos = """
        INSERT INTO produtos (produto_id, nome, categoria, preco_base)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (produto_id) DO UPDATE SET
            nome = EXCLUDED.nome,
            categoria = EXCLUDED.categoria,
            preco_base = EXCLUDED.preco_base
    """
    sql_clientes = """
        INSERT INTO clientes (id, nome, email, cidade, estado, cadastro_em)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            nome = EXCLUDED.nome,
            email = EXCLUDED.email,
            cidade = EXCLUDED.cidade,
            estado = EXCLUDED.estado,
            cadastro_em = EXCLUDED.cadastro_em
    """
    sql_pedidos = """
        INSERT INTO pedidos (
            id, cliente_id, data_pedido, status, valor_total, valor_itens, divergente
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            cliente_id = EXCLUDED.cliente_id,
            data_pedido = EXCLUDED.data_pedido,
            status = EXCLUDED.status,
            valor_total = EXCLUDED.valor_total,
            valor_itens = EXCLUDED.valor_itens,
            divergente = EXCLUDED.divergente
    """
    sql_itens = """
        INSERT INTO itens_pedido (
            pedido_id, linha, produto_id, quantidade, preco_unitario
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (pedido_id, linha) DO UPDATE SET
            produto_id = EXCLUDED.produto_id,
            quantidade = EXCLUDED.quantidade,
            preco_unitario = EXCLUDED.preco_unitario
    """

    parametros = _parametros_conexao()
    with psycopg.connect(**parametros) as conexao:
        with conexao.cursor() as cursor:
            cursor.executemany(sql_produtos, linhas_produtos)
            cursor.executemany(sql_clientes, linhas_clientes)
            cursor.executemany(sql_pedidos, linhas_pedidos)
            cursor.executemany(sql_itens, linhas_itens)

            reconciliacao = reconciliar_dados(dados, cursor)
            logger.info(
                "reconciliacao: clientes=%s produtos=%s pedidos_origem=%s "
                "pedidos_destino=%s itens_origem=%s itens_destino=%s "
                "divergentes_origem=%s divergentes_destino=%s "
                "soma_valor_itens_origem=%.2f soma_valor_itens_destino=%.2f "
                "diferenca=%.2f",
                reconciliacao["contagens_origem"]["clientes"],
                reconciliacao["contagens_origem"]["produtos"],
                reconciliacao["contagens_origem"]["pedidos"],
                reconciliacao["contagens_destino"]["pedidos"],
                reconciliacao["contagens_origem"]["itens_pedido"],
                reconciliacao["contagens_destino"]["itens_pedido"],
                reconciliacao["pedidos_divergentes_origem"],
                reconciliacao["pedidos_divergentes_destino"],
                reconciliacao["soma_valor_itens_origem"],
                reconciliacao["soma_valor_itens_destino"],
                reconciliacao["diferenca_valor_itens"],
            )
            contagens = reconciliacao["contagens_destino"]

    logger.info("UPSERT concluído e confirmado na transação: %s", contagens)
    return contagens
