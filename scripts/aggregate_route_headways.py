"""
Route Headway Baseline Aggregator
Maintains running statistics of route-level headways
This preserves route behavior patterns even after raw data cleanup
"""

import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'pt_analytics'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD')
}

def aggregate_route_headways():
    """
    Calculate and store route-level headway baselines.
    Uses incremental averaging to maintain history.
    """
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        print("Calculating route headway baselines...")
        
        # Calculate current headways from recent data
        cur.execute("""
        WITH stop_arrivals AS (
            SELECT 
                vp.vehicle_id,
                vp.route_id,
                vp.timestamp as arrival_time,
                os.osm_id as stop_id,
                os.name as stop_name,
                ST_Distance(vp.geom::geography, os.location::geography) as distance_meters,
                ROW_NUMBER() OVER (
                    PARTITION BY vp.vehicle_id, vp.route_id, os.osm_id 
                    ORDER BY vp.timestamp
                ) as ping_number
            FROM vehicle_positions vp
            JOIN osm_stops os 
              ON ST_DWithin(vp.geom::geography, os.location::geography, 25)
            WHERE vp.route_id IS NOT NULL
        ),
        arrivals_only AS (
            SELECT *
            FROM stop_arrivals
            WHERE distance_meters < 25 AND ping_number = 1
        ),
        route_headways AS (
            SELECT 
                stop_id,
                stop_name,
                route_id,
                EXTRACT(EPOCH FROM (
                    arrival_time - LAG(arrival_time) OVER (
                        PARTITION BY stop_id, route_id 
                        ORDER BY arrival_time
                    )
                ))/60 as headway_minutes
            FROM arrivals_only
        ),
        current_stats AS (
            SELECT 
                route_id,
                stop_id,
                stop_name,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY headway_minutes) as median_headway,
                AVG(headway_minutes) as avg_headway,
                COUNT(*) as new_observations
            FROM route_headways
            WHERE headway_minutes IS NOT NULL
              AND headway_minutes > 0
            GROUP BY route_id, stop_id, stop_name
            HAVING COUNT(*) >= 1  -- Accept single observations to build baselines faster
        )
        INSERT INTO route_headway_baselines (
            route_id, stop_id, stop_name,
            median_headway_minutes, avg_headway_minutes, 
            observation_count, last_updated
        )
        SELECT 
            route_id,
            stop_id,
            stop_name,
            median_headway,
            avg_headway,
            new_observations,
            NOW()
        FROM current_stats
        ON CONFLICT (route_id, stop_id) DO UPDATE SET
            -- Running average with exponential weighting (70% old, 30% new)
            median_headway_minutes = route_headway_baselines.median_headway_minutes * 0.7 + EXCLUDED.median_headway_minutes * 0.3,
            avg_headway_minutes = route_headway_baselines.avg_headway_minutes * 0.7 + EXCLUDED.avg_headway_minutes * 0.3,
            observation_count = route_headway_baselines.observation_count + EXCLUDED.observation_count,
            last_updated = NOW()
        """)
        
        updated = cur.rowcount
        conn.commit()
        
        # Show summary
        cur.execute("""
            SELECT 
                COUNT(*) as total_baselines,
                COUNT(DISTINCT route_id) as unique_routes,
                ROUND(AVG(median_headway_minutes)::numeric, 1) as avg_median,
                ROUND(MIN(median_headway_minutes)::numeric, 1) as min_median,
                ROUND(MAX(median_headway_minutes)::numeric, 1) as max_median
            FROM route_headway_baselines
        """)
        stats = cur.fetchone()
        
        print(f"SUCCESS: Updated {updated} route-stop baselines")
        if stats and stats[0] > 0:
            print(f"\nBaseline summary:")
            print(f"  Total baselines: {stats[0]}")
            print(f"  Unique routes: {stats[1]}")
            print(f"  Avg median headway: {stats[2]} min")
            print(f"  Range: {stats[3]} - {stats[4]} min")
        
    except Exception as e:
        print(f"Error aggregating route headways: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    aggregate_route_headways()
