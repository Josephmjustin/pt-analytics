"""
Calculate bunching scores from vehicle_arrivals (TransXChange-based)
Uses route-aware thresholds and learned headway patterns
"""

import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'pt_analytics'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD')
}

def calculate_bunching_from_arrivals():
    """
    Calculate bunching scores from vehicle_arrivals table
    Uses TransXChange route information and learned headway baselines
    """
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        print("Calculating bunching scores from vehicle arrivals...")
        
        # Get unprocessed arrivals (last 10 minutes)
        cur.execute("""
            WITH route_stop_arrivals AS (
                SELECT 
                    route_name,
                    naptan_id,
                    timestamp,
                    vehicle_id,
                    -- Calculate headway (time since previous arrival on same route-stop)
                    EXTRACT(EPOCH FROM (
                        timestamp - LAG(timestamp) OVER (
                            PARTITION BY route_name, naptan_id 
                            ORDER BY timestamp
                        )
                    ))/60 AS headway_minutes
                FROM vehicle_arrivals
                ORDER BY route_name, naptan_id, timestamp
            ),
            route_stop_stats AS (
                SELECT 
                    route_name,
                    naptan_id,
                    -- Get learned baseline headway (default to 10 min if not learned yet)
                    COALESCE(
                        (SELECT median_headway_minutes 
                         FROM route_headway_baselines rhb
                         JOIN gtfs_routes gr ON rhb.route_id = gr.route_id
                         WHERE gr.route_short_name = route_name
                           AND rhb.stop_id::TEXT = naptan_id
                         LIMIT 1),
                        10.0  -- Default for routes without baseline
                    ) AS expected_headway_minutes,
                    COUNT(*) AS total_arrivals,
                    COUNT(*) FILTER (WHERE headway_minutes IS NOT NULL) AS measured_headways,
                    -- Count bunched arrivals (< 50% of expected, min 2 min)
                    COUNT(*) FILTER (
                        WHERE headway_minutes < GREATEST(
                            COALESCE(
                                (SELECT median_headway_minutes * 0.5
                                 FROM route_headway_baselines rhb
                                 JOIN gtfs_routes gr ON rhb.route_id = gr.route_id
                                 WHERE gr.route_short_name = route_name
                                   AND rhb.stop_id::TEXT = naptan_id
                                 LIMIT 1),
                                5.0
                            ),
                            2.0  -- Minimum 2-minute floor
                        )
                    ) AS bunched_arrivals,
                    NOW() AS analysis_timestamp
                FROM route_stop_arrivals
                WHERE headway_minutes IS NOT NULL
                GROUP BY route_name, naptan_id
                HAVING COUNT(*) >= 2  -- Need at least 2 arrivals to calculate headway
            )
            INSERT INTO bunching_scores (
                stop_id,
                stop_name,
                bunching_rate_pct,
                total_arrivals,
                bunched_arrivals,
                expected_headway_minutes,
                analysis_timestamp,
                data_window_start,
                data_window_end
            )
            SELECT 
                rss.naptan_id AS stop_id,
                (SELECT stop_name FROM txc_stops WHERE naptan_id = rss.naptan_id) AS stop_name,
                CASE 
                    WHEN measured_headways > 0 
                    THEN ROUND((bunched_arrivals::numeric / measured_headways * 100), 1)
                    ELSE 0 
                END AS bunching_rate_pct,
                total_arrivals,
                bunched_arrivals,
                expected_headway_minutes,
                analysis_timestamp,
                NOW() - INTERVAL '10 minutes' AS data_window_start,
                NOW() AS data_window_end
            FROM route_stop_stats rss
            WHERE measured_headways > 0
        """)
        
        inserted = cur.rowcount
        conn.commit()
        
        if inserted == 0:
            print("No bunching scores calculated (need at least 2 arrivals per route-stop)")
            return
        
        print(f"✓ Calculated {inserted} bunching scores")
        
        # Show top bunching locations
        cur.execute("""
            SELECT 
                stop_name,
                bunching_rate_pct,
                total_arrivals,
                bunched_arrivals
            FROM bunching_scores
            WHERE analysis_timestamp >= NOW() - INTERVAL '1 minute'
            ORDER BY bunching_rate_pct DESC
            LIMIT 5
        """)
        
        top_stops = cur.fetchall()
        if top_stops:
            print("\nTop bunching locations this cycle:")
            for stop_name, rate, total, bunched in top_stops:
                print(f"  {stop_name}: {rate}% ({bunched}/{total} arrivals)")
        
    except Exception as e:
        print(f"Error calculating bunching: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    calculate_bunching_from_arrivals()
