import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="pt_analytics_db",
        user="ptqueryer",
        password="pt_pass"
    )
    print("Connected successfully")
except Exception as e:
    print("Connection failed:", e)
