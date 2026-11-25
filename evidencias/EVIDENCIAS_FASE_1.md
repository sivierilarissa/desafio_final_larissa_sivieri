# Evidências — Fase 1: extração

**Código:** `etl/extracao.py` implementa a extração e as validações; `etl/main.py` coordena o processo e imprime os contadores.

**Execução observada em 21/11/2026**, com a API local e páginas de 50 registros:

| Recurso | Páginas | Registros recebidos |
|---|---:|---:|
| Clientes | 20 | 1.000 |
| Pedidos | 102 | 5.100 |

Os pedidos incluem 100 duplicatas. A extração preserva os 5.100 registros; a deduplicação ocorre depois, na transformação. O terminal confirmou a conclusão das 20 páginas de clientes e das 102 páginas de pedidos.

`buscar_pagina` valida os parâmetros antes da chamada HTTP e trata falhas de conexão/HTTP, JSON inválido e respostas com paginação inconsistente. `extrair_todas_paginas` confere os totais informados pela API e o total de registros recebido. Esses comportamentos estão implementados no código; este documento não afirma que cenários de falha foram testados manualmente.

Os dados originais foram salvos antes da transformação em `brutos/`, com timestamp nos nomes. Exemplos: `clientes_20261121T182006335229-0300.json` e `pedidos_20261121T182006520417-0300.json`. Os arquivos ficam localmente; `brutos/` está no `.gitignore`.

Para reproduzir a extração com o ambiente atual, na raiz do projeto e com a API ligada:

```bash
source .venv/bin/activate
python -m etl.main
```
