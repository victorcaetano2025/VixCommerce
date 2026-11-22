
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="VixCommerce Inventory")


# Estoque inicial para simulação
inventory = {
    "SKU-22": 10,
    "SKU-23": 5,
    "SKU-24": 0
}


class ReservationRequest(BaseModel):
    sku: str
    quantity: int


@app.get("/")
def home():
    return {"message": "Inventory funcionando!"}


@app.get("/inventory/{sku}")
def check_stock(sku: str):

    if sku not in inventory:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado."
        )

    return {
        "sku": sku,
        "available": inventory[sku]
    }


@app.post("/inventory/reservations")
def reserve_stock(request: ReservationRequest):

    if request.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="A quantidade deve ser maior que zero."
        )

    if request.sku not in inventory:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado."
        )

    if inventory[request.sku] < request.quantity:
        raise HTTPException(
            status_code=409,
            detail="Estoque insuficiente."
        )

    inventory[request.sku] -= request.quantity

    return {
        "message": "Estoque reservado com sucesso!",
        "sku": request.sku,
        "reserved": request.quantity,
        "remaining": inventory[request.sku]
    }
