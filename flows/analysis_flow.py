"""
Prefect Flow: PT Analytics Analysis Pipeline
Runs every 10 minutes:
1. Find stop events (vehicles stopped for 20+ seconds)
2. Match to TransXChange stops
3. Record arrivals
4. Calculate bunching scores
5. Mark positions as analyzed
"""

from prefect import flow, task
from datetime import timedelta, datetime
import sys
import os
import psycopg2
from psycopg2.extras import execute_batch, RealDictCursor

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.processing.stop_detector import find_stop_events
from src.processing.vehicle_matcher import match_vehicle_to_stop
from src.api.database import get_db_connection

# Import bunching calculation
try:
    from calculate_bunching_from_arrivals import calculate_bunching_from_arrivals
    HAS_BUNCHING_CALC = True
except ImportError:
    HAS_BUNCHING_CALC = False
    print("Warning: calculate_bunching_from_arrivals not found")

@task(name="Detect Stop Events", retries=2, retry_delay_seconds=30)
def detect_and_match_stops():
    """Find stop events and match to TransXChange stops"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get unanalyzed positions from last 10 minutes
    cur.execute("""
        SELECT 
            vehicle_id,
            route_id,
            latitude,
            longitude,
            timestamp
        FROM vehicle_positions
        WHERE analyzed = false
          AND timestamp >= NOW() - INTERVAL '10 minutes'
        ORDER BY vehicle_id, timestamp
    """)
    
    positions = cur.fetchall()
    print(f"Found {len(positions)} unanalyzed positions")
    
    if not positions:
        cur.close()
        conn.close()
        return 0, 0
    
    # Find stop events
    stop_events = find_stop_events(positions)
    print(f"Detected {len(stop_events)} stop events")
    
    if not stop_events:
        # Mark all as analyzed even if no stops detected
        cur.execute("""
            UPDATE vehicle_positions 
            SET analyzed = true 
            WHERE analyzed = false 
              AND timestamp >= NOW() - INTERVAL '10 minutes'
        """)
        conn.commit()
        cur.close()
        conn.close()
        return 0, 0
    
    # Match stop events to TransXChange stops
    matched_count = 0
    arrivals = []
    
    for i, stop_event in enumerate(stop_events):
        if (i + 1) % 10 == 0:
            print(f"  Matching {i + 1}/{len(stop_events)} stop events...")
        
        # Match using vehicle matcher
        match_result = match_vehicle_to_stop(stop_event)
        
        if match_result['matched']:
            matched_count += 1
            arrivals.append({
                'vehicle_id': match_result['vehicle_id'],
                'route_name': match_result['route_name'],
                'naptan_id': match_result['naptan_id'],
                'timestamp': match_result['timestamp'],
                'distance_m': match_result['distance_m'],
                'dwell_time_seconds': stop_event['dwell_time_seconds']
            })
    
    print(f"Matched {matched_count}/{len(stop_events)} stop events to stops")
    
    # Record arrivals
    if arrivals:
        # Create arrivals table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_arrivals (
                id SERIAL PRIMARY KEY,
                vehicle_id TEXT NOT NULL,
                route_name TEXT NOT NULL,
                naptan_id TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                distance_m FLOAT,
                dwell_time_seconds INTEGER,
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
             a['timestamp'], a['distance_m'], a['dwell_time_seconds'])
            for a in arrivals
        ]
        
        execute_batch(cur, """
            INSERT INTO vehicle_arrivals 
            (vehicle_id, route_name, naptan_id, timestamp, distance_m, dwell_time_seconds)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, values, page_size=500)
        
        print(f"Recorded {len(arrivals)} arrivals")
    
    # Mark all positions in this batch as analyzed
    cur.execute("""
        UPDATE vehicle_positions 
        SET analyzed = true 
        WHERE analyzed = false 
          AND timestamp >= NOW() - INTERVAL '10 minutes'
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    
    return len(stop_events), matched_count

@task(name="Calculate Bunching Scores", retries=2, retry_delay_seconds=30)
def run_bunching_analysis():
    """Calculate bunching from vehicle arrivals"""
    if not HAS_BUNCHING_CALC:
        print("Skipping bunching calculation (module not available)")
        return
    
    print("Calculating bunching scores from arrivals...")
    calculate_bunching_from_arrivals()
    print("Bunching calculation complete")

@flow(name="PT Analytics - Analysis Pipeline (10min)")
def analysis_pipeline():
    """Analysis pipeline - runs every 10 minutes"""
    print(f"[{datetime.now()}] Starting analysis pipeline...")
    
    # Step 1: Detect stops and match to TransXChange
    stop_events, matched = detect_and_match_stops()
    
    # Step 2: Calculate bunching if we have arrivals
    if matched > 0:
        run_bunching_analysis()
    else:
        print("No matched stops - skipping bunching calculation")
    
    print(f"Pipeline complete: {stop_events} stops detected, {matched} matched")

if __name__ == "__main__":
    analysis_pipeline()
