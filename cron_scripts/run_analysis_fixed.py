#!/usr/bin/env python3
"""
Fixed analysis script with proper connection handling
"""
import sys
import os
from datetime import datetime
import fcntl

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

LOCK_FILE = '/tmp/pt_analysis.lock'

def detect_and_match_stops():
    """Find stop events - WITH PROPER CONNECTION HANDLING"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                vehicle_id, route_name, direction, operator,
                latitude, longitude, timestamp
            FROM vehicle_positions
            WHERE analyzed = false
            AND timestamp >= NOW() - INTERVAL '30 minutes'
            ORDER BY vehicle_id, timestamp
        """)
        
        positions = cur.fetchall()
        print(f"Found {len(positions)} unanalyzed positions")
        
        if not positions:
            cur.execute("UPDATE vehicle_positions SET analyzed = true WHERE analyzed = false")
            conn.commit()
            return 0, 0
        
        stop_events = find_stop_events(positions)
        print(f"Detected {len(stop_events)} stop events")
        
        if not stop_events:
            cur.execute("UPDATE vehicle_positions SET analyzed = true WHERE analyzed = false")
            conn.commit()
            return 0, 0
        
        # Match stops
        matched_count = 0
        arrivals = []
        
        for stop_event in stop_events:
            match_result = match_vehicle_to_stop(stop_event)
            if match_result['matched']:
                matched_count += 1
                arrivals.append({
                    'vehicle_id': match_result['vehicle_id'],
                    'route_name': match_result['route_name'],
                    'direction': match_result.get('direction'),
                    'naptan_id': match_result['naptan_id'],
                    'timestamp': match_result['timestamp'],
                    'distance_m': match_result['distance_m'],
                    'dwell_time_seconds': stop_event.get('dwell_time_seconds', 0)
                })
        
        print(f"Matched {matched_count}/{len(stop_events)}")
        
        # Store arrivals
        if arrivals:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vehicle_arrivals (
                    id SERIAL PRIMARY KEY,
                    vehicle_id TEXT, route_name TEXT, direction TEXT,
                    naptan_id TEXT, timestamp TIMESTAMP,
                    distance_m FLOAT, dwell_time_seconds INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_arrivals_route_stop 
                ON vehicle_arrivals(route_name, naptan_id, timestamp);
            """)
            
            values = [(a['vehicle_id'], a['route_name'], a['direction'],
                      a['naptan_id'], a['timestamp'], a['distance_m'], 
                      a['dwell_time_seconds']) for a in arrivals]
            
            execute_batch(cur, """
                INSERT INTO vehicle_arrivals 
                (vehicle_id, route_name, direction, naptan_id, timestamp, distance_m, dwell_time_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, values, page_size=500)
        
        # Mark as analyzed
        cur.execute("UPDATE vehicle_positions SET analyzed = true WHERE analyzed = false")
        conn.commit()
        
        return len(stop_events), matched_count
        
    except Exception as e:
        print(f"ERROR in detect_and_match: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
            print("✓ Connection closed")

def run_analysis():
    """Main with proper error handling"""
    print(f"[{datetime.now()}] Starting analysis...")
    
    try:
        stop_events, matched = detect_and_match_stops()
        print(f"✓ Detected: {stop_events} stops, {matched} matched")
        
        if matched > 0 and HAS_ALL_MODULES:
            print("Running bunching calculation...")
            calculate_bunching_from_arrivals()
            
            print("Running aggregation...")
            aggregate_scores()
            aggregate_route_headways()
            
            print("Running cleanup...")
            cleanup_old_data()
            
            # Cleanup old arrivals
            conn = None
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM vehicle_arrivals WHERE timestamp < NOW() - INTERVAL '1 hour'")
                conn.commit()
            finally:
                if conn:
                    conn.close()
        
        print(f"✓ Complete at {datetime.now()}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("Another analysis running. Exiting.")
        sys.exit(0)
    
    try:
        run_analysis()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()