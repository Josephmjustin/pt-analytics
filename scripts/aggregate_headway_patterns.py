"""
Aggregate Headway Patterns for SRI Platform
Populates headway_patterns table from vehicle_arrivals

Calculates:
- Median, avg, std, min, max headway
- Coefficient of variation
- Bunching rate (% < 50% of median)
- By route/direction/operator/stop/year/month/day/hour
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

def aggregate_headway_patterns():
    """
    Calculate headway patterns from vehicle_arrivals
    Aggregates by: route + direction + operator + stop + time dimensions
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print(f"[{datetime.now()}] Aggregating headway patterns...")
        print("="*60)
        
        # Calculate headways and aggregate into patterns
        query = """
        WITH arrival_headways AS (
            SELECT 
                route_name,
                direction,
                COALESCE(operator, 'Unknown') as operator,
                naptan_id as stop_id,
                timestamp,
                EXTRACT(YEAR FROM timestamp)::INT as year,
                EXTRACT(MONTH FROM timestamp)::INT as month,
                EXTRACT(DOW FROM timestamp)::INT as day_of_week,
                EXTRACT(HOUR FROM timestamp)::INT as hour,
                -- Calculate headway to previous bus on same route/direction/stop
                EXTRACT(EPOCH FROM (
                    timestamp - LAG(timestamp) OVER (
                        PARTITION BY route_name, direction, naptan_id 
                        ORDER BY timestamp
                    )
                ))/60.0 AS headway_minutes
            FROM vehicle_arrivals
            WHERE direction IS NOT NULL
              AND timestamp >= NOW() - INTERVAL '7 days'  -- Process last 7 days
        ),
        headway_stats AS (
            SELECT 
                route_name,
                direction,
                operator,
                stop_id,
                year,
                month,
                day_of_week,
                hour,
                -- Aggregate metrics
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY headway_minutes) as median_headway,
                AVG(headway_minutes) as avg_headway,
                STDDEV(headway_minutes) as std_headway,
                MIN(headway_minutes) as min_headway,
                MAX(headway_minutes) as max_headway,
                -- Coefficient of variation (normalized variability)
                CASE 
                    WHEN AVG(headway_minutes) > 0 
                    THEN STDDEV(headway_minutes) / AVG(headway_minutes)
                    ELSE NULL
                END as cv,
                -- Bunching rate: % of headways < 50% of median
                100.0 * COUNT(*) FILTER (
                    WHERE headway_minutes < PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY headway_minutes) * 0.5
                ) / COUNT(*) as bunching_rate,
                COUNT(*) as observation_count
            FROM arrival_headways
            WHERE headway_minutes IS NOT NULL
              AND headway_minutes > 0  -- Exclude invalid headways
              AND headway_minutes < 120  -- Exclude gaps > 2 hours
            GROUP BY route_name, direction, operator, stop_id, year, month, day_of_week, hour
            HAVING COUNT(*) >= 3  -- Need at least 3 observations
        )
        INSERT INTO headway_patterns (
            route_name, direction, operator, stop_id,
            year, month, day_of_week, hour,
            median_headway_minutes, avg_headway_minutes, std_headway_minutes,
            min_headway_minutes, max_headway_minutes,
            coefficient_of_variation, bunching_rate, observation_count,
            last_updated
        )
        SELECT 
            route_name, direction, operator, stop_id,
            year, month, day_of_week, hour,
            ROUND(median_headway::numeric, 2),
            ROUND(avg_headway::numeric, 2),
            ROUND(std_headway::numeric, 2),
            ROUND(min_headway::numeric, 2),
            ROUND(max_headway::numeric, 2),
            ROUND(cv::numeric, 4),
            ROUND(bunching_rate::numeric, 2),
            observation_count,
            NOW()
        FROM headway_stats
        ON CONFLICT (route_name, direction, operator, stop_id, year, month, day_of_week, hour)
        DO UPDATE SET
            median_headway_minutes = EXCLUDED.median_headway_minutes,
            avg_headway_minutes = EXCLUDED.avg_headway_minutes,
            std_headway_minutes = EXCLUDED.std_headway_minutes,
            min_headway_minutes = EXCLUDED.min_headway_minutes,
            max_headway_minutes = EXCLUDED.max_headway_minutes,
            coefficient_of_variation = EXCLUDED.coefficient_of_variation,
            bunching_rate = EXCLUDED.bunching_rate,
            observation_count = headway_patterns.observation_count + EXCLUDED.observation_count,
            last_updated = NOW()
        """
        
        cur.execute(query)
        inserted = cur.rowcount
        conn.commit()
        
        print(f"✓ Upserted {inserted:,} headway pattern records")
        
        # Show summary stats
        cur.execute("""
            SELECT 
                COUNT(*) as total_patterns,
                COUNT(DISTINCT route_name) as unique_routes,
                COUNT(DISTINCT stop_id) as unique_stops,
                COUNT(DISTINCT (route_name, direction, operator)) as unique_services,
                ROUND(AVG(median_headway_minutes)::numeric, 1) as avg_median_headway,
                ROUND(AVG(coefficient_of_variation)::numeric, 3) as avg_cv,
                ROUND(AVG(bunching_rate)::numeric, 1) as avg_bunching_rate
            FROM headway_patterns
        """)
        
        stats = cur.fetchone()
        print(f"\nCurrent headway_patterns state:")
        print(f"  Total patterns: {stats[0]:,}")
        print(f"  Unique routes: {stats[1]}")
        print(f"  Unique stops: {stats[2]}")
        print(f"  Unique services: {stats[3]}")
        print(f"  Avg median headway: {stats[4]} min")
        print(f"  Avg CV: {stats[5]}")
        print(f"  Avg bunching rate: {stats[6]}%")
        
        # Show top 5 routes by bunching
        print(f"\nTop 5 routes by bunching rate:")
        cur.execute("""
            SELECT 
                route_name,
                direction,
                operator,
                ROUND(AVG(bunching_rate)::numeric, 1) as avg_bunching,
                COUNT(*) as pattern_count
            FROM headway_patterns
            GROUP BY route_name, direction, operator
            ORDER BY avg_bunching DESC
            LIMIT 5
        """)
        
        for row in cur.fetchall():
            print(f"  {row[0]} ({row[1]}) - {row[2]}: {row[3]}% bunching ({row[4]} patterns)")
        
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
    aggregate_headway_patterns()
