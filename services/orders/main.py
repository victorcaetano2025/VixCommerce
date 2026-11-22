
import requests
import json
import hashlib

from uuid import uuid4
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from database.db import create_tables, get_connection


app = FastAPI(title="VixCommerce Orders")


@app.on_event("startup")
def startup():
    create_tables()


@app.get("/")
def home():
    return {"message": "Orders funcionando!"}


@app.post("/orders")
def create_order(
    order: dict,
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):

    # 1. Calcula o hash do conteúdo recebido
    request_body = json.dumps(order, sort_keys=True)

    request_hash = hashlib.sha256(
        request_body.encode()
    ).hexdigest()

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # 2. Verifica se a chave já foi utilizada
        cursor.execute(
            """
            SELECT request_hash, response_body, status_code
            FROM idempotency_keys
            WHERE idempotency_key = ?
            """,
            (idempotency_key,)
        )

        existing_request = cursor.fetchone()

        if existing_request:

            if existing_request["request_hash"] != request_hash:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key já utilizada com outro conteúdo."
                )

            return JSONResponse(
                status_code=existing_request["status_code"],
                content=json.loads(existing_request["response_body"])
            )

        # 3. Consulta o Inventory e reserva os produtos
        items = order.get("items", [])

        if not items:
            raise HTTPException(
                status_code=400,
                detail="O pedido precisa conter pelo menos um produto."
            )

        for item in items:
            try:
                response = requests.post(
                    "http://localhost:8001/inventory/reservations",
                    json={
                        "sku": item["sku"],
                        "quantity": item["quantity"]
                    },
                    timeout=3
                )

            except requests.RequestException:
                raise HTTPException(
                    status_code=503,
                    detail="Serviço Inventory indisponível."
                )

            if response.status_code != 200:
                detail = response.json().get(
                    "detail",
                    "Não foi possível reservar o estoque."
                )

                raise HTTPException(
                    status_code=response.status_code,
                    detail=detail
                )

        # 4. Cria o novo pedido
        order_id = str(uuid4())
        event_id = str(uuid4())

        new_order = {
            "orderId": order_id,
            "status": "CREATED",
            **order
        }

        event = {
            "eventId": event_id,
            "eventType": "order.created",
            "data": new_order
        }

        response_body = {
            "message": "Pedido criado e evento registrado na Outbox!",
            "order": new_order,
            "eventId": event_id
        }

        # 5. Salva pedido, evento e chave na mesma transação
        cursor.execute(
            """
            INSERT INTO orders (id, customer_id, status)
            VALUES (?, ?, ?)
            """,
            (
                order_id,
                new_order["customerId"],
                new_order["status"]
            )
        )

        cursor.execute(
            """
            INSERT INTO outbox_events
            (id, aggregate_id, event_type, payload)
            VALUES (?, ?, ?, ?)
            """,
            (
                event_id,
                order_id,
                "order.created",
                json.dumps(event)
            )
        )

        cursor.execute(
            """
            INSERT INTO idempotency_keys
            (idempotency_key, request_hash, response_body, status_code)
            VALUES (?, ?, ?, ?)
            """,
            (
                idempotency_key,
                request_hash,
                json.dumps(response_body),
                201
            )
        )

        connection.commit()

        return JSONResponse(
            status_code=201,
            content=response_body
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


@app.get("/orders")
def list_orders():

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM orders")

        orders = [
            dict(row)
            for row in cursor.fetchall()
        ]

        return orders

    finally:
        connection.close()
