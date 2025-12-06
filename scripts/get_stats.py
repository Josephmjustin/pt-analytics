"""
Get Updated Database Statistics
Run this after bbox changes to update README
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

def table_exists(cur, table_name):
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = %s
        )
    """, (table_name,))
    return cur.fetchone()[0]

def get_stats():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("\n" + "="*60)
    print("PT ANALYTICS - DATABASE STATISTICS")
    print("="*60 + "\n")
    
    # Vehicle positions count
    cur.execute("SELECT COUNT(*) FROM vehicle_positions")
    vehicle_count = cur.fetchone()[0]
    print(f"Vehicle Positions: {vehicle_count:,}")
    
    # OSM stops count
    cur.execute("SELECT COUNT(*) FROM osm_stops")
    stop_count = cur.fetchone()[0]
    print(f"OSM Stops: {stop_count:,}")
    
    # Stops with arrivals (if table exists)
    if table_exists(cur, 'stop_arrivals'):
        cur.execute("""
            SELECT COUNT(DISTINCT stop_id) 
            FROM stop_arrivals
        """)
        active_stops = cur.fetchone()[0]
        print(f"Stops with Arrivals: {active_stops:,}")
        print(f"Coverage: {(active_stops/stop_count*100):.1f}%\n")
        
        # Stop arrivals count
        cur.execute("SELECT COUNT(*) FROM stop_arrivals")
        arrival_count = cur.fetchone()[0]
        print(f"Stop Arrivals: {arrival_count:,}")
    else:
        print("Stops with Arrivals: N/A (table not created yet)")
        active_stops = 0
        arrival_count = 0
    
    # Bunching events (if table exists)
    if table_exists(cur, 'bunching_events'):
        cur.execute("SELECT COUNT(*) FROM bunching_events")
        bunching_count = cur.fetchone()[0]
        print(f"Bunching Events: {bunching_count:,}\n")
    else:
        print("Bunching Events: N/A (table not created yet)\n")
        bunching_count = 0
    
    # Bunching scores (alternative table)
    if table_exists(cur, 'bunching_scores'):
        cur.execute("SELECT COUNT(*) FROM bunching_scores")
        score_count = cur.fetchone()[0]
        print(f"Bunching Score Records: {score_count:,}")
        
        cur.execute("SELECT COUNT(DISTINCT stop_id) FROM bunching_scores")
        analyzed_stops = cur.fetchone()[0]
        print(f"Stops Analyzed: {analyzed_stops:,}\n")
    else:
        analyzed_stops = 0
    
    # Database size
    cur.execute("""
        SELECT pg_size_pretty(pg_database_size(current_database()))
    """)
    db_size = cur.fetchone()[0]
    print(f"Database Size: {db_size}\n")
    
    # Date range
    cur.execute("""
        SELECT 
            MIN(timestamp)::date as earliest,
            MAX(timestamp)::date as latest,
            MAX(timestamp) - MIN(timestamp) as duration
        FROM vehicle_positions
    """)
    earliest, latest, duration = cur.fetchone()
    print(f"Data Range: {earliest} to {latest}")
    print(f"Duration: {duration}\n")
    
    # Routes analyzed
    cur.execute("""
        SELECT COUNT(DISTINCT route_id) 
        FROM vehicle_positions 
        WHERE route_id IS NOT NULL
    """)
    route_count = cur.fetchone()[0]
    print(f"Routes Analyzed: {route_count:,}\n")
    
    # Unique vehicles
    cur.execute("""
        SELECT COUNT(DISTINCT vehicle_id)
        FROM vehicle_positions
    """)
    vehicle_unique = cur.fetchone()[0]
    print(f"Unique Vehicles: {vehicle_unique:,}\n")
    
    print("="*60)
    print("README UPDATE SNIPPETS")
    print("="*60 + "\n")
    
    if vehicle_count >= 1000000:
        vol_str = f"{vehicle_count/1000000:.1f}M+"
    else:
        vol_str = f"{vehicle_count:,}"
    
    coverage = analyzed_stops if analyzed_stops > 0 else active_stops
    if coverage == 0:
        coverage = "TBD"
    
    print(f"- **Data Volume:** {vol_str} vehicle positions analyzed")
    print(f"- **Coverage:** {coverage} stops across Liverpool")
    print(f"- **Storage:** {db_size}")
    print(f"- **Routes:** {route_count}+ active routes")
    
    if stop_count > 0 and coverage != "TBD":
        print(f"- **Stop Coverage:** {(coverage/stop_count*100):.1f}% ({coverage}/{stop_count} stops)")
    
    print(f"\nExpanded bbox now tracking {stop_count:,} OSM stops")
    print(f"(up from 251 stops in original Liverpool city center bbox)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    get_stats()
