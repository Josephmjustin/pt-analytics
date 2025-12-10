"""
Calculate bunching scores BY ROUTE-STOP-HOUR
This is the core table for passenger-facing bunching predictions
"""

import psycopg2
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

def calculate_bunching_from_arrivals():
    """
    Calculate bunching scores grouped by ROUTE + STOP + HOUR.
    This allows route-specific bunching predictions per hour.
    """
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        print("Calculating route-stop-hour bunching scores...")
        
        cur.execute("""
            WITH route_stop_arrivals AS (
                SELECT 
                    route_name,
                    naptan_id,
                    timestamp,
                    EXTRACT(HOUR FROM timestamp)::INTEGER as hour_of_day,
                    EXTRACT(EPOCH FROM (
                        timestamp - LAG(timestamp) OVER (
                            PARTITION BY route_name, naptan_id 
                            ORDER BY timestamp
                        )
                    ))/60 AS headway_minutes
                FROM vehicle_arrivals
                ORDER BY route_name, naptan_id, timestamp
            ),
            arrivals_with_baseline AS (
                SELECT 
                    route_name,
                    naptan_id,
                    timestamp,
                    hour_of_day,
                    headway_minutes,
                    -- Get baseline for this specific route-stop-hour
                    COALESCE(
                        (SELECT median_headway_minutes 
                         FROM route_headway_baselines_hourly rhb
                         WHERE rhb.route_id = route_name
                           AND rhb.stop_id = naptan_id
                           AND rhb.hour_of_day = hour_of_day
                         LIMIT 1),
                        (SELECT median_headway_minutes 
                         FROM route_headway_baselines rhb
                         WHERE rhb.route_id = route_name
                           AND rhb.stop_id = naptan_id
                         LIMIT 1),
                        10.0
                    ) AS expected_headway_minutes,
                    -- Is this arrival bunched?
                    CASE 
                        WHEN headway_minutes < GREATEST(
                            COALESCE(
                                (SELECT median_headway_minutes * 0.5
                                 FROM route_headway_baselines_hourly rhb
                                 WHERE rhb.route_id = route_name
                                   AND rhb.stop_id = naptan_id
                                   AND rhb.hour_of_day = hour_of_day
                                 LIMIT 1),
                                (SELECT median_headway_minutes * 0.5
                                 FROM route_headway_baselines rhb
                                 WHERE rhb.route_id = route_name
                                   AND rhb.stop_id = naptan_id
                                 LIMIT 1),
                                5.0
                            ),
                            2.0
                        ) THEN 1
                        ELSE 0
                    END AS is_bunched
                FROM route_stop_arrivals
                WHERE headway_minutes IS NOT NULL
            ),
            route_stop_hour_stats AS (
                SELECT 
                    route_name,
                    naptan_id,
                    hour_of_day,
                    COUNT(*) + 1 AS total_arrivals,
                    COUNT(*) AS measured_headways,
                    AVG(headway_minutes) AS avg_headway,
                    AVG(expected_headway_minutes) AS avg_expected_headway,
                    SUM(is_bunched) AS bunched_arrivals
                FROM arrivals_with_baseline
                GROUP BY route_name, naptan_id, hour_of_day
                HAVING COUNT(*) >= 2  -- Need at least 2 headways per hour
            )
            INSERT INTO bunching_by_route_stop_hour (
                route_id,
                stop_id,
                hour_of_day,
                stop_name,
                bunching_rate_pct,
                avg_headway_minutes,
                expected_headway_minutes,
                total_arrivals,
                bunched_arrivals,
                observation_count,
                last_updated
            )
            SELECT 
                rsh.route_name AS route_id,
                rsh.naptan_id AS stop_id,
                rsh.hour_of_day,
                ts.stop_name,
                ROUND((bunched_arrivals::numeric / measured_headways * 100), 1) AS bunching_rate_pct,
                ROUND(avg_headway::numeric, 1) AS avg_headway_minutes,
                ROUND(avg_expected_headway::numeric, 1) AS expected_headway_minutes,
                total_arrivals,
                bunched_arrivals,
                measured_headways AS observation_count,
                NOW()
            FROM route_stop_hour_stats rsh
            LEFT JOIN txc_stops ts ON rsh.naptan_id = ts.naptan_id
            ON CONFLICT (route_id, stop_id, hour_of_day) DO UPDATE SET
                bunching_rate_pct = (bunching_by_route_stop_hour.bunching_rate_pct * 0.7 + EXCLUDED.bunching_rate_pct * 0.3),
                avg_headway_minutes = (bunching_by_route_stop_hour.avg_headway_minutes * 0.7 + EXCLUDED.avg_headway_minutes * 0.3),
                expected_headway_minutes = EXCLUDED.expected_headway_minutes,
                total_arrivals = bunching_by_route_stop_hour.total_arrivals + EXCLUDED.total_arrivals,
                bunched_arrivals = bunching_by_route_stop_hour.bunched_arrivals + EXCLUDED.bunched_arrivals,
                observation_count = bunching_by_route_stop_hour.observation_count + EXCLUDED.observation_count,
                last_updated = NOW()
        """)
        
        inserted = cur.rowcount
        conn.commit()
        
        print(f"✓ Updated {inserted} route-stop-hour records")
        
        # Show summary
        cur.execute("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT route_id) as unique_routes,
                COUNT(DISTINCT stop_id) as unique_stops,
                COUNT(DISTINCT hour_of_day) as hours_covered,
                ROUND(AVG(bunching_rate_pct)::numeric, 1) as avg_bunching_rate
            FROM bunching_by_route_stop_hour
        """)
        
        stats = cur.fetchone()
        if stats:
            print(f"\nCurrent state:")
            print(f"  Total records: {stats[0]}")
            print(f"  Unique routes: {stats[1]}")
            print(f"  Unique stops: {stats[2]}")
            print(f"  Hours covered: {stats[3]}/24")
            print(f"  Avg bunching: {stats[4]}%")
        
        # Show example: Route 26 at different hours
        cur.execute("""
            SELECT 
                route_id,
                stop_name,
                hour_of_day,
                bunching_rate_pct,
                expected_headway_minutes
            FROM bunching_by_route_stop_hour
            WHERE route_id = '26'
            ORDER BY stop_id, hour_of_day
            LIMIT 10
        """)
        
        examples = cur.fetchall()
        if examples:
            print(f"\nExample: Route 26 bunching by hour:")
            for route, stop, hour, rate, expected in examples:
                print(f"  {stop} @ {hour:02d}:00 → {rate}% bunching (expected {expected} min)")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    calculate_bunching_from_arrivals()
