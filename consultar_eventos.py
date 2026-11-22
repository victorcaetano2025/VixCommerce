
from database.db import get_connection

connection = get_connection()

try:
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, aggregate_id, event_type, status
        FROM outbox_events
        WHERE aggregate_id = 'b18a08b7-2a77-4d3f-87a0-69b9fb32fc31'
    """)

    events = cursor.fetchall()

    for event in events:
        print(dict(event))

    print(f"\nTotal de eventos: {len(events)}")

finally:
    connection.close()
