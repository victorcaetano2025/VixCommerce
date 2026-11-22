
import pika
import json
import os


def get_connection():
    credentials = pika.PlainCredentials(
        os.getenv("RABBITMQ_USER", "vixcommerce"),
        os.getenv("RABBITMQ_PASSWORD", "vixcommerce123")
    )

    parameters = pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST", "localhost"),
        port=5672,
        credentials=credentials,
        heartbeat=60
    )

    return pika.BlockingConnection(parameters)


def publish_order_event(order):
    connection = get_connection()
    channel = connection.channel()

    channel.exchange_declare(
        exchange="vixcommerce.events",
        exchange_type="topic",
        durable=True
    )

    channel.basic_publish(
        exchange="vixcommerce.events",
        routing_key="order.created",
        body=json.dumps(order),
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type="application/json"
        )
    )

    connection.close()
