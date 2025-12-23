"""
Aggregate Journey Time Patterns for SRI Platform
Populates journey_time_patterns table

Calculates stop-to-stop journey times:
- Average, median, std journey time
- Coefficient of variation
- 85th percentile (planning threshold)
- By route/direction/operator/origin-destination/time
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

def aggregate_journey_time_patterns():
    """
    Calculate journey time patterns from consecutive stop arrivals
    Measures consistency of travel times between stops
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print(f"[{datetime.now()}] Aggregating journey time patterns...")
        print("="*60)
        
        # Calculate journey times between consecutive stops
        query = """
        WITH ordered_arrivals AS (
            SELECT 
                vehicle_id,
                route_name,
                direction,
                COALESCE(operator, 'Unknown') as operator,
                naptan_id as stop_id,
                timestamp,
                EXTRACT(YEAR FROM timestamp)::INT as year,
                EXTRACT(MONTH FROM timestamp)::INT as month,
                EXTRACT(DOW FROM timestamp)::INT as day_of_week,
                EXTRACT(HOUR FROM timestamp)::INT as hour,
                -- Get next stop for this vehicle on this trip
                LEAD(naptan_id) OVER (
                    PARTITION BY vehicle_id, route_name, direction, DATE(timestamp)
                    ORDER BY timestamp
                ) as next_stop_id,
                LEAD(timestamp) OVER (
                    PARTITION BY vehicle_id, route_name, direction, DATE(timestamp)
                    ORDER BY timestamp
                ) as next_timestamp
            FROM vehicle_arrivals
            WHERE direction IS NOT NULL
              AND timestamp >= NOW() - INTERVAL '7 days'
        ),
        journey_times AS (
            SELECT 
                route_name,
                direction,
                operator,
                stop_id as origin_stop_id,
                next_stop_id as destination_stop_id,
                year, month, day_of_week, hour,
                EXTRACT(EPOCH FROM (next_timestamp - timestamp))/60.0 as journey_minutes
            FROM ordered_arrivals
            WHERE next_stop_id IS NOT NULL
              AND next_timestamp IS NOT NULL
              AND next_timestamp > timestamp  -- Sanity check
              AND EXTRACT(EPOCH FROM (next_timestamp - timestamp))/60.0 BETWEEN 0.5 AND 60  -- 30s to 60min
        ),
        journey_stats AS (
            SELECT 
                route_name,
                direction,
                operator,
                origin_stop_id,
                destination_stop_id,
                year, month, day_of_week, hour,
                AVG(journey_minutes) as avg_journey,
                STDDEV(journey_minutes) as std_journey,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY journey_minutes) as median_journey,
                PERCENTILE_CONT(0.85) WITHIN GROUP (ORDER BY journey_minutes) as p85_journey,
                CASE 
                    WHEN AVG(journey_minutes) > 0 
                    THEN STDDEV(journey_minutes) / AVG(journey_minutes)
                    ELSE NULL
                END as cv,
                COUNT(*) as observation_count
            FROM journey_times
            GROUP BY route_name, direction, operator, 
                     origin_stop_id, destination_stop_id,
                     year, month, day_of_week, hour
            HAVING COUNT(*) >= 3  -- Need at least 3 observations
        )
        INSERT INTO journey_time_patterns (
            route_name, direction, operator, 
            origin_stop_id, destination_stop_id,
            year, month, day_of_week, hour,
            avg_journey_minutes,
            std_journey_minutes,
            median_journey_minutes,
            coefficient_of_variation,
            percentile_85_minutes,
            observation_count,
            last_updated
        )
        SELECT 
            route_name, direction, operator,
            origin_stop_id, destination_stop_id,
            year, month, day_of_week, hour,
            ROUND(avg_journey::numeric, 2),
            ROUND(std_journey::numeric, 2),
            ROUND(median_journey::numeric, 2),
            ROUND(cv::numeric, 4),
            ROUND(p85_journey::numeric, 2),
            observation_count,
            NOW()
        FROM journey_stats
        ON CONFLICT (route_name, direction, operator, origin_stop_id, destination_stop_id, 
                     year, month, day_of_week, hour)
        DO UPDATE SET
            avg_journey_minutes = EXCLUDED.avg_journey_minutes,
            std_journey_minutes = EXCLUDED.std_journey_minutes,
            median_journey_minutes = EXCLUDED.median_journey_minutes,
            coefficient_of_variation = EXCLUDED.coefficient_of_variation,
            percentile_85_minutes = EXCLUDED.percentile_85_minutes,
            observation_count = journey_time_patterns.observation_count + EXCLUDED.observation_count,
            last_updated = NOW()
        """
        
        cur.execute(query)
        inserted = cur.rowcount
        conn.commit()
        
        print(f"✓ Upserted {inserted:,} journey time pattern records")
        
        # Show summary stats
        cur.execute("""
            SELECT 
                COUNT(*) as total_patterns,
                COUNT(DISTINCT route_name) as unique_routes,
                COUNT(DISTINCT (origin_stop_id, destination_stop_id)) as unique_segments,
                ROUND(AVG(avg_journey_minutes)::numeric, 1) as avg_journey_time,
                ROUND(AVG(coefficient_of_variation)::numeric, 3) as avg_cv,
                ROUND(AVG(percentile_85_minutes / NULLIF(median_journey_minutes, 0))::numeric, 2) as avg_p85_ratio
            FROM journey_time_patterns
        """)
        
        stats = cur.fetchone()
        print(f"\nCurrent journey_time_patterns state:")
        print(f"  Total patterns: {stats[0]:,}")
        print(f"  Unique routes: {stats[1]}")
        print(f"  Unique segments: {stats[2]}")
        print(f"  Avg journey time: {stats[3]} min")
        print(f"  Avg CV: {stats[4]}")
        print(f"  Avg P85/Median ratio: {stats[5]}")
        
        # Show most variable segments
        print(f"\nTop 5 most variable segments (high CV):")
        cur.execute("""
            SELECT 
                route_name,
                direction,
                ROUND(AVG(coefficient_of_variation)::numeric, 3) as avg_cv,
                COUNT(*) as pattern_count
            FROM journey_time_patterns
            WHERE coefficient_of_variation IS NOT NULL
            GROUP BY route_name, direction
            ORDER BY avg_cv DESC
            LIMIT 5
        """)
        
        for row in cur.fetchall():
            print(f"  {row[0]} ({row[1]}): CV={row[2]} ({row[3]} patterns)")
        
        print("="*60)
        print(f"✓ Complete at {datetime.now()}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    aggregate_journey_time_patterns()
