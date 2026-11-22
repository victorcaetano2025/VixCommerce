# VixCommerce

Projeto acadêmico de arquitetura de microsserviços e gerenciamento de APIs.

## Tecnologias

- Python
- FastAPI
- Uvicorn
- SQLite
- RabbitMQ
- Docker

## Microsserviços

- Orders: gerenciamento de pedidos.
- Inventory: gerenciamento de estoque.
- Notifications: processamento de notificações.
- Outbox Publisher: worker independente que publica no RabbitMQ os eventos
  pendentes registrados pelo Orders.

## Objetivo

Desenvolver uma arquitetura de microsserviços para uma plataforma de comércio eletrônico, trabalhando com comunicação síncrona, assíncrona, contratos de APIs e resiliência.

## Bancos de dados

Os bancos são arquivos SQLite locais. Não é necessário iniciar um servidor de
banco nem executar comandos de criação manualmente:

- **Orders**: `vixcommerce.db`, na raiz do projeto. Armazena pedidos
  (`orders`), eventos da Outbox (`outbox_events`) e chaves de idempotência
  (`idempotency_keys`).
- **Notifications**: `services/notifications/database/notifications.db`.
  Armazena os eventos já processados (`processed_events`) para evitar
  processamento duplicado.

**Sim, a inicialização é automática:** ao iniciar o Orders, ele cria o arquivo
`vixcommerce.db` (se ainda não existir) e suas tabelas. Ao iniciar o Notifications,
ele cria `notifications.db` e a tabela de eventos processados. O Outbox Publisher
usa o banco do Orders; não precisa de um banco próprio. Basta iniciar os
processos conforme as instruções abaixo.

Os arquivos permanecem no disco quando os processos são encerrados e são
reutilizados na próxima execução. Esses bancos são locais para desenvolvimento e
demonstração; não são compartilhados entre réplicas e não são adequados para
concorrência distribuída em produção.

## Como executar o projeto no Windows

Abra o PowerShell na pasta raiz do projeto:

No Visual Studio Code, abra a pasta `VixCommerce` e use o terminal integrado,
indicando que os comandos abaixo devem ser executados na raiz do projeto.

### 1. Criar e ativar o ambiente Python

Se o ambiente `venv` ainda não tiver sido criado:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
```

Caso o PowerShell bloqueie a ativação:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
pip install -r requirements.txt
```

### 2. Iniciar o RabbitMQ

Com Docker Desktop aberto, execute:

```powershell
docker compose up -d
```

Confira se o serviço está ativo:

```powershell
docker compose ps
```

A interface administrativa pode ser aberta em:

<http://localhost:15672>

Credenciais configuradas no projeto:

- Usuário: `vixcommerce`
- Senha: `vixcommerce123`

### 3. Iniciar o microsserviço Inventory

Em um novo terminal:

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn services.inventory.main:app --port 8001
```

Acesse:

<http://localhost:8001/docs>

### 4. Iniciar o microsserviço Orders

Em outro terminal:

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn services.orders.main:app --port 8000
```

Acesse:

<http://localhost:8000/docs>

### 5. Iniciar o microsserviço Notifications

Em outro terminal:

```powershell
.\venv\Scripts\Activate.ps1
python -m services.notifications.main
```

O terminal deve ficar aguardando eventos com a mensagem `Aguardando eventos...`.

### 6. Iniciar o Outbox Publisher

Em outro terminal, inicie o worker e deixe-o rodando:

```powershell
.\venv\Scripts\Activate.ps1
python -m services.orders.outbox_publisher
```

O worker consulta a Outbox a cada dois segundos. Ao encontrar um evento
`PENDING`, publica-o no RabbitMQ e, após a confirmação do broker, atualiza seu
status para `PUBLISHED`. Se a publicação falhar, o evento permanece pendente e
será tentado novamente na próxima consulta.

### 7. Criar um pedido

No Swagger do Orders em <http://localhost:8000/docs>, execute `POST /orders`
usando um conteúdo semelhante ao seguinte:

```json
{
  "customerId": "cliente-003",
  "items": [
    {
      "sku": "SKU-22",
      "quantity": 1
    }
  ]
}
```

Informe no header `Idempotency-Key` uma chave única, por exemplo:

```text
pedido-cliente-003-1
```

Ao enviar novamente a mesma chave com o mesmo corpo, a API deve retornar o
mesmo pedido e não criar uma duplicação.

### 8. Consultar os dados persistidos

Os scripts de consulta podem ser executados pela raiz do projeto:

```powershell
python consultar_pedidos.py
python consultar_outbox.py
python consultar_idempotencia.py
python consultar_eventos.py
```

| Arquivo | O que consulta |
| --- | --- |
| `consultar_pedidos.py` | Pedidos do cliente `C-20`. Para consultar outro cliente, altere o filtro no script; também é possível usar `GET /orders` no Swagger. |
| `consultar_outbox.py` | ID e status (`PENDING` ou `PUBLISHED`) de todos os eventos da Outbox. |
| `consultar_idempotencia.py` | Chaves de idempotência, hash da requisição, status HTTP e resposta armazenada. |
| `consultar_eventos.py` | Eventos da Outbox de um pedido específico. O ID do pedido está definido no próprio script. |

Esses quatro scripts apenas leem e exibem dados.

### 9. Testar duplicidade do evento

O `reenviar_evento.py` publica novamente no RabbitMQ um evento cujo ID está
definido no próprio script:

```powershell
python reenviar_evento.py
```

Esse script envia uma mensagem de verdade. Com o Notifications em execução, o
consumer deve reconhecer o `eventId` já processado e ignorar a duplicidade.

### 10. Encerrar os processos

Em cada terminal, incluindo o Outbox Publisher, interrompa o processo com
`Ctrl+C`.

Para interromper o RabbitMQ:

```powershell
docker compose down
```

Para remover também o volume de dados do RabbitMQ:

```powershell
docker compose down -v
```

## Documentação de arquitetura

As principais decisões técnicas, alternativas avaliadas e consequências estão
registradas em [Decisões de Arquitetura](docs/DECISOES_ARQUITETURA.md).