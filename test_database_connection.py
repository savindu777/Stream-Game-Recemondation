
from database import get_connection

conn = get_connection()

try:
    with conn.cursor() as cursor:

        cursor.execute("SELECT COUNT(*) FROM games")

        total = cursor.fetchone()[0]

        print("Total games:", total)

finally:
    conn.close()
