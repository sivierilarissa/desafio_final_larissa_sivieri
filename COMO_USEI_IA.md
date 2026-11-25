# Como usei IA

## Ferramenta e forma de uso

Utilizei o ChatGPT(Codex) e o Claude como apoio durante o desenvolvimento do projeto. Pedi ajuda para comparar alternativas, entender mensagens do terminal, revisar partes do código e pensar em testes. Eu defini as tarefas, avaliei as propostas, executei os comandos e tomei as decisões sobre o que manter ou alterar.

## Sugestões aceitas

### Comparação de estratégias de idempotência

**Pedido:** comparei estratégias para que executar o ETL novamente não duplicasse os dados.

**Proposta:** a IA explicou alternativas como UPSERT, limpar as tabelas antes de cada carga e ignorar registros com chaves já existentes.

**Decisão:** escolhi UPSERT em uma transação única porque ele atualiza os registros existentes e permite aplicar correções vindas da origem. Registrei como limite que essa estratégia não remove do banco registros que tenham desaparecido da origem.

**Validação:** executei duas cargas e obtive as mesmas contagens: 1.000 clientes, 12 produtos, 5.000 pedidos e 12.455 itens. O teste `test_idempotencia_da_carga_mantem_contagens` também verifica o comportamento em duas cargas.

### Revisão do teste de reconciliação

**Pedido:** revisei o teste que compara a soma das vendas mensais com a soma geral.

**Proposta:** a IA observou que uma tolerância de R$ 0,01 poderia aceitar uma diferença de um centavo e sugeriu comparar os valores com igualdade exata.

**Decisão:** aceitei porque os valores comparados são do tipo `NUMERIC`, apropriado para valores monetários.

**Validação:** o teste compara `soma_meses == total_geral`, e a consulta de conferência retorna `confere = t`.

### Casos adicionais para os testes de transformação

**Pedido:** revisei os testes das funções de transformação.

**Proposta:** a IA sugeriu testar uma data inexistente, um conflito envolvendo pedido repetido e o limite da tolerância financeira.

**Decisão:** aceitei esses casos para complementar os caminhos esperados e verificar erros e limites das regras.

**Validação:** a suíte tem 13 testes: 10 de transformação, cobrindo A1 a A6 e casos adicionais, e 3 de reconciliação.

### Consultas de validação e marcadores SQL

**Pedido:** revisei as consultas SQL de validação e a forma de localizá-las nos testes.

**Proposta:** a IA sugeriu explicar o que significa “vendas” na consulta mensal e criar uma consulta para conferir a soma mensal com a soma geral. Também esclareceu os marcadores usados para identificar as consultas.

**Decisão:** aceitei as explicações e mantive marcadores distintos. `-- QUERY: vendas_por_mes` identifica a consulta mensal; `-- QUERY: conferencia_soma_vendas_mes` identifica a consulta de conferência.

**Validação:** a soma mensal e a soma geral retornaram R$ 312.047,75, a conferência retornou `confere = t` e a consulta identificou 238 pedidos divergentes.

### Validação mais estrita das siglas de estado

**Pedido:** avaliei como validar o campo `estado` dos clientes.

**Proposta:** a IA apontou que verificar apenas o comprimento permitiria valores como `"1!"` e `"éS"`. Sugeriu exigir exatamente duas letras ASCII.

**Decisão:** aceitei a validação mais estrita para garantir que a sigla contenha duas letras sem acentos, números ou pontuação.

**Validação:** o teste `test_a2_rejeita_estado_que_nao_seja_duas_letras_ascii` verifica a rejeição de valores inválidos. Outro teste verifica a conversão de letras minúsculas para maiúsculas.

### Ampliação da cobertura dos testes

**Pedido:** Optei por verificar se os testes cobriam também os módulos de extração, carga e execução principal, além das transformações e da reconciliação.

**Decisão:** ampliei a verificação e consultei o relatório de cobertura para identificar se havia partes do código que os testes não executavam.

**Validação:** executei `python -m coverage run --source=etl -m pytest`: os 13 testes passaram. O relatório de cobertura mostrou 62% no total: `carga.py` 91%, `extracao.py` 29%, `main.py` 0% e `transformacao.py` 84%. Esse percentual mede quais linhas foram exercitadas pelos testes; não significa que um teste tenha falhado.

## Sugestões rejeitadas

### Incluir o corpo da resposta HTTP na mensagem de erro

**Pedido:** revisei a função `buscar_pagina`, responsável por buscar páginas da API.

**Proposta:** foi sugerido incluir o corpo da resposta HTTP, como `pagina inexistente`, na mensagem de erro.

**Decisão:** mantive o uso de `raise_for_status()` e o tratamento com `ErroExtracao`. Na revisão, considerei que depender do conteúdo da resposta poderia deixar a mensagem instável; preferi manter uma mensagem com contexto do recurso e da página.

**Validação:** com a API desligada, a extração retorna `ErroExtracao` com o contexto do recurso e da página.

### Criar uma função separada para converter produtos

**Pedido:** avaliei onde fazer a conversão dos campos de produto antes de carregá-los no banco.

**Proposta:** foi sugerida uma função separada `converter_produtos` em `transformacao.py`.

**Decisão:** não criei essa função. No código atual, `_linhas_produtos`, em `carga.py`, converte `produto_id` para inteiro e `preco_base` para `Decimal` ao preparar os parâmetros do UPSERT. Entendi essa etapa como uma adaptação dos tipos do CSV aos tipos esperados pelo banco, sem uma regra A1 a A6 específica para produtos.

**Validação:** a carga inseriu 12 produtos e a reconciliação conferiu a contagem no destino.

## Falhas e retrabalho

### Aviso do `urllib3` com o Python do sistema

**O que aconteceu:** o Python 3.9.6 do sistema usava LibreSSL, e o `urllib3` v2 emitia um aviso relacionado a essa configuração.

**Como corrigi:** usei uma `.venv` com Python 3.14.10 para as execuções registradas, em vez de ocultar o aviso.

**Validação:** executei os testes usando o Python da `.venv`.