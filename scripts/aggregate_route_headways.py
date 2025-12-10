"""
Route Headway Baseline Aggregator - TransXChange Version with Hourly Patterns
Calculates both overall and hour-specific baselines to handle peak/off-peak variations
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
    Calculate and store route-level headway baselines from vehicle_arrivals.
    Calculates BOTH overall baselines AND hourly baselines for peak/off-peak detection.
    """
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        print("Calculating route headway baselines from vehicle_arrivals...")
        
        # Calculate OVERALL baselines (existing logic)
        cur.execute("""
        WITH route_headways AS (
            SELECT 
                va.naptan_id as stop_id,
                ts.stop_name,
                va.route_name,
                EXTRACT(EPOCH FROM (
                    va.timestamp - LAG(va.timestamp) OVER (
                        PARTITION BY va.naptan_id, va.route_name 
                        ORDER BY va.timestamp
                    )
                ))/60 as headway_minutes
            FROM vehicle_arrivals va
            JOIN txc_stops ts ON va.naptan_id = ts.naptan_id
            WHERE va.timestamp >= NOW() - INTERVAL '30 minutes'
        ),
        current_stats AS (
            SELECT 
                route_name,
                stop_id,
                stop_name,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY headway_minutes) as median_headway,
                AVG(headway_minutes) as avg_headway,
                COUNT(*) as new_observations
            FROM route_headways
            WHERE headway_minutes IS NOT NULL
              AND headway_minutes > 1      -- Must be > 1 minute
              AND headway_minutes < 60     -- Must be < 60 minutes (realistic service)
            GROUP BY route_name, stop_id, stop_name
            HAVING COUNT(*) >= 2  -- Need at least 2 valid headways
        )
        INSERT INTO route_headway_baselines (
            route_id, stop_id, stop_name,
            median_headway_minutes, avg_headway_minutes, 
            observation_count, last_updated
        )
        SELECT 
            route_name as route_id,
            stop_id,
            stop_name,
            median_headway,
            avg_headway,
            new_observations,
            NOW()
        FROM current_stats
        ON CONFLICT (route_id, stop_id) DO UPDATE SET
            median_headway_minutes = route_headway_baselines.median_headway_minutes * 0.7 + EXCLUDED.median_headway_minutes * 0.3,
            avg_headway_minutes = route_headway_baselines.avg_headway_minutes * 0.7 + EXCLUDED.avg_headway_minutes * 0.3,
            observation_count = route_headway_baselines.observation_count + EXCLUDED.observation_count,
            last_updated = NOW()
        """)
        
        overall_updated = cur.rowcount
        conn.commit()
        
        # Calculate HOURLY baselines (new logic)
        print("Calculating hourly baselines...")
        cur.execute("""
        WITH route_headways_hourly AS (
            SELECT 
                va.naptan_id as stop_id,
                ts.stop_name,
                va.route_name,
                EXTRACT(HOUR FROM va.timestamp) as hour_of_day,
                EXTRACT(EPOCH FROM (
                    va.timestamp - LAG(va.timestamp) OVER (
                        PARTITION BY va.naptan_id, va.route_name, EXTRACT(HOUR FROM va.timestamp)
                        ORDER BY va.timestamp
                    )
                ))/60 as headway_minutes
            FROM vehicle_arrivals va
            JOIN txc_stops ts ON va.naptan_id = ts.naptan_id
            WHERE va.timestamp >= NOW() - INTERVAL '7 days'  -- Look at last week for hourly patterns
        ),
        hourly_stats AS (
            SELECT 
                route_name,
                stop_id,
                stop_name,
                hour_of_day,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY headway_minutes) as median_headway,
                AVG(headway_minutes) as avg_headway,
                COUNT(*) as new_observations
            FROM route_headways_hourly
            WHERE headway_minutes IS NOT NULL
              AND headway_minutes > 1
              AND headway_minutes < 60
            GROUP BY route_name, stop_id, stop_name, hour_of_day
            HAVING COUNT(*) >= 2
        )
        INSERT INTO route_headway_baselines_hourly (
            route_id, stop_id, stop_name, hour_of_day,
            median_headway_minutes, avg_headway_minutes, 
            observation_count, last_updated
        )
        SELECT 
            route_name as route_id,
            stop_id,
            stop_name,
            hour_of_day::INTEGER,
            median_headway,
            avg_headway,
            new_observations,
            NOW()
        FROM hourly_stats
        ON CONFLICT (route_id, stop_id, hour_of_day) DO UPDATE SET
            median_headway_minutes = route_headway_baselines_hourly.median_headway_minutes * 0.7 + EXCLUDED.median_headway_minutes * 0.3,
            avg_headway_minutes = route_headway_baselines_hourly.avg_headway_minutes * 0.7 + EXCLUDED.avg_headway_minutes * 0.3,
            observation_count = route_headway_baselines_hourly.observation_count + EXCLUDED.observation_count,
            last_updated = NOW()
        """)
        
        hourly_updated = cur.rowcount
        conn.commit()
        
        # Show summary for overall baselines
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
        
        print(f"\n✓ Overall baselines: Updated {overall_updated}")
        if stats and stats[0] > 0:
            print(f"  Total: {stats[0]} baselines")
            print(f"  Routes: {stats[1]} unique routes")
            print(f"  Avg headway: {stats[2]} min (range: {stats[3]}-{stats[4]} min)")
        
        # Show summary for hourly baselines
        cur.execute("""
            SELECT 
                COUNT(*) as total_baselines,
                COUNT(DISTINCT route_id) as unique_routes,
                COUNT(DISTINCT hour_of_day) as unique_hours,
                ROUND(AVG(median_headway_minutes)::numeric, 1) as avg_median
            FROM route_headway_baselines_hourly
        """)
        hourly_stats = cur.fetchone()
        
        print(f"\n✓ Hourly baselines: Updated {hourly_updated}")
        if hourly_stats and hourly_stats[0] > 0:
            print(f"  Total: {hourly_stats[0]} hour-specific baselines")
            print(f"  Routes: {hourly_stats[1]} unique routes")
            print(f"  Hours covered: {hourly_stats[2]}/24")
            print(f"  Avg headway: {hourly_stats[3]} min")
        else:
            print("  No hourly baselines yet (need more data)")
        
    except Exception as e:
        print(f"Error aggregating route headways: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    aggregate_route_headways()
