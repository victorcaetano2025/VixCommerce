from database.db import get_connection

connection = get_connection()

try:
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id, status FROM outbox_events"
    )

    events = cursor.fetchall()

    for event in events:
        print(dict(event))

finally:
    connection.close()
