"""Funções pequenas de transformação e validação dos dados Verdejar."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Tuple, Union


def contar_emails_ausentes(clientes: Iterable[Dict[str, Any]]) -> int:
    """Conta clientes com email explicitamente nulo, sem alterar os registros."""
    total = 0

    for numero, cliente in enumerate(clientes, start=1):
        if not isinstance(cliente, dict):
            raise TypeError(f"O cliente da posição {numero} não é um dicionário")
        if "email" not in cliente:
            raise ValueError(f"O cliente da posição {numero} não tem o campo 'email'")
        if cliente["email"] is None:
            total += 1

    return total


class EstadoInvalidoError(ValueError):
    """Reúne clientes cujo estado não pode ser padronizado."""

    def __init__(self, problemas: List[str]) -> None:
        self.problemas = problemas
        detalhes = "\n".join(f"- {problema}" for problema in problemas)
        super().__init__(
            f"Estados inválidos encontrados ({len(problemas)}):\n{detalhes}"
        )


def padronizar_estados(
    clientes: Iterable[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """Devolve cópias com estado em maiúsculas e reúne estados inválidos."""
    clientes_padronizados = []
    total_corrigidos = 0
    problemas = []

    for numero, cliente in enumerate(clientes, start=1):
        if not isinstance(cliente, dict):
            problemas.append(
                f"posição {numero}: registro de cliente não é um dicionário"
            )
            continue
        if "estado" not in cliente:
            problemas.append(
                f"cliente ID {cliente.get('id', '<sem ID>')!r}, posição {numero}: "
                "campo 'estado' ausente"
            )
            continue

        estado = cliente["estado"]
        if (
            not isinstance(estado, str)
            or len(estado) != 2
            or not estado.isascii()
            or not estado.isalpha()
        ):
            problemas.append(
                f"cliente ID {cliente.get('id', '<sem ID>')!r}, posição {numero}: "
                f"estado inválido {estado!r}; esperada sigla de 2 letras ASCII"
            )
            continue

        estado_padronizado = estado.upper()
        cliente_copiado = cliente.copy()
        cliente_copiado["estado"] = estado_padronizado
        clientes_padronizados.append(cliente_copiado)

        if estado_padronizado != estado:
            total_corrigidos += 1

    if problemas:
        raise EstadoInvalidoError(problemas)

    return clientes_padronizados, total_corrigidos


def converter_data_pedido(valor: str) -> date:
    """Converte uma data ISO ou DD/MM/AAAA para datetime.date."""
    if not isinstance(valor, str):
        raise TypeError("A data do pedido deve ser informada como texto")

    data_texto = valor.strip()
    formatos = ("%Y-%m-%d", "%d/%m/%Y")

    for formato in formatos:
        try:
            return datetime.strptime(data_texto, formato).date()
        except ValueError:
            continue

    raise ValueError(
        f"Data inválida: {valor!r}. Formatos aceitos: AAAA-MM-DD ou DD/MM/AAAA"
    )


def converter_datas_pedidos(
    pedidos: Iterable[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """Converte datas dos pedidos e conta as que vieram em DD/MM/AAAA."""
    pedidos_convertidos = []
    total_formato_dia_mes_ano = 0

    for numero, pedido in enumerate(pedidos, start=1):
        if not isinstance(pedido, dict):
            raise TypeError(f"O pedido da posição {numero} não é um dicionário")
        if "data_pedido" not in pedido:
            raise ValueError(
                f"O pedido da posição {numero} não tem o campo 'data_pedido'"
            )

        data_original = pedido["data_pedido"]
        data_convertida = converter_data_pedido(data_original)
        pedido_copiado = pedido.copy()
        pedido_copiado["data_pedido"] = data_convertida
        pedidos_convertidos.append(pedido_copiado)

        if "/" in data_original:
            total_formato_dia_mes_ano += 1

    return pedidos_convertidos, total_formato_dia_mes_ano


def converter_valor_monetario(valor: Union[str, int, float, Decimal]) -> Decimal:
    """Converte valor decimal com ponto ou vírgula para Decimal de duas casas."""
    if isinstance(valor, bool):
        # bool é subclasse de int em Python; sem este teste, True viraria 1.00
        raise TypeError("Valor monetário não pode ser booleano")

    if isinstance(valor, str):
        texto = valor.strip()
        # "1.234,56" tem ponto e vírgula: não dá para saber qual é o decimal
        if "," in texto and "." in texto:
            raise ValueError(
                f"Formato monetário ambíguo: {valor!r}; use ponto ou vírgula decimal"
            )
        texto = texto.replace(",", ".")  # "125,84" -> "125.84"
    elif isinstance(valor, (int, float, Decimal)):
        # str() antes de Decimal: Decimal(4.3) carrega o erro binário do float,
        # Decimal("4.3") não
        texto = str(valor)
    else:
        raise TypeError(f"Tipo não aceito para valor monetário: {type(valor).__name__}")

    try:
        valor_decimal = Decimal(texto)
    except InvalidOperation as erro:
        raise ValueError(f"Valor monetário inválido: {valor!r}") from erro

    if not valor_decimal.is_finite():
        raise ValueError(f"Valor monetário não é finito: {valor!r}")
    # O destino usa NUMERIC(x,2); valores com mais casas serão arredondados aqui.
    # ROUND_HALF_UP: por exemplo, 0,005 vira 0,01.
    return valor_decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def converter_valores_pedidos(
    pedidos: Iterable[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """Converte valor_total para Decimal e conta textos com vírgula decimal."""
    pedidos_convertidos = []
    total_textos_com_virgula = 0

    for numero, pedido in enumerate(pedidos, start=1):
        if not isinstance(pedido, dict):
            raise TypeError(f"O pedido da posição {numero} não é um dicionário")
        if "valor_total" not in pedido:
            raise ValueError(
                f"O pedido da posição {numero} não tem o campo 'valor_total'"
            )

        valor_original = pedido["valor_total"]
        valor_convertido = converter_valor_monetario(valor_original)
        pedido_copiado = pedido.copy()
        pedido_copiado["valor_total"] = valor_convertido
        pedidos_convertidos.append(pedido_copiado)

        if isinstance(valor_original, str) and "," in valor_original:
            total_textos_com_virgula += 1

    return pedidos_convertidos, total_textos_com_virgula


class ConflitoPedidoError(ValueError):
    """Reúne IDs de pedido que reapareceram com conteúdo diferente."""

    def __init__(self, conflitos: List[Dict[str, Any]]) -> None:
        self.conflitos = conflitos
        detalhes = []
        for conflito in conflitos:
            campos = ", ".join(conflito["campos_diferentes"]) or "conteúdo diferente"
            detalhes.append(
                f"- ID {conflito['id']!r}: posições "
                f"{conflito['posicao_primeira']} e {conflito['posicao_conflito']}; "
                f"campos diferentes: {campos}"
            )
        super().__init__(
            f"Conflitos de pedidos encontrados ({len(conflitos)}):\n"
            + "\n".join(detalhes)
        )


def remover_pedidos_duplicados(
    pedidos: Iterable[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """Mantém a primeira ocorrência, conta repetições e reúne conflitos."""
    primeiros_por_id = {}
    primeiras_posicoes = {}
    pedidos_unicos = []
    total_duplicados = 0
    conflitos = []

    for numero, pedido in enumerate(pedidos, start=1):
        if not isinstance(pedido, dict):
            raise TypeError(f"O pedido da posição {numero} não é um dicionário")
        if "id" not in pedido or pedido["id"] is None:
            raise ValueError(f"O pedido da posição {numero} não tem um ID válido")

        pedido_id = pedido["id"]
        try:
            ja_existe = pedido_id in primeiros_por_id
        except TypeError as erro:
            raise ValueError(
                f"ID de pedido não pode ser usado como chave: {pedido_id!r}"
            ) from erro

        if not ja_existe:
            # primeira ocorrência do ID: guarda o pedido e a posição
            primeiros_por_id[pedido_id] = pedido
            primeiras_posicoes[pedido_id] = numero
            pedidos_unicos.append(pedido)
        elif pedido == primeiros_por_id[pedido_id]:
            # mesmo ID e conteúdo idêntico: duplicata, só conta
            total_duplicados += 1
        else:
            # mesmo ID com conteúdo diferente: conflito, não pode ser descartado
            # em silêncio; guarda quais campos diferem
            primeiro = primeiros_por_id[pedido_id]
            chaves = set(primeiro) | set(pedido)
            campos_diferentes = sorted(
                str(campo) for campo in chaves
                if (
                    campo not in primeiro
                    or campo not in pedido
                    or primeiro.get(campo) != pedido.get(campo)
                )
            )
            conflitos.append({
                "id": pedido_id,
                "posicao_primeira": primeiras_posicoes[pedido_id],
                "posicao_conflito": numero,
                "campos_diferentes": campos_diferentes,
            })
    # os conflitos são reunidos e levantados juntos, no fim do laço
    if conflitos:
        raise ConflitoPedidoError(conflitos)

    return pedidos_unicos, total_duplicados


def calcular_divergencias_financeiras(
    pedidos: Iterable[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """Calcula valor_itens e divergente sem substituir valor_total."""
    pedidos_calculados = []
    total_divergentes = 0
    tolerancia = Decimal("0.01")

    for numero, pedido in enumerate(pedidos, start=1):
        if not isinstance(pedido, dict):
            raise TypeError(f"O pedido da posição {numero} não é um dicionário")
        if "valor_total" not in pedido or "itens" not in pedido:
            raise ValueError(
                f"O pedido da posição {numero} precisa dos campos "
                "'valor_total' e 'itens'"
            )
        if not isinstance(pedido["itens"], list):
            raise TypeError(
                f"A lista de itens do pedido {pedido.get('id', numero)!r} "
                "é inválida"
            )

        valor_total = converter_valor_monetario(pedido["valor_total"])
        valor_itens = Decimal("0.00")

        for linha, item in enumerate(pedido["itens"], start=1):
            if not isinstance(item, dict):
                raise TypeError(
                    f"O item {linha} do pedido {pedido.get('id', numero)!r} "
                    "não é um dicionário"
                )
            if "quantidade" not in item or "preco_unitario" not in item:
                raise ValueError(
                    f"O item {linha} do pedido {pedido.get('id', numero)!r} "
                    "precisa dos campos 'quantidade' e 'preco_unitario'"
                )

            quantidade = item["quantidade"]
            if not isinstance(quantidade, int) or isinstance(quantidade, bool):
                raise TypeError(
                    f"A quantidade do item {linha} do pedido "
                    f"{pedido.get('id', numero)!r} deve ser um inteiro"
                )

            preco_unitario = converter_valor_monetario(item["preco_unitario"])
            # Decimal(int) * Decimal: nenhuma conta financeira passa por float
            valor_itens += Decimal(quantidade) * preco_unitario

        valor_itens = valor_itens.quantize(Decimal("0.01"))
        # diferença estritamente MAIOR que 0,01: exatamente 0,01 não é divergência
        divergente = abs(valor_total - valor_itens) > tolerancia

        pedido_copiado = pedido.copy()
        pedido_copiado["valor_itens"] = valor_itens
        pedido_copiado["divergente"] = divergente
        pedidos_calculados.append(pedido_copiado)

        if divergente:
            total_divergentes += 1

    return pedidos_calculados, total_divergentes
