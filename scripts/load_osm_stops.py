"""
Fetch bus stops from OpenStreetMap using Overpass API
Loads them into PostgreSQL as osm_stops table
"""

import requests
import psycopg2
from psycopg2.extras import execute_values, Json
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'pt_analytics'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD')
}

# Liverpool bounding box - EXPANDED to cover full metro area
# Format: south,west,north,east
BBOX = "53.35,-3.05,53.48,-2.80"  # Full Liverpool metro

def fetch_osm_stops():
    """Fetch bus stops from OSM Overpass API"""
    
    # Overpass query for bus stops
    query = f"""
    [out:json][timeout:60];
    (
      node["highway"="bus_stop"]({BBOX});
      node["public_transport"="platform"]({BBOX});
      node["public_transport"="stop_position"]({BBOX});
    );
    out body;
    """
    
    print("Querying Overpass API for Liverpool bus stops...")
    
    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        data=query,
        timeout=120
    )
    
    if response.status_code != 200:
        raise Exception(f"Overpass API error: {response.status_code}")
    
    data = response.json()
    stops = data.get('elements', [])
    
    print(f"Found {len(stops)} bus stops from OSM")
    return stops

def create_osm_stops_table(cur):
    """Create osm_stops table with PostGIS geometry"""
    
    cur.execute("""
        DROP TABLE IF EXISTS osm_stops CASCADE;
        
        CREATE TABLE osm_stops (
            osm_id BIGINT PRIMARY KEY,
            name TEXT,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            location GEOGRAPHY(Point, 4326),
            tags JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE INDEX idx_osm_stops_location ON osm_stops USING GIST(location);
    """)
    
    print("Created osm_stops table")

def load_stops_to_db(stops):
    """Load OSM stops into PostgreSQL"""
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        create_osm_stops_table(cur)
        
        # Prepare data for insertion
        stop_data = []
        for stop in stops:
            osm_id = stop['id']
            lat = stop['lat']
            lon = stop['lon']
            tags = stop.get('tags', {})
            name = tags.get('name', tags.get('ref', f'Stop {osm_id}'))
            
            stop_data.append((
                osm_id,
                name,
                lat,
                lon,
                lon,
                lat,
                Json(tags)
            ))
        
        # Insert stops
        execute_values(
            cur,
            """
            INSERT INTO osm_stops (osm_id, name, latitude, longitude, location, tags)
            VALUES %s
            ON CONFLICT (osm_id) DO NOTHING
            """,
            stop_data,
            template="(%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)",
            page_size=100,
            fetch=False
        )
        
        conn.commit()
        print(f"✓ Loaded {len(stop_data)} stops into osm_stops table")
        
        # Show sample
        cur.execute("SELECT osm_id, name, latitude, longitude FROM osm_stops LIMIT 5")
        samples = cur.fetchall()
        print("\nSample stops:")
        for s in samples:
            print(f"  {s[1]} ({s[2]:.4f}, {s[3]:.4f})")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    stops = fetch_osm_stops()
    load_stops_to_db(stops)
