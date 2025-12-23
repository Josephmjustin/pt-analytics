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
        print("Using 30-day historical baseline as expected arrival times")
        print()
        
        # Calculate schedule adherence based on deviation from historical median
        query = """
        WITH historical_baseline AS (
            -- Calculate median arrival time per route/direction/stop/hour over 30 days
            SELECT 
                route_name,
                direction,
                COALESCE(operator, 'Unknown') as operator,
                naptan_id as stop_id,
                EXTRACT(HOUR FROM timestamp)::INT as hour,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM timestamp::TIME)) as median_arrival_seconds,
                COUNT(*) as baseline_observations
            FROM vehicle_arrivals
            WHERE direction IS NOT NULL
              AND timestamp >= NOW() - INTERVAL '30 days'
              AND timestamp < NOW() - INTERVAL '7 days'  -- Use older data for baseline
            GROUP BY route_name, direction, operator, naptan_id, EXTRACT(HOUR FROM timestamp)
            HAVING COUNT(*) >= 10  -- Need sufficient baseline data
        ),
        recent_arrivals_with_baseline AS (
            SELECT 
                va.route_name,
                va.direction,
                COALESCE(va.operator, 'Unknown') as operator,
                va.naptan_id as stop_id,
                EXTRACT(YEAR FROM va.timestamp)::INT as year,
                EXTRACT(MONTH FROM va.timestamp)::INT as month,
                EXTRACT(DOW FROM va.timestamp)::INT as day_of_week,
                EXTRACT(HOUR FROM va.timestamp)::INT as hour,
                va.timestamp,
                hb.median_arrival_seconds,
                -- Calculate deviation in minutes
                (EXTRACT(EPOCH FROM va.timestamp::TIME) - hb.median_arrival_seconds) / 60.0 as deviation_minutes
            FROM vehicle_arrivals va
            INNER JOIN historical_baseline hb 
                ON va.route_name = hb.route_name
                AND va.direction = hb.direction
                AND COALESCE(va.operator, 'Unknown') = hb.operator
                AND va.naptan_id = hb.stop_id
                AND EXTRACT(HOUR FROM va.timestamp) = hb.hour
            WHERE va.direction IS NOT NULL
              AND va.timestamp >= NOW() - INTERVAL '7 days'
        ),
        adherence_stats AS (
            SELECT 
                route_name,
                direction,
                operator,
                stop_id,
                year,
                month,
                day_of_week,
                hour,
                -- Calculate statistics
                AVG(deviation_minutes) as avg_deviation,
                STDDEV(deviation_minutes) as std_deviation,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY deviation_minutes) as median_deviation,
                -- Count on-time, early, late (within ±2 minutes = on-time)
                COUNT(*) FILTER (WHERE deviation_minutes BETWEEN -2 AND 2) as on_time_count,
                COUNT(*) FILTER (WHERE deviation_minutes < -2) as early_count,
                COUNT(*) FILTER (WHERE deviation_minutes > 2) as late_count,
                COUNT(*) as total_observations
            FROM recent_arrivals_with_baseline
            GROUP BY route_name, direction, operator, stop_id, year, month, day_of_week, hour
            HAVING COUNT(*) >= 5  -- Need sufficient recent data
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
            ROUND(avg_deviation::numeric, 2),
            ROUND(std_deviation::numeric, 2),
            ROUND(median_deviation::numeric, 2),
            on_time_count,
            early_count,
            late_count,
            ROUND((on_time_count::FLOAT / total_observations * 100)::numeric, 2) as on_time_pct,
            total_observations,
            NOW()
        FROM adherence_stats
        ON CONFLICT (route_name, direction, operator, stop_id, year, month, day_of_week, hour)
        DO UPDATE SET
            avg_deviation_minutes = EXCLUDED.avg_deviation_minutes,
            std_deviation_minutes = EXCLUDED.std_deviation_minutes,
            median_deviation_minutes = EXCLUDED.median_deviation_minutes,
            on_time_count = schedule_adherence_patterns.on_time_count + EXCLUDED.on_time_count,
            early_count = schedule_adherence_patterns.early_count + EXCLUDED.early_count,
            late_count = schedule_adherence_patterns.late_count + EXCLUDED.late_count,
            on_time_percentage = 
                (schedule_adherence_patterns.on_time_count + EXCLUDED.on_time_count)::FLOAT / 
                (schedule_adherence_patterns.observation_count + EXCLUDED.observation_count) * 100,
            observation_count = schedule_adherence_patterns.observation_count + EXCLUDED.observation_count,
            last_updated = NOW()
        """
        
        cur.execute(query)
        inserted = cur.rowcount
        conn.commit()
        
        print(f"✓ Upserted {inserted:,} schedule adherence pattern records (historical baseline)")
        
        # Show summary
        cur.execute("""
            SELECT 
                COUNT(*) as total_patterns,
                COUNT(DISTINCT route_name) as unique_routes,
                COUNT(DISTINCT stop_id) as unique_stops,
                ROUND(AVG(on_time_percentage)::numeric, 1) as avg_on_time_pct,
                ROUND(AVG(avg_deviation_minutes)::numeric, 1) as avg_deviation_min
            FROM schedule_adherence_patterns
        """)
        
        stats = cur.fetchone()
        print(f"\nCurrent schedule_adherence_patterns state:")
        print(f"  Total patterns: {stats[0]:,}")
        print(f"  Unique routes: {stats[1]}")
        print(f"  Unique stops: {stats[2]}")
        print(f"  Avg on-time rate: {stats[3]}% (±2 min threshold)")
        print(f"  Avg deviation: {stats[4]} minutes")
        
        # Show best and worst performers
        print(f"\nTop 5 most reliable routes (highest on-time %):")
        cur.execute("""
            SELECT 
                route_name,
                direction,
                operator,
                ROUND(AVG(on_time_percentage)::numeric, 1) as avg_on_time,
                COUNT(*) as pattern_count
            FROM schedule_adherence_patterns
            GROUP BY route_name, direction, operator
            ORDER BY avg_on_time DESC
            LIMIT 5
        """)
        
        for row in cur.fetchall():
            print(f"  {row[0]} ({row[1]}) - {row[2]}: {row[3]}% on-time")
        
        print(f"\nTop 5 least reliable routes (lowest on-time %):")
        cur.execute("""
            SELECT 
                route_name,
                direction,
                operator,
                ROUND(AVG(on_time_percentage)::numeric, 1) as avg_on_time,
                ROUND(AVG(avg_deviation_minutes)::numeric, 1) as avg_late_by
            FROM schedule_adherence_patterns
            GROUP BY route_name, direction, operator
            ORDER BY avg_on_time ASC
            LIMIT 5
        """)
        
        for row in cur.fetchall():
            print(f"  {row[0]} ({row[1]}) - {row[2]}: {row[3]}% on-time (avg {row[4]:+.1f} min)")
        
        print("\n📋 Methodology: Historical Pattern Baseline")
        print("  - Baseline: Median arrival time from previous 30 days")
        print("  - On-time: Within ±2 minutes of historical median")
        print("  - Enhancement: Can integrate TransXChange scheduled times later")
        
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