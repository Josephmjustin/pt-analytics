import csv
import psycopg2
from psycopg2.extras import execute_values

try:
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="pt_analytics_db",
        user="ptqueryer",
        password="pt_pass"
    )
    cursor = conn.cursor()
    batch = []
    
    with open("../static/stops.txt", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            stop_id = row.get("stop_id") or None
            stop_code = row.get("stop_code") or None
            stop_name = row.get("stop_name") or None

            # Convert numeric fields safely
            try:
                stop_lat = float(row.get("stop_lat")) if row.get("stop_lat") else None
            except ValueError:
                stop_lat = None

            try:
                stop_lon = float(row.get("stop_lon")) if row.get("stop_lon") else None
            except ValueError:
                stop_lon = None

            wheelchair_boarding = (
                int(row.get("wheelchair_boarding"))
                if row.get("wheelchair_boarding") not in (None, "")
                else None
            )

            location_type = (
                int(row.get("location_type"))
                if row.get("location_type") not in (None, "")
                else None
            )

            parent_station = row.get("parent_station") or None
            platform_code = row.get("platform_code") or None

            batch.append((stop_id, stop_code, stop_name, stop_lat, stop_lon, stop_lon, stop_lat, wheelchair_boarding, location_type, parent_station, platform_code))
        
    # Database insert
    execute_values(cursor, """
        INSERT INTO gtfs_stops 
        (stop_id, stop_code, stop_name, stop_lat, stop_lon, location, wheelchair_boarding, location_type, parent_station, platform_code)
        VALUES %s
        ON CONFLICT (stop_id) DO NOTHING
    """, batch, template="(%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s)")
    
    conn.commit()
    print(f"Total records processed: {len(batch)}")
    cursor.close()
    
except Exception as e:
    print("Error:", e)
    
finally:
    if conn:
        conn.close()