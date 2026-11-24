"""Funções de extração da API Verdejar."""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union

import requests


class ErroExtracao(RuntimeError):
    """Indica falha de comunicação ou resposta inválida da API."""


def buscar_pagina(
    recurso: str,
    pagina: int = 1,
    tamanho_pagina: int = 50,
    base_url: str = "http://127.0.0.1:8000",
    timeout: int = 10,
) -> Dict[str, Any]:
    """Busca uma página de clientes ou pedidos e valida sua estrutura."""
    if recurso not in {"clientes", "pedidos"}:
        raise ValueError("recurso deve ser 'clientes' ou 'pedidos'")
    if pagina < 1:
        raise ValueError("pagina deve ser maior ou igual a 1")
    if not 1 <= tamanho_pagina <= 200:
        raise ValueError("tamanho_pagina deve estar entre 1 e 200")

    url = f"{base_url.rstrip('/')}/{recurso}"
    parametros = {"page": pagina, "page_size": tamanho_pagina}

    try:
        resposta = requests.get(url, params=parametros, timeout=timeout)
        resposta.raise_for_status()
    except requests.RequestException as erro:
        raise ErroExtracao(
            f"Falha ao buscar {recurso}, página {pagina}: {erro}"
        ) from erro

    try:
        dados = resposta.json()
    except ValueError as erro:
        raise ErroExtracao(
            f"A API retornou conteúdo que não é JSON para {recurso}, página {pagina}"
        ) from erro

    campos_obrigatorios = {
        "page",
        "page_size",
        "total_items",
        "total_pages",
        "items",
    }
    if not isinstance(dados, dict) or not campos_obrigatorios.issubset(dados):
        raise ErroExtracao(
            f"Resposta inválida para {recurso}, página {pagina}: "
            "faltam campos de paginação"
        )
    if dados["page"] != pagina or dados["page_size"] != tamanho_pagina:
        raise ErroExtracao(
            f"A API respondeu com página/tamanho diferentes do pedido: "
            f"page={dados['page']}, page_size={dados['page_size']}"
        )
    if not isinstance(dados["items"], list):
        raise ErroExtracao("O campo 'items' da resposta não é uma lista")

    return dados


def extrair_todas_paginas(
    recurso: str,
    tamanho_pagina: int = 50,
    base_url: str = "http://127.0.0.1:8000",
    timeout: int = 10,
) -> List[Dict[str, Any]]:
    """Busca todas as páginas de um recurso sem transformar os registros."""
    logger = logging.getLogger(__name__)

    primeira = buscar_pagina(
        recurso, 1, tamanho_pagina, base_url=base_url, timeout=timeout
    )
    total_itens = primeira["total_items"]
    total_paginas = primeira["total_pages"]

    if (
        not isinstance(total_itens, int)
        or isinstance(total_itens, bool)
        or total_itens < 0
        or not isinstance(total_paginas, int)
        or isinstance(total_paginas, bool)
        or total_paginas < 1
    ):
        raise ErroExtracao("A API informou totais inválidos na paginação")

    paginas_esperadas = (total_itens + tamanho_pagina - 1) // tamanho_pagina
    if total_paginas != paginas_esperadas:
        raise ErroExtracao(
            f"Paginação inconsistente: a API informou {total_paginas} páginas, "
            f"mas {total_itens} registros com páginas de {tamanho_pagina} "
            f"deveriam ocupar {paginas_esperadas} páginas"
        )

    registros = list(primeira["items"])
    logger.info(
        "Extraída página %d/%d de %s: %d registros",
        1, total_paginas, recurso, len(primeira["items"]),
    )

    for pagina in range(2, total_paginas + 1):
        resposta = buscar_pagina(
            recurso, pagina, tamanho_pagina, base_url=base_url, timeout=timeout
        )
        if (
            resposta["total_items"] != total_itens
            or resposta["total_pages"] != total_paginas
        ):
            raise ErroExtracao(
                f"Os totais de paginação mudaram durante a extração de {recurso}"
            )

        registros.extend(resposta["items"])
        logger.info(
            "Extraída página %d/%d de %s: %d registros",
            pagina, total_paginas, recurso, len(resposta["items"]),
        )

    if len(registros) != total_itens:
        raise ErroExtracao(
            f"Extração incompleta de {recurso}: esperados {total_itens} registros, "
            f"recebidos {len(registros)}"
        )

    logger.info(
        "Extração de %s concluída: %d páginas, %d registros",
        recurso, total_paginas, len(registros),
    )
    return registros


def salvar_json_bruto(
    recurso: str,
    registros: List[Dict[str, Any]],
    pasta_saida: Union[str, Path] = Path(__file__).resolve().parent.parent / "brutos",
) -> Path:
    """Salva os registros recebidos sem transformação, em um arquivo novo."""
    if recurso not in {"clientes", "pedidos"}:
        raise ValueError("recurso deve ser 'clientes' ou 'pedidos'")
    if not isinstance(registros, list):
        raise TypeError("registros deve ser uma lista de dicionários")

    diretorio = Path(pasta_saida)
    diretorio.mkdir(parents=True, exist_ok=True)

    identificador = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%f%z")
    caminho = diretorio / f"{recurso}_{identificador}.json"

    with caminho.open("x", encoding="utf-8") as arquivo:
        json.dump(registros, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")

    logging.getLogger(__name__).info(
        "Dados brutos de %s salvos em %s (%d registros)",
        recurso, caminho, len(registros),
    )
    return caminho


def ler_produtos_csv(
    caminho_csv: Union[str, Path] = (
        Path(__file__).resolve().parent.parent / "insumos" / "dados" / "produtos.csv"
    ),
) -> List[Dict[str, str]]:
    """Lê produtos.csv e mantém os valores originais como texto."""
    arquivo_csv = Path(caminho_csv)
    campos_obrigatorios = {"produto_id", "nome", "categoria", "preco_base"}

    with arquivo_csv.open("r", encoding="utf-8", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        if leitor.fieldnames is None:
            raise ErroExtracao(f"O CSV de produtos está vazio: {arquivo_csv}")

        campos_ausentes = campos_obrigatorios - set(leitor.fieldnames)
        if campos_ausentes:
            raise ErroExtracao(
                "Cabeçalho inválido no CSV de produtos; faltam os campos: "
                + ", ".join(sorted(campos_ausentes))
            )

        produtos = []
        for numero_linha, produto in enumerate(leitor, start=2):
            if None in produto or any(valor is None for valor in produto.values()):
                raise ErroExtracao(
                    f"Linha {numero_linha} incompleta ou com colunas extras "
                    f"no CSV de produtos: {arquivo_csv}"
                )
            produtos.append(produto)

    logging.getLogger(__name__).info(
        "Lidos %d produtos de %s", len(produtos), arquivo_csv
    )
    return produtos
