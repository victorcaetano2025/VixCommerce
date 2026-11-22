
from database.db import get_connection

connection = get_connection()

try:
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, customer_id, status
        FROM orders
        WHERE customer_id = 'C-20'
    """)

    orders = cursor.fetchall()

    print("Pedidos encontrados:")
    for order in orders:
        print(dict(order))

    print(f"\nTotal de pedidos: {len(orders)}")

finally:
    connection.close()
