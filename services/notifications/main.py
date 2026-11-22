
import pika
import json

from services.notifications.database.db import (
    create_tables,
    get_connection
)


def callback(ch, method, properties, body):

    try:
        event = json.loads(body)

        event_id = event["eventId"]
        event_type = event["eventType"]

        connection = get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO processed_events
                (event_id, event_type)
                VALUES (?, ?)
                """,
                (event_id, event_type)
            )

            if cursor.rowcount == 0:
                print(f"Evento duplicado ignorado: {event_id}")
            else:
                print("Evento recebido pelo Notifications:")
                print(json.dumps(event, indent=4))
                print("Notificação processada!")

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as error:
        print(f"Erro ao processar evento: {error}")

        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True
        )


def start_consumer():

    # Garante que a tabela de eventos processados exista
    create_tables()

    credentials = pika.PlainCredentials(
        "vixcommerce",
        "vixcommerce123"
    )

    parameters = pika.ConnectionParameters(
        host="localhost",
        port=5672,
        credentials=credentials
    )

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    channel.exchange_declare(
        exchange="vixcommerce.events",
        exchange_type="topic",
        durable=True
    )

    channel.queue_declare(
        queue="notifications.order.created",
        durable=True
    )

    channel.queue_bind(
        exchange="vixcommerce.events",
        queue="notifications.order.created",
        routing_key="order.created"
    )

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue="notifications.order.created",
        on_message_callback=callback
    )

    print("Aguardando eventos...")
    channel.start_consuming()


if __name__ == "__main__":
    start_consumer()
