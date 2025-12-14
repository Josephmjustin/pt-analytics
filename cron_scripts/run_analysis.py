#!/usr/bin/env python3
"""
Standalone analysis script for cron
Runs complete analysis pipeline with SIRI-VM direction support:
1. Detect stops & match to TransXChange
2. Calculate bunching (with direction)
3. Aggregate to running averages
4. Cleanup old data
"""
import sys
import os
from datetime import datetime

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.append(os.path.join(project_root, 'scripts'))

from src.processing.stop_detector import find_stop_events
from src.processing.vehicle_matcher import match_vehicle_to_stop
from src.api.database import get_db_connection
from psycopg2.extras import execute_batch, RealDictCursor

try:
    from scripts.calculate_bunching_from_arrivals import calculate_bunching_from_arrivals
    from scripts.aggregate_scores import aggregate_scores
    from scripts.aggregate_route_headways import aggregate_route_headways
    from scripts.cleanup_old_data import cleanup_old_data
    HAS_ALL_MODULES = True
except ImportError as e:
    HAS_ALL_MODULES = False
    print(f"Warning: Missing module - {e}")

def detect_and_match_stops():
    """Find stop events and match to TransXChange stops"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Fetch unanalyzed positions with direction from SIRI-VM
    cur.execute("""
        SELECT 
            vehicle_id,
            route_id,
            route_name,
            direction,
            operator,
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
    
    # Detect stop events
    stop_events = find_stop_events(positions)
    print(f"Detected {len(stop_events)} stop events")
    
    if not stop_events:
        # Mark as analyzed even if no stops detected
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
        
        match_result = match_vehicle_to_stop(stop_event)
        
        if match_result['matched']:
            matched_count += 1
            arrivals.append({
                'vehicle_id': match_result['vehicle_id'],
                'route_name': match_result['route_name'],
                'direction': match_result.get('direction'),  # Direction from SIRI-VM
                'naptan_id': match_result['naptan_id'],
                'timestamp': match_result['timestamp'],
                'distance_m': match_result['distance_m'],
                'dwell_time_seconds': stop_event.get('dwell_time_seconds', 0)
            })
    
    print(f"Matched {matched_count}/{len(stop_events)} stop events to stops")
    
    # Store arrivals with direction
    if arrivals:
        # Ensure table exists with direction column
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_arrivals (
                id SERIAL PRIMARY KEY,
                vehicle_id TEXT NOT NULL,
                route_name TEXT NOT NULL,
                direction TEXT,
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
            
            CREATE INDEX IF NOT EXISTS idx_arrivals_direction
            ON vehicle_arrivals(direction);
            
            CREATE INDEX IF NOT EXISTS idx_arrivals_route_dir
            ON vehicle_arrivals(route_name, direction);
        """)
        
        # Insert arrivals with direction
        values = [
            (a['vehicle_id'], a['route_name'], a['direction'],
             a['naptan_id'], a['timestamp'], a['distance_m'], a['dwell_time_seconds'])
            for a in arrivals
        ]
        
        execute_batch(cur, """
            INSERT INTO vehicle_arrivals 
            (vehicle_id, route_name, direction, naptan_id, timestamp, distance_m, dwell_time_seconds)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, values, page_size=500)
        
        print(f"Recorded {len(arrivals)} arrivals")
        
        # Show direction coverage
        with_direction = sum(1 for a in arrivals if a['direction'] is not None)
        print(f"  Arrivals with direction: {with_direction}/{len(arrivals)} ({100*with_direction/len(arrivals):.1f}%)")
    
    # Mark positions as analyzed
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

def run_analysis():
    """Main analysis function"""
    print(f"[{datetime.now()}] Starting analysis pipeline...")
    print("="*60)
    
    # Step 1: Detect stops and match
    stop_events, matched = detect_and_match_stops()
    print(f"Step 1: {stop_events} stops detected, {matched} matched")
    
    if matched == 0:
        print("No matched stops - skipping remaining steps")
        return
    
    if not HAS_ALL_MODULES:
        print("Missing modules - skipping calculations")
        return
    
    # Step 2: Calculate bunching (now with direction)
    print("Step 2: Calculating bunching...")
    calculate_bunching_from_arrivals()
    
    # Step 3: Aggregate
    print("Step 3: Aggregating patterns...")
    aggregate_scores()
    aggregate_route_headways()
    
    # Step 4: Cleanup
    print("Step 4: Cleaning up...")
    cleanup_old_data()  # Now uses smart cleanup logic
    
    # Cleanup old arrivals
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM vehicle_arrivals
        WHERE timestamp < NOW() - INTERVAL '1 hour'
    """)
    deleted_arrivals = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"Deleted {deleted_arrivals} old arrivals")
    print("="*60)
    print(f"Complete at {datetime.now()}")
    print(f"Summary: {stop_events} stops, {matched} matched")

if __name__ == "__main__":
    try:
        run_analysis()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)