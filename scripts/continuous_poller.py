"""
Continuous polling of BODS GTFS-RT feed with TransXChange matching
Fetches vehicle positions and matches to route-specific stops
"""

import os
import requests
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

# Import vehicle matcher
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.processing.vehicle_matcher import match_vehicle_to_stop

load_dotenv()

# BODS API Configuration
BODS_API_KEY = os.getenv("BODS_API_KEY")
LIVERPOOL_BBOX = "-3.05,53.35,-2.85,53.48"
GTFS_RT_URL = f"https://data.bus-data.dft.gov.uk/api/v1/gtfsrtdatafeed/?api_key={BODS_API_KEY}&boundingBox={LIVERPOOL_BBOX}"

# Database Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT", 5432)
}

def fetch_vehicle_positions():
    """Fetch vehicle positions from BODS GTFS-RT API"""
    try:
        response = requests.get(GTFS_RT_URL, timeout=30)
        response.raise_for_status()
        
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        
        vehicles = []
        for entity in feed.entity:
            if not entity.HasField('vehicle'):
                continue
            
            vehicle = entity.vehicle
            
            # Extract position data
            if vehicle.HasField('position'):
                vehicle_data = {
                    'vehicle_id': vehicle.vehicle.id if vehicle.HasField('vehicle') and vehicle.vehicle.HasField('id') else entity.id,
                    'route_id': vehicle.trip.route_id if vehicle.HasField('trip') and vehicle.trip.HasField('route_id') else None,
                    'trip_id': vehicle.trip.trip_id if vehicle.HasField('trip') and vehicle.trip.HasField('trip_id') else None,
                    'latitude': vehicle.position.latitude,
                    'longitude': vehicle.position.longitude,
                    'bearing': vehicle.position.bearing if vehicle.position.HasField('bearing') else None,
                    'timestamp': datetime.fromtimestamp(vehicle.timestamp) if vehicle.HasField('timestamp') else datetime.now()
                }
                vehicles.append(vehicle_data)
        
        return vehicles
    
    except Exception as e:
        print(f"Error fetching GTFS-RT: {e}")
        return []

def store_vehicle_positions(vehicles):
    """Store raw vehicle positions (staging table - 15min retention)"""
    if not vehicles:
        return
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Insert vehicle positions
    values = [
        (
            v['vehicle_id'],
            v['latitude'],
            v['longitude'],
            v['timestamp'],
            v['route_id'],
            v['trip_id'],
            v['bearing']
        )
        for v in vehicles
    ]
    
    execute_batch(cur, """
        INSERT INTO vehicle_positions 
        (vehicle_id, latitude, longitude, timestamp, route_id, trip_id, bearing)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (vehicle_id, timestamp) DO NOTHING
    """, values, page_size=500)
    
    conn.commit()
    cur.close()
    conn.close()

def match_and_record_arrivals(vehicles):
    """Match vehicles to stops using TransXChange and record arrivals"""
    if not vehicles:
        return
    
    print(f"Matching {len(vehicles)} vehicles to stops...")
    matched_count = 0
    unmatched_count = 0
    arrivals = []
    
    for i, vehicle in enumerate(vehicles):
        # Progress indicator every 50 vehicles
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(vehicles)} vehicles...")
        
        # Match vehicle to stop using TransXChange
        match_result = match_vehicle_to_stop(vehicle)
        
        if match_result['matched']:
            matched_count += 1
            arrivals.append({
                'vehicle_id': match_result['vehicle_id'],
                'route_name': match_result['route_name'],
                'naptan_id': match_result['naptan_id'],
                'timestamp': match_result['timestamp'],
                'distance_m': match_result['distance_m']
            })
        else:
            unmatched_count += 1
    
    # Store arrivals in database
    if arrivals:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Create arrivals table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_arrivals (
                id SERIAL PRIMARY KEY,
                vehicle_id TEXT NOT NULL,
                route_name TEXT NOT NULL,
                naptan_id TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                distance_m FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_arrivals_route_stop 
            ON vehicle_arrivals(route_name, naptan_id, timestamp);
            
            CREATE INDEX IF NOT EXISTS idx_arrivals_timestamp 
            ON vehicle_arrivals(timestamp);
        """)
        
        # Insert arrivals
        values = [
            (a['vehicle_id'], a['route_name'], a['naptan_id'], 
             a['timestamp'], a['distance_m'])
            for a in arrivals
        ]
        
        execute_batch(cur, """
            INSERT INTO vehicle_arrivals 
            (vehicle_id, route_name, naptan_id, timestamp, distance_m)
            VALUES (%s, %s, %s, %s, %s)
        """, values, page_size=500)
        
        conn.commit()
        cur.close()
        conn.close()
    
    print(f"Matched: {matched_count}, Unmatched: {unmatched_count}, Arrivals recorded: {len(arrivals)}")
    return matched_count, unmatched_count

def poll_and_ingest():
    """Main polling function - called by Prefect every 10 seconds"""
    print(f"[{datetime.now()}] Polling BODS API...")
    
    # Fetch vehicle positions
    vehicles = fetch_vehicle_positions()
    print(f"Fetched {len(vehicles)} vehicle positions")
    
    if not vehicles:
        return
    
    # Store raw positions (staging) - NO matching here, done in analysis flow
    store_vehicle_positions(vehicles)
    print(f"Stored {len(vehicles)} positions (unanalyzed)")
    
    print(f"Poll complete")

if __name__ == "__main__":
    # Test run
    poll_and_ingest()
