"""
OSM-based Bunching Score Calculator with Route-Aware Baselines
Uses stored route headway baselines for dynamic thresholds
Falls back to stop-level analysis if no baseline exists
"""

import os
import psycopg2
from psycopg2.extras import execute_values
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

def calculate_bunching_scores_osm():
    """
    Calculate bunching scores using route headway baselines.
    Bunching threshold = 0.5 * route_median, minimum 2 minutes
    Falls back to 2-minute fixed threshold if no baseline exists
    """
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Get data window
        cur.execute("""
            SELECT MIN(timestamp), MAX(timestamp) 
            FROM vehicle_positions
        """)
        data_window = cur.fetchone()
        
        if not data_window[0] or not data_window[1]:
            print("No data available for analysis")
            return
        
        window_start, window_end = data_window
        print(f"Analyzing data from {window_start} to {window_end}")
        
        # Calculate bunching using stored baselines
        analysis_query = f"""
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
              AND vp.timestamp >= '{window_start}'::timestamp
        ),
        arrivals_only AS (
            SELECT *
            FROM stop_arrivals
            WHERE distance_meters < 25 AND ping_number = 1
        ),
        stop_headways AS (
            -- Calculate headways at stop level
            SELECT 
                stop_id,
                stop_name,
                route_id,
                arrival_time,
                EXTRACT(EPOCH FROM (
                    arrival_time - LAG(arrival_time) OVER (
                        PARTITION BY stop_id 
                        ORDER BY arrival_time
                    )
                ))/60 as headway_minutes
            FROM arrivals_only
        ),
        bunching_detection AS (
            -- Use route baselines where available
            SELECT 
                sh.stop_id,
                sh.stop_name,
                sh.route_id,
                sh.headway_minutes,
                rhb.median_headway_minutes as route_baseline,
                -- Dynamic threshold: 50% of baseline, minimum 2 min
                COALESCE(
                    GREATEST(rhb.median_headway_minutes * 0.5, 2.0),
                    2.0  -- Fallback to 2 min if no baseline
                ) as bunching_threshold,
                CASE 
                    WHEN sh.headway_minutes < COALESCE(
                        GREATEST(rhb.median_headway_minutes * 0.5, 2.0),
                        2.0
                    ) THEN 1
                    ELSE 0
                END as is_bunched
            FROM stop_headways sh
            LEFT JOIN route_headway_baselines rhb 
              ON sh.route_id = rhb.route_id 
              AND sh.stop_id::TEXT = rhb.stop_id::TEXT
            WHERE sh.headway_minutes IS NOT NULL
        )
        SELECT 
            stop_id,
            stop_name,
            COUNT(*) as total_arrivals,
            SUM(is_bunched) as bunched_count,
            ROUND(AVG(headway_minutes)::numeric, 2) as avg_headway_minutes,
            ROUND(MIN(headway_minutes)::numeric, 2) as min_headway_minutes,
            ROUND(MAX(headway_minutes)::numeric, 2) as max_headway_minutes,
            ROUND(AVG(route_baseline)::numeric, 2) as avg_baseline,
            COUNT(*) FILTER (WHERE route_baseline IS NOT NULL) as with_baseline,
            ROUND(
                (SUM(is_bunched)::numeric / COUNT(*)::numeric * 100), 
                2
            ) as bunching_rate_pct
        FROM bunching_detection
        GROUP BY stop_id, stop_name
        HAVING COUNT(*) >= 2
        ORDER BY bunching_rate_pct DESC;
        """
        
        print("Running baseline-aware bunching analysis...")
        cur.execute(analysis_query)
        results = cur.fetchall()
        
        print(f"Query returned {len(results)} results")
        
        if not results:
            print("No bunching scores calculated (insufficient data)")
            return
        
        # Insert scores into bunching_scores table
        analysis_timestamp = datetime.now()
        
        insert_data = [
            (
                str(row[0]),  # stop_id
                row[1],  # stop_name
                analysis_timestamp,
                row[2],  # total_arrivals
                row[3],  # bunched_count
                row[9],  # bunching_rate_pct
                row[4],  # avg_headway_minutes
                row[5],  # min_headway_minutes
                row[6],  # max_headway_minutes
                window_start,
                window_end
            )
            for row in results
        ]
        
        execute_values(
            cur,
            """
            INSERT INTO bunching_scores (
                stop_id, stop_name, analysis_timestamp,
                total_arrivals, bunched_count, bunching_rate_pct,
                avg_headway_minutes, min_headway_minutes, max_headway_minutes,
                data_window_start, data_window_end
            ) VALUES %s
            ON CONFLICT (stop_id, analysis_timestamp) DO NOTHING
            """,
            insert_data
        )
        
        conn.commit()
        print(f"SUCCESS: Inserted {len(results)} bunching scores at {analysis_timestamp}")
        
        # Print summary
        print(f"\nBunching scores:")
        for row in results:
            baseline_info = f"baseline: {row[7]:.1f}min" if row[8] > 0 else "no baseline (using 2min)"
            print(f"  {row[1]}: {row[9]:.1f}% bunching")
            print(f"    ({row[2]} arrivals, {baseline_info})")
        
    except Exception as e:
        print(f"Error calculating bunching scores: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    calculate_bunching_scores_osm()
