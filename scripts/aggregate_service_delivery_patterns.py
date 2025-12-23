"""
Aggregate Service Delivery Patterns for SRI Platform
Populates service_delivery_patterns table

Tracks service reliability:
- Scheduled vs completed trips
- Cancellation rates
- Partial trip completion

NOTE: Currently uses observed trips as proxy
TODO: Integrate with GTFS/TransXChange scheduled trip counts
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

def aggregate_service_delivery_patterns():
    """
    Calculate service delivery patterns
    
    CURRENT: Tracks observed trips (no cancellation data yet)
    Assumes all observed trips = completed trips
    
    FUTURE: Will compare against scheduled trips from TransXChange
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print(f"[{datetime.now()}] Aggregating service delivery patterns...")
        print("="*60)
        print("⚠ WARNING: Schedule data not yet integrated")
        print("Tracking observed trips only (no cancellation detection)")
        print()
        
        # Count unique vehicle trips by route/direction/operator/time
        query = """
        WITH trip_patterns AS (
            SELECT 
                route_name,
                direction,
                COALESCE(operator, 'Unknown') as operator,
                -- Use single representative timestamp to extract time dimensions
                EXTRACT(YEAR FROM MAX(timestamp))::INT as year,
                EXTRACT(MONTH FROM MAX(timestamp))::INT as month,
                EXTRACT(DOW FROM MAX(timestamp))::INT as day_of_week,
                EXTRACT(HOUR FROM MAX(timestamp))::INT as hour,
                -- Count unique vehicle-day combinations as "trips"
                COUNT(DISTINCT (vehicle_id, DATE(timestamp))) as observed_trips
            FROM vehicle_arrivals
            WHERE direction IS NOT NULL
              AND operator IS NOT NULL
              AND timestamp >= NOW() - INTERVAL '7 days'
            GROUP BY route_name, direction, COALESCE(operator, 'Unknown'),
                     DATE(timestamp), EXTRACT(HOUR FROM timestamp)
            HAVING COUNT(DISTINCT (vehicle_id, DATE(timestamp))) >= 1
        ),
        aggregated_patterns AS (
            SELECT 
                route_name,
                direction,
                operator,
                year,
                month,
                day_of_week,
                hour,
                SUM(observed_trips) as total_observed_trips
            FROM trip_patterns
            GROUP BY route_name, direction, operator, year, month, day_of_week, hour
        )
        INSERT INTO service_delivery_patterns (
            route_name, direction, operator,
            year, month, day_of_week, hour,
            scheduled_trips,
            completed_trips,
            cancelled_trips,
            partial_trips,
            service_delivery_rate,
            last_updated
        )
        SELECT 
            route_name, direction, operator,
            year, month, day_of_week, hour,
            total_observed_trips,  -- Placeholder: use observed as scheduled
            total_observed_trips,  -- All observed trips assumed completed
            0,  -- No cancellation data yet
            0,  -- No partial trip data yet
            100.0,  -- Placeholder: 100% delivery rate
            NOW()
        FROM aggregated_patterns
        ON CONFLICT (route_name, direction, operator, year, month, day_of_week, hour)
        DO UPDATE SET
            scheduled_trips = service_delivery_patterns.scheduled_trips + EXCLUDED.scheduled_trips,
            completed_trips = service_delivery_patterns.completed_trips + EXCLUDED.completed_trips,
            service_delivery_rate = 
                100.0 * service_delivery_patterns.completed_trips::FLOAT / 
                NULLIF(service_delivery_patterns.scheduled_trips, 0),
            last_updated = NOW()
        """
        
        cur.execute(query)
        inserted = cur.rowcount
        conn.commit()
        
        print(f"✓ Upserted {inserted:,} service delivery pattern records")
        
        # Show summary
        cur.execute("""
            SELECT 
                COUNT(*) as total_patterns,
                COUNT(DISTINCT route_name) as unique_routes,
                SUM(completed_trips) as total_completed_trips,
                SUM(cancelled_trips) as total_cancelled_trips,
                ROUND(AVG(service_delivery_rate)::numeric, 1) as avg_delivery_rate
            FROM service_delivery_patterns
        """)
        
        stats = cur.fetchone()
        print(f"\nCurrent service_delivery_patterns state:")
        print(f"  Total patterns: {stats[0]:,}")
        print(f"  Unique routes: {stats[1]}")
        print(f"  Total completed trips: {stats[2]:,}")
        print(f"  Total cancelled trips: {stats[3]:,}")
        print(f"  Avg delivery rate: {stats[4]}%")
        print(f"  (Placeholder data - actual scheduled trips unknown)")
        
        # Show routes by trip volume
        print(f"\nTop 5 routes by trip volume:")
        cur.execute("""
            SELECT 
                route_name,
                direction,
                operator,
                SUM(completed_trips) as total_trips
            FROM service_delivery_patterns
            GROUP BY route_name, direction, operator
            ORDER BY total_trips DESC
            LIMIT 5
        """)
        
        for row in cur.fetchall():
            print(f"  {row[0]} ({row[1]}) - {row[2]}: {row[3]} trips")
        
        print("\n📋 TODO: Integrate scheduled trip data")
        print("  1. Parse scheduled trips from TransXChange")
        print("  2. Compare observed vs scheduled to detect cancellations")
        print("  3. Track partial trips (started but not completed)")
        
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
    aggregate_service_delivery_patterns()