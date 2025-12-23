#!/usr/bin/env python3
"""
OPTIMIZED analysis script - 100x faster
- Fetches all stops once into memory
- Does matching in-memory (no network calls per event)
- Bulk inserts results
- Proper connection handling
"""
import sys
import os
from datetime import datetime
import fcntl
from math import radians, sin, cos, sqrt, atan2

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.append(os.path.join(project_root, 'scripts'))

from src.processing.stop_detector import find_stop_events
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

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two points"""
    R = 6371000  # Earth radius in meters
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

class StopMatcher:
    """In-memory stop matcher - loads once, matches fast"""
    
    def __init__(self, conn):
        """Load all route-stop mappings into memory"""
        print("Loading stops into memory...")
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Load all stops with their routes and directions
        cur.execute("""
            SELECT DISTINCT
                s.naptan_id,
                s.stop_name,
                s.latitude,
                s.longitude,
                rp.route_name,
                rp.direction
            FROM txc_stops s
            JOIN txc_pattern_stops ps ON s.naptan_id = ps.naptan_id
            JOIN txc_route_patterns rp ON ps.pattern_id = rp.pattern_id
            WHERE s.latitude IS NOT NULL 
              AND s.longitude IS NOT NULL
        """)
        
        # Build index: route_name -> direction -> [stops]
        self.route_stops = {}
        for row in cur.fetchall():
            route = row['route_name']
            direction = row['direction']
            
            if route not in self.route_stops:
                self.route_stops[route] = {}
            if direction not in self.route_stops[route]:
                self.route_stops[route][direction] = []
            
            self.route_stops[route][direction].append({
                'naptan_id': row['naptan_id'],
                'stop_name': row['stop_name'],
                'lat': float(row['latitude']),
                'lon': float(row['longitude'])
            })
        
        cur.close()
        
        total_routes = len(self.route_stops)
        total_stops = sum(len(stops) for dirs in self.route_stops.values() 
                         for stops in dirs.values())
        print(f"✓ Loaded {total_stops} stops across {total_routes} routes")
    
    def match(self, stop_event, radius_m=30.0):
        """Match stop event to nearest valid stop (in-memory, fast)"""
        vehicle_id = stop_event['vehicle_id']
        lat = stop_event['latitude']
        lon = stop_event['longitude']
        timestamp = stop_event.get('timestamp') or stop_event.get('stop_timestamp')
        route_name = stop_event.get('route_name')
        direction = stop_event.get('direction')
        
        if not route_name or route_name not in self.route_stops:
            return None
        
        # Get candidate stops for this route+direction
        candidates = []
        
        if direction and direction in self.route_stops[route_name]:
            candidates = self.route_stops[route_name][direction]
        elif direction is None:
            # No direction - check all directions for this route
            for dir_stops in self.route_stops[route_name].values():
                candidates.extend(dir_stops)
        
        if not candidates:
            return None
        
        # Find nearest stop within radius
        best_stop = None
        best_distance = radius_m
        
        for stop in candidates:
            distance = haversine_distance(lat, lon, stop['lat'], stop['lon'])
            if distance < best_distance:
                best_distance = distance
                best_stop = stop
        
        if best_stop:
            return {
                'vehicle_id': vehicle_id,
                'route_name': route_name,
                'direction': direction,
                'naptan_id': best_stop['naptan_id'],
                'stop_name': best_stop['stop_name'],
                'distance_m': round(best_distance, 1),
                'timestamp': timestamp,
                'matched': True
            }
        
        return None

def detect_and_match_stops():
    """Find stop events and match - OPTIMIZED VERSION"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Fetch unanalyzed positions
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
        
        # Detect stop events (in-memory, fast)
        stop_events = find_stop_events(positions)
        print(f"Detected {len(stop_events)} stop events")
        
        if not stop_events:
            cur.execute("UPDATE vehicle_positions SET analyzed = true WHERE analyzed = false")
            conn.commit()
            return 0, 0
        
        # Load stops into memory ONCE
        matcher = StopMatcher(conn)
        
        # Match all events (in-memory, no network calls!)
        print(f"Matching {len(stop_events)} events...")
        arrivals = []
        matched_count = 0
        
        for i, stop_event in enumerate(stop_events):
            if (i + 1) % 500 == 0:
                print(f"  Progress: {i + 1}/{len(stop_events)}")
            
            match_result = matcher.match(stop_event)
            
            if match_result:
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
        
        print(f"✓ Matched {matched_count}/{len(stop_events)} ({100*matched_count/len(stop_events):.1f}%)")
        
        # Bulk insert arrivals
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
                CREATE INDEX IF NOT EXISTS idx_arrivals_direction
                ON vehicle_arrivals(direction);
            """)
            
            values = [
                (a['vehicle_id'], a['route_name'], a['direction'],
                 a['naptan_id'], a['timestamp'], a['distance_m'], 
                 a['dwell_time_seconds']) 
                for a in arrivals
            ]
            
            execute_batch(cur, """
                INSERT INTO vehicle_arrivals 
                (vehicle_id, route_name, direction, naptan_id, timestamp, distance_m, dwell_time_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, values, page_size=1000)
            
            print(f"✓ Inserted {len(arrivals)} arrivals")
        
        # Mark ALL as analyzed
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
    """Main analysis with proper error handling"""
    print(f"[{datetime.now()}] Starting OPTIMIZED analysis...")
    print("="*60)
    
    try:
        stop_events, matched = detect_and_match_stops()
        print(f"✓ Analysis: {stop_events} stops detected, {matched} matched")
        
        if matched > 0 and HAS_ALL_MODULES:
            print("\nCalculating bunching scores...")
            calculate_bunching_from_arrivals()
            
            print("Aggregating patterns...")
            aggregate_scores()
            aggregate_route_headways()
            
            print("Cleaning up old data...")
            cleanup_old_data()
            
            # Cleanup old arrivals
            conn = None
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM vehicle_arrivals WHERE timestamp < NOW() - INTERVAL '1 hour'")
                deleted = cur.rowcount
                conn.commit()
                print(f"✓ Deleted {deleted} old arrivals")
            finally:
                if conn:
                    conn.close()
        
        print("="*60)
        print(f"✓ Complete at {datetime.now()}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    # Acquire lock
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