import time
import psycopg2
from psycopg2.extras import execute_values
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import requests
import os
from dotenv import load_dotenv

load_dotenv()
BODS_API_URL = "https://data.bus-data.dft.gov.uk/api/v1/gtfsrtdatafeed/"
API_KEY = os.getenv("BODS_API_KEY")
LIVERPOOL_BBOX = "53.418993289369965,53.44199101568962,-2.976103768216373,-2.876646486925741"

feed = gtfs_realtime_pb2.FeedMessage()
# parameters for BODS API request
params = {
    'boundingBox': LIVERPOOL_BBOX,
    'api_key': API_KEY
}

def poll_and_ingest():
    """Run one ingestion cycle"""
    conn = None
    try:
        # API call
        response = requests.get(BODS_API_URL, params=params)
        
        if response.status_code != 200:
            print(f"API Error: {response.status_code}")
            return  # Skip this cycle, don't exit
        
        feed.ParseFromString(response.content)
        
        # Database connection
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        cursor = conn.cursor()
        batch = []
        
        parse_start = time.time()
        
        for entity in feed.entity:
            if entity.HasField('vehicle'):
                v = entity.vehicle
                
                latitude = v.position.latitude
                longitude = v.position.longitude
                
                # Filter to Liverpool only (53.35-53.48, -3.05 to -2.85)
                if not (53.35 <= latitude <= 53.48 and -3.05 <= longitude <= -2.85):
                    continue
                
                vehicle_id = v.vehicle.id if v.HasField('vehicle') else None
                timestamp = datetime.fromtimestamp(v.timestamp) if v.HasField('timestamp') else None
                route_id = v.trip.route_id if v.HasField('trip') else None
                trip_id = v.trip.trip_id if v.HasField('trip') else None
                bearing = v.position.bearing if v.position.HasField('bearing') else None
                
                batch.append((vehicle_id, latitude, longitude, timestamp, route_id, trip_id, bearing, longitude, latitude))
        
        parse_end = time.time()
        
        # Database insert
        insert_start = time.time()
        execute_values(cursor, """
            INSERT INTO vehicle_positions 
            (vehicle_id, latitude, longitude, timestamp, route_id, trip_id, bearing, geom)
            VALUES %s
            ON CONFLICT (vehicle_id, timestamp) DO NOTHING
        """, batch, 
        template="(%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))")
        
        conn.commit()
        insert_end = time.time()
        
        print(f"[{datetime.now()}] Parse: {parse_end - parse_start:.2f}s | Insert: {insert_end - insert_start:.2f}s | Records: {len(batch)}")
        
        cursor.close()
        
    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")
        
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Starting continuous polling (every 60 seconds)...")
    print("Press Ctrl+C to stop")
    
    while True:
        try:
            poll_and_ingest()
            time.sleep(60)
        except KeyboardInterrupt:
            print("\nStopping poller...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)  # Wait before retry