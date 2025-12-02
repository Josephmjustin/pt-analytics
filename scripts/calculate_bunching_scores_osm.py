"""
OSM-based Bunching Score Calculator
Uses OSM stops instead of GTFS Static for spatial matching
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
    """Calculate bunching scores using OSM stops (no trip_id dependency)"""
    
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
        
        # Run bunching analysis with OSM stops
        analysis_query = """
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
              ON ST_DWithin(vp.geom::geography, os.location::geography, 100)
            WHERE vp.route_id IS NOT NULL
        ),
        arrivals_only AS (
            SELECT *
            FROM stop_arrivals
            WHERE distance_meters < 100 AND ping_number = 1
        ),
        headways AS (
            SELECT 
                stop_id,
                stop_name,
                arrival_time,
                arrival_time - LAG(arrival_time) OVER (
                    PARTITION BY stop_id 
                    ORDER BY arrival_time
                ) as headway_actual,
                EXTRACT(EPOCH FROM (
                    arrival_time - LAG(arrival_time) OVER (
                        PARTITION BY stop_id 
                        ORDER BY arrival_time
                    )
                ))/60 as headway_minutes
            FROM arrivals_only
        )
        SELECT 
            stop_id,
            stop_name,
            COUNT(*) as total_arrivals,
            COUNT(*) FILTER (WHERE headway_minutes < 5) as bunched_count,
            ROUND(AVG(headway_minutes)::numeric, 2) as avg_headway_minutes,
            ROUND(MIN(headway_minutes)::numeric, 2) as min_headway_minutes,
            ROUND(MAX(headway_minutes)::numeric, 2) as max_headway_minutes,
            ROUND(
                (COUNT(*) FILTER (WHERE headway_minutes < 5)::numeric / COUNT(*)::numeric * 100), 
                2
            ) as bunching_rate_pct
        FROM headways
        WHERE headway_minutes IS NOT NULL
        GROUP BY stop_id, stop_name
        HAVING COUNT(*) >= 3
        ORDER BY bunching_rate_pct DESC;
        """
        
        print("Running OSM-based bunching analysis...")
        cur.execute(analysis_query)
        results = cur.fetchall()
        
        if not results:
            print("No bunching scores calculated (insufficient data)")
            return
        
        # Insert scores into bunching_scores table
        analysis_timestamp = datetime.now()
        
        insert_data = [
            (
                str(row[0]),  # stop_id (OSM ID as string)
                row[1],  # stop_name
                analysis_timestamp,
                row[2],  # total_arrivals
                row[3],  # bunched_count
                row[7],  # bunching_rate_pct
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
        print(f"\nTop 10 stops by bunching rate:")
        for row in results[:10]:
            print(f"  {row[1]}: {row[7]:.1f}% bunching ({row[2]} arrivals)")
        
    except Exception as e:
        print(f"Error calculating bunching scores: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    calculate_bunching_scores_osm()
