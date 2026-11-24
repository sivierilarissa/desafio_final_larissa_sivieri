# Contrato de dados — Projeto Verdejar

Formato das quatro tabelas PostgreSQL, conforme `insumos/schema.sql`, e regras aplicadas pelo ETL.

**Origem:** clientes e pedidos vêm da API local; produtos vêm de `insumos/dados/produtos.csv`. Os JSONs brutos são salvos localmente em `brutos/`, com data e hora no nome. Essa pasta está no `.gitignore`.

## Tabelas

| Tabela.campo | Tipo | Nulo? | Regra |
|---|---|---|---|
| `clientes.id` | INTEGER PK | Não | ID recebido da API |
| `clientes.nome`, `clientes.cidade` | TEXT | Não | Mantidos como recebidos |
| `clientes.email` | TEXT | Sim | `null` é preservado; não é preenchido |
| `clientes.estado` | CHAR(2) | Não | Exige duas letras ASCII e converte para maiúsculas; não valida a lista oficial de UFs |
| `clientes.cadastro_em` | DATE | Não | A API observada envia `AAAA-MM-DD`; convertido com `date.fromisoformat`; valor não conversível interrompe a carga |
| `produtos.produto_id` | INTEGER PK | Não | Do CSV, convertido para inteiro |
| `produtos.nome`, `produtos.categoria` | TEXT | Não | Mantidos como recebidos do CSV |
| `produtos.preco_base` | NUMERIC(10,2) | Não | Do CSV, convertido para `Decimal` com duas casas; os 12 valores atuais foram conferidos e não mudam ao arredondar |
| `pedidos.id` | INTEGER PK | Não | Duplicatas idênticas são reduzidas a uma; ID repetido com conteúdo diferente gera conflito e interrompe o ETL |
| `pedidos.cliente_id` | INTEGER FK | Não | Referencia `clientes.id` |
| `pedidos.data_pedido` | DATE | Não | Aceita `AAAA-MM-DD` e `DD/MM/AAAA`; data não conversível interrompe o ETL |
| `pedidos.status` | TEXT | Não | Mantido como recebido |
| `pedidos.valor_total` | NUMERIC(12,2) | Não | Quantia original preservada e convertida para `Decimal`; aceita ponto ou vírgula como separador decimal, não separador de milhar; se ambos aparecem, rejeita como ambíguo |
| `pedidos.valor_itens` | NUMERIC(12,2) | Não | Calculado pela soma de `quantidade × preco_unitario` |
| `pedidos.divergente` | BOOLEAN | Não | `true` quando a diferença absoluta entre `valor_total` e `valor_itens` é maior que R$ 0,01 |
| `itens_pedido.pedido_id` | INTEGER FK | Não | Referencia `pedidos.id` |
| `itens_pedido.linha` | INTEGER PK composta | Não | Posição do item no pedido, começando em 1; junto com `pedido_id`, forma a chave primária |
| `itens_pedido.produto_id` | INTEGER FK | Não | Referencia `produtos.produto_id` |
| `itens_pedido.quantidade` | INTEGER | Não | Deve ser inteiro |
| `itens_pedido.preco_unitario` | NUMERIC(10,2) | Não | Convertido para `Decimal` com duas casas usando `ROUND_HALF_UP`; valores com mais casas seriam arredondados |

Os 89.026 preços unitários observados nos sete snapshots brutos não têm casas decimais extras que mudem com o arredondamento. Os snapshots podem repetir o mesmo conjunto de origem.

Campos obrigatórios ausentes, valores que não podem ser convertidos ou violações das restrições do banco interrompem a carga; o ETL não inventa valores. `TEXT NOT NULL` permite texto vazio, que não é rejeitado por uma validação específica.

## As seis armadilhas

| Armadilha | Regra | Contador | Resultado |
|---|---|---|---:|
| A1 | E-mail nulo preservado como `NULL` | E-mails ausentes | 81 |
| A2 | Estado convertido para maiúsculas | Estados corrigidos | 151 |
| A3 | Datas convertidas para `date` | Datas `DD/MM/AAAA` | 1.037 |
| A4 | `valor_total` convertido para `Decimal` | Valores com vírgula | 1.255 |
| A5 | Duplicata idêntica mantida uma vez; conflito de conteúdo interrompe o ETL | Duplicados idênticos | 100 |
| A6 | `valor_itens` calculado; `valor_total` não é substituído | Pedidos divergentes | 238 |

Os contadores A3, A4 e A6 consideram somente os 5.000 pedidos únicos, após a deduplicação.

## Totais observados

| Métrica | Origem após transformação | PostgreSQL |
|---|---:|---:|
| Clientes | 1.000 | 1.000 |
| Produtos | 12 | 12 |
| Pedidos recebidos / únicos | 5.100 / 5.000 | 5.000 |
| Itens de pedido | 12.455 | 12.455 |
| Soma de `valor_total` | R$ 312.047,75 | R$ 312.047,75 |
| Soma de `valor_itens` | R$ 311.228,75 | R$ 311.228,75 |

A diferença de R$ 819,00 entre as somas reflete divergências dos dados de origem. O ETL preserva `valor_total` e calcula `valor_itens` separadamente.

## Observações e carga

- **Vendas** significa a soma de `pedidos.valor_total`, incluindo pedidos divergentes e todos os status.
- O pedido 81 tem `valor_total` negativo (−R$ 1,84), recebido da origem; o schema permite esse valor.
- A carga usa UPSERT (`INSERT ... ON CONFLICT ... DO UPDATE`) em uma transação, na ordem `produtos`, `clientes`, `pedidos`, `itens_pedido`. Com os mesmos dados, a carga repetida mantém as contagens. UPSERT não remove linhas que deixaram de aparecer na origem.
- Resultados de validação e detalhes das execuções estão no `README.md`.
