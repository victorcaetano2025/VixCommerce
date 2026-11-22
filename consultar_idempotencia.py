
from database.db import get_connection

connection = get_connection()

try:
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            idempotency_key,
            request_hash,
            status_code,
            response_body
        FROM idempotency_keys
    """)

    records = cursor.fetchall()

    for record in records:
        print(dict(record))

    print(f"\nTotal de chaves: {len(records)}")

finally:
    connection.close()
