import psycopg2
from psycopg2.extras import execute_values
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import time
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# BODS API configuration
BODS_API_URL = "https://data.bus-data.dft.gov.uk/api/v1/gtfsrtdatafeed/"
API_KEY = os.getenv("BODS_API_KEY")
LIVERPOOL_BBOX = "53.418993289369965,53.44199101568962,-2.976103768216373,-2.876646486925741"

feed = gtfs_realtime_pb2.FeedMessage()

# Fetch live data from BODS API
params = {
    'boundingBox': LIVERPOOL_BBOX,
    'api_key': API_KEY
}

response = requests.get(BODS_API_URL, params=params)

if response.status_code == 200:
    feed.ParseFromString(response.content)
else:
    print(f"API Error: {response.status_code}")
    exit(1)

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

    parse_start = time.time()
    
    for entity in feed.entity:
        if entity.HasField('vehicle'):
            v = entity.vehicle
            
            # Extract fields safely
            vehicle_id = v.vehicle.id if v.HasField('vehicle') else None
            latitude = v.position.latitude
            longitude = v.position.longitude
            
            # Convert Unix timestamp to datetime
            timestamp = datetime.fromtimestamp(v.timestamp) if v.HasField('timestamp') else None
            
            route_id = v.trip.route_id if v.HasField('trip') else None
            trip_id = v.trip.trip_id if v.HasField('trip') else None
            bearing = v.position.bearing if v.position.HasField('bearing') else None
            
            batch.append((vehicle_id, latitude, longitude, timestamp, route_id, trip_id, bearing))
    
    parse_end = time.time()
    
    # Database insert
    insert_start = time.time()
    execute_values(cursor, """
        INSERT INTO vehicle_positions 
        (vehicle_id, latitude, longitude, timestamp, route_id, trip_id, bearing)
        VALUES %s
        ON CONFLICT (vehicle_id, timestamp) DO NOTHING
    """, batch)
    
    conn.commit()
    insert_end = time.time()
    
    print(f"Parse/extract time: {parse_end - parse_start:.2f}s")
    print(f"Database insert time: {insert_end - insert_start:.2f}s")
    print(f"Total records processed: {len(batch)}")
    
    cursor.close()
    
except Exception as e:
    print("Error:", e)
    
finally:
    if conn:
        conn.close()