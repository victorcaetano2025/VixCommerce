
import pika

from database.db import get_connection
from services.orders.rabbitmq import get_connection as get_rabbitmq_connection

event_id = "b1f6f309-f9c4-4921-8ad1-10d56a36242a"

connection = get_connection()

try:
    cursor = connection.cursor()

    cursor.execute(
        "SELECT event_type, payload FROM outbox_events WHERE id = ?",
        (event_id,)
    )

    event = cursor.fetchone()

finally:
    connection.close()

if event is None:
    print("Evento não encontrado.")
else:
    rabbit_connection = get_rabbitmq_connection()

    try:
        channel = rabbit_connection.channel()

        channel.exchange_declare(
            exchange="vixcommerce.events",
            exchange_type="topic",
            durable=True
        )

        channel.confirm_delivery()

        channel.basic_publish(
            exchange="vixcommerce.events",
            routing_key=event["event_type"],
            body=event["payload"],
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
                message_id=event_id
            ),
            mandatory=True
        )

        print("Mesmo evento enviado novamente!")

    finally:
        rabbit_connection.close()
