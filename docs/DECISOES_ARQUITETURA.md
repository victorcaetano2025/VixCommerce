# Decisoes de Arquitetura

Este documento registra as principais decisoes adotadas no projeto VixCommerce
para resolver idempotencia, resiliência e comunicacao entre microsservicos.

## ADR-001 — Arquitetura baseada em microsservicos

### Contexto

O sistema precisa separar as responsabilidades de pedidos, estoque e notificacoes.

### Decisao

O projeto foi dividido em tres microsservicos independentes:

- Orders: cria pedidos e registra eventos.
- Inventory: consulta e reserva estoque.
- Notifications: recebe e processa eventos assíncronos.

### Alternativas consideradas

- Monólito: rejeitado porque reduziria a separacao de responsabilidades e a
  demonstracao dos padrões distribuídos solicitados.
- Microsservicos sem protocolos HTTP/AMQP: rejeitado porque nao atenderia aos
  requisitos de comunicacao sincrona e assincrona.

### Consequencias

- Maior isolamento entre dominios.
- Necessidade de tratar falhas de rede e inconsistencias temporarias.
- Os servicos precisam usar contratos definidos e configuracao independente.

## ADR-002 — Comunicacao sincrona para reserva de estoque

### Contexto

Ao criar um pedido, o Orders precisa confirmar previamente se o estoque esta
disponivel.

### Decisao

Foi adotada comunicacao sincrona por HTTP/REST entre Orders e Inventory.

### Alternativas consideradas

- Comunicacao assíncrona: nao seria adequada para confirmar a reserva antes da
  resposta de criacao do pedido.
- Validacao local no Orders: rejeitada porque duplicaria a fonte de verdade do
  estoque.

### Consequencias

- Acoes invalidas podem retornar respostas HTTP de erro imediatamente.
- Falha ou indisponibilidade do Inventory gera HTTP 503.
- Falha em um item apos reservas anteriores exige estrategia de compensacao
  para nao deixar estoque reservado parcialmente.

## ADR-003 — Idempotencia na criacao de pedidos

### Contexto

Uma requisicao pode ser enviada mais de uma vez por timeout, retry ou falha
entre cliente e servidor.

### Decisao

O endpoint `POST /orders` exige o header `Idempotency-Key`. A chave e armazenada
junto com o hash do conteudo, o codigo HTTP e o corpo da resposta.

Comportamento:

- Mesma chave e mesmo conteudo: retorna a resposta original.
- Mesma chave e conteudo diferente: retorna HTTP 409.
- Nova chave: cria pedido e registra a resposta.

### Alternativas consideradas

- Duplicacao identificada apenas pelo pedido: rejeitada porque nao distingue
  corretamente requisições e nao preserva a resposta original.
- Chave sem hash do conteudo: rejeitada porque permitiria reutilizar uma chave
  para outro pedido.

### Consequencias

- Evita pedidos duplicados em repeticoes da mesma requisicao.
- Exige que o cliente gere uma chave unica para cada operacao.
- Identificador e resultado da primeira requisicao ficam persistidos.

## ADR-004 — Outbox transacional

### Contexto

Criar o pedido no banco e publicar o evento separadamente pode gerar inconsistencias:

- Pedido criado sem evento publicado.
- Evento publicado sem pedido persistido.

### Decisao

Foi adotado o padrao Transactional Outbox. O pedido, o evento
`order.created` e a chave de idempotencia sao persistidos na mesma transacao
SQLite. Um publisher separado roda como worker independente, consulta eventos
com status `PENDING` a cada dois segundos e publica no RabbitMQ. O evento so e
marcado como `PUBLISHED` depois da confirmacao de publicacao pelo broker.

### Alternativas consideradas

- Publicar direto apos salvar o pedido: rejeitado por nao garantir atomicidade.
- Nao persistir eventos: rejeitado por impedir recuperacao apos falha.
- Executar o publisher dentro do processo HTTP do Orders: rejeitado para manter
  o ciclo de vida do worker independente da API e permitir escalar cada processo
  separadamente.

### Consequencias

- Pedido e registro do evento nao ficam inconsistentes.
- Eventos podem permanecer `PENDING` durante indisponibilidade do RabbitMQ e
  sao tentados novamente pelo worker.
- O worker deve ser iniciado junto com os demais processos da aplicação e
  permanecer em execução.
- Se a publicação for confirmada mas a atualização do banco falhar, o evento
  pode ser publicado novamente; o consumer deve continuar idempotente.

## ADR-005 — RabbitMQ com exchange topic

### Contexto

Os pedidos criados precisam ser distribuidos para consumidores interessados sem
acoplar Orders diretamente a Notifications.

### Decisao

Foi usado RabbitMQ com exchange do tipo `topic`, nomeado
`vixcommerce.events`. A rota `order.created` publica eventos para a fila
`notifications.order.created`.

### Alternativas consideradas

- HTTP direto para Notifications: rejeitado porque acopla os microsservicos e
  perde a resiliencia proporcionada por uma fila.
- Exchange do tipo direct: rejeitado por oferecer menor flexibilidade futura.

### Consequencias

- Notifications pode receber eventos independentemente da disponibilidade
  imediata do Orders.
- O RabbitMQ persiste a troca e a fila entre reinicializacoes.
- Novos consumidores podem usar outras routing keys sem alterar o publisher.

## ADR-006 — Confirmacao manual de mensagens e tratamento de duplicidade

### Contexto

Falhas apos o processamento podem causar reentrega da mesma mensagem pelo broker.
Reprocessar o evento sem controle pode gerar efeitos duplicados.

### Decisao

O consumer usa `prefetch_count=1` e confirma a mensagem somente depois de
persistir o resultado. O campo `event_id` em `processed_events` funciona como
chave primária para ignorar duplicidades.

Em caso de erro:

- `basic_nack(requeue=True)` devolve a mensagem para reprocessamento.

### Alternativas consideradas

- Ack imediato: rejeitado porque poderia perder eventos em caso de falha posterior.
- Processamento sem controle de duplicidade: rejeitado por violar o comportamento
  idempotente do consumer.

### Consequencias

- O mesmo evento pode ser entregue mais de uma vez, mas o efeito nao se duplica.
- Falhas temporarias permitem reentrega.
- Erros permanentes exigem tratamento futuro por retry limitado e dead-letter queue.

## ADR-007 — SQLite para persistencia local

### Contexto

O projeto deve ser simples de executar e demonstrar em ambiente academico.

### Decisao

Cada banco usado pelo projeto utiliza SQLite:

- Banco compartilhado dos pedidos e da Outbox.
- Banco separado para os eventos processados por Notifications.

### Alternativas consideradas

- PostgreSQL ou outro banco de rede: nao foi adotado para manter o ambiente
  simples e evitar infraestrutura adicional neste exercicio.

### Consequencias

- Facilita demonstracao e reproducao local.
- A persistencia nao deve ser considerada adequada para concorrencia distribuida
  em producao.
- A separacao dos bancos nao substitui um transacao distribuida real.

## Riscos e melhorias futuras

- Adicionar retry limitado e Dead-Letter Queue no RabbitMQ.
- Implementar compensacao de estoque em pedidos com varios itens.
- Substituir SQLite por banco compartilhado entre replica do mesmo servico em
  ambiente distribuido.
- Adicionar observabilidade com identificador de correlacao e metricas.
