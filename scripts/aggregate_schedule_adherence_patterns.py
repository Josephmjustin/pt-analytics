"""
Aggregate Schedule Adherence Patterns for SRI Platform
Populates schedule_adherence_patterns table

NOTE: Currently creates placeholder data
TODO: Integrate with GTFS/TransXChange scheduled times

Calculates:
- Average deviation from schedule (minutes)
- Standard deviation of deviations
- On-time percentage (within ±2 minutes)
- Early/late counts
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

def aggregate_schedule_adherence_patterns():
    """
    Calculate schedule adherence patterns
    
    CURRENT: Placeholder implementation - assumes no schedule data
    Sets all routes to neutral scores (0 deviation = on-time)
    
    FUTURE: Will integrate with TransXChange scheduled arrival times
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print(f"[{datetime.now()}] Aggregating schedule adherence patterns...")
        print("="*60)
        print("⚠ WARNING: Schedule data not yet integrated")
        print("Creating placeholder patterns (all on-time)")
        print()
        
        # For now, create patterns based on actual arrivals
        # When we have scheduled times, we'll calculate deviations
        query = """
        WITH arrival_patterns AS (
            SELECT 
                route_name,
                direction,
                COALESCE(operator, 'Unknown') as operator,
                naptan_id as stop_id,
                EXTRACT(YEAR FROM timestamp)::INT as year,
                EXTRACT(MONTH FROM timestamp)::INT as month,
                EXTRACT(DOW FROM timestamp)::INT as day_of_week,
                EXTRACT(HOUR FROM timestamp)::INT as hour,
                COUNT(*) as arrival_count
            FROM vehicle_arrivals
            WHERE direction IS NOT NULL
              AND timestamp >= NOW() - INTERVAL '7 days'
            GROUP BY route_name, direction, operator, naptan_id, 
                     year, month, day_of_week, hour
            HAVING COUNT(*) >= 3
        )
        INSERT INTO schedule_adherence_patterns (
            route_name, direction, operator, stop_id,
            year, month, day_of_week, hour,
            avg_deviation_minutes,
            std_deviation_minutes,
            median_deviation_minutes,
            on_time_count,
            early_count,
            late_count,
            on_time_percentage,
            observation_count,
            last_updated
        )
        SELECT 
            route_name, direction, operator, stop_id,
            year, month, day_of_week, hour,
            0.0,  -- Placeholder: no deviation data yet
            0.0,  -- Placeholder: no std dev
            0.0,  -- Placeholder: no median
            arrival_count,  -- Assume all on-time for now
            0,  -- No early data
            0,  -- No late data
            100.0,  -- Placeholder: 100% on-time
            arrival_count,
            NOW()
        FROM arrival_patterns
        ON CONFLICT (route_name, direction, operator, stop_id, year, month, day_of_week, hour)
        DO UPDATE SET
            on_time_count = schedule_adherence_patterns.on_time_count + EXCLUDED.on_time_count,
            observation_count = schedule_adherence_patterns.observation_count + EXCLUDED.observation_count,
            last_updated = NOW()
        """
        
        cur.execute(query)
        inserted = cur.rowcount
        conn.commit()
        
        print(f"✓ Upserted {inserted:,} schedule adherence pattern records (placeholder)")
        
        # Show summary
        cur.execute("""
            SELECT 
                COUNT(*) as total_patterns,
                COUNT(DISTINCT route_name) as unique_routes,
                COUNT(DISTINCT stop_id) as unique_stops
            FROM schedule_adherence_patterns
        """)
        
        stats = cur.fetchone()
        print(f"\nCurrent schedule_adherence_patterns state:")
        print(f"  Total patterns: {stats[0]:,}")
        print(f"  Unique routes: {stats[1]}")
        print(f"  Unique stops: {stats[2]}")
        print(f"  (All placeholder data - 100% on-time)")
        
        print("\n📋 TODO: Integrate TransXChange scheduled times")
        print("  1. Parse scheduled arrival times from TransXChange")
        print("  2. Calculate actual vs scheduled deviations")
        print("  3. Update this script to use real deviation data")
        
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
    aggregate_schedule_adherence_patterns()
