
import json
import sqlite3
import time

import pika

from database.db import get_connection
from services.orders.rabbitmq import get_connection as get_rabbitmq_connection

POLL_INTERVAL_SECONDS = 2


def get_pending_events():

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT id, aggregate_id, event_type, payload
            FROM outbox_events
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
        """)

        events = [dict(row) for row in cursor.fetchall()]

        return events

    finally:
        connection.close()


def publish_event(event):

    connection = get_rabbitmq_connection()

    try:
        channel = connection.channel()

        channel.exchange_declare(
            exchange="vixcommerce.events",
            exchange_type="topic",
            durable=True
        )

        # Ativa confirmação de publicação pelo RabbitMQ
        channel.confirm_delivery()

        channel.basic_publish(
            exchange="vixcommerce.events",
            routing_key=event["event_type"],
            body=event["payload"],
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
                message_id=event["id"]
            ),
            mandatory=True
        )

        print(f"Evento publicado: {event['id']}")

    finally:
        connection.close()


def mark_event_as_published(event_id):

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE outbox_events
            SET status = 'PUBLISHED',
                published_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (event_id,)
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()



def process_outbox():

    try:
        events = get_pending_events()
    except sqlite3.Error as error:
        print(f"Erro ao consultar eventos pendentes da Outbox: {error}")
        return

    if not events:
        return

    for event in events:

        try:
            publish_event(event)

            mark_event_as_published(event["id"])

        except (pika.exceptions.AMQPError, OSError, sqlite3.Error) as error:
            print(f"Erro ao publicar evento {event['id']}: {error}")


def run_publisher():
    print(
        "Outbox Publisher iniciado. "
        f"Consultando eventos a cada {POLL_INTERVAL_SECONDS} segundos..."
    )

    while True:
        process_outbox()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        run_publisher()
    except KeyboardInterrupt:
        print("Outbox Publisher encerrado.")