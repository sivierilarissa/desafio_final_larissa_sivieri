-- DEFINICAO DE "VENDAS"
-- Vendas = soma de pedidos.valor_total, informado pela origem e normalizado para NUMERIC.
-- valor_itens serve para detectar divergencias; nao e usado como total de vendas.
-- Pedidos divergentes entram na soma, pois valor_total foi preservado.
-- Sem filtro de status: o resultado e o valor bruto de todos os pedidos unicos carregados, nao uma receita liquida de cancelamentos.

-- QUERY: vendas_por_mes
-- Caminho A: PostgreSQL. Soma do valor_total por mes.
SELECT
    DATE_TRUNC('month', data_pedido)::date AS mes,
    SUM(valor_total)::NUMERIC(14,2) AS total_vendas
FROM pedidos
GROUP BY DATE_TRUNC('month', data_pedido)
ORDER BY mes;

-- QUERY: conferencia_soma_vendas_mes
-- TESTE: a soma mensal deve ser igual a soma geral de valor_total em pedidos.
-- Se "confere" for falso, revise as datas e a consulta mensal.
WITH mensal AS (
    SELECT DATE_TRUNC('month', data_pedido)::date AS mes,
           SUM(valor_total) AS total_vendas
    FROM pedidos
    GROUP BY DATE_TRUNC('month', data_pedido)
),
totais AS (
    SELECT
        COALESCE((SELECT SUM(total_vendas) FROM mensal), 0.00) AS soma_mensal,
        COALESCE((SELECT SUM(valor_total) FROM pedidos), 0.00) AS soma_geral
)
SELECT
    soma_mensal,
    soma_geral,
    soma_mensal - soma_geral AS diferenca,
    soma_mensal = soma_geral AS confere
FROM totais;

-- QUERY: pedidos_por_estado
SELECT
    c.estado,
    COUNT(*) AS quantidade_pedidos
FROM pedidos AS p
JOIN clientes AS c ON c.id = p.cliente_id
GROUP BY c.estado
ORDER BY c.estado;

-- QUERY: pedidos_divergentes
SELECT
    id AS pedido_id,
    cliente_id,
    data_pedido,
    valor_total,
    valor_itens,
    ABS(valor_total - valor_itens)::NUMERIC(12,2) AS diferenca
FROM pedidos
WHERE divergente IS TRUE
ORDER BY id;