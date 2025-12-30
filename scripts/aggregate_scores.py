"""
Aggregate bunching scores into running averages
UPDATED: Only aggregates if tables exist (post-migration compatibility)
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

def table_exists(cur, table_name):
    """Check if a table exists"""
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        )
    """, (table_name,))
    return cur.fetchone()[0]

def aggregate_scores():
    """
    Aggregate bunching data - skips if tables don't exist
    NOTE: After migration, only bunching_by_route_stop_hour and bunching_by_stop remain
    """
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Check which tables exist
        has_by_hour = table_exists(cur, 'bunching_by_hour')
        has_by_stop = table_exists(cur, 'bunching_by_stop')
        has_by_day = table_exists(cur, 'bunching_by_day')
        has_by_month = table_exists(cur, 'bunching_by_month')
        has_by_hour_day = table_exists(cur, 'bunching_by_hour_day')
        has_route_stop_hour = table_exists(cur, 'bunching_by_route_stop_hour')
        
        print(f"Bunching tables status:")
        print(f"  bunching_by_route_stop_hour: {'✓' if has_route_stop_hour else '✗'}")
        print(f"  bunching_by_hour: {'✓' if has_by_hour else '✗ (dropped in migration)'}")
        print(f"  bunching_by_stop: {'✓' if has_by_stop else '✗'}")
        print(f"  bunching_by_day: {'✓' if has_by_day else '✗ (dropped in migration)'}")
        print(f"  bunching_by_month: {'✓' if has_by_month else '✗ (dropped in migration)'}")
        print(f"  bunching_by_hour_day: {'✓' if has_by_hour_day else '✗ (dropped in migration)'}")
        
        if not has_route_stop_hour:
            print("\n⚠ Warning: bunching_by_route_stop_hour doesn't exist - skipping all bunching aggregation")
            return
        
        # Only aggregate to tables that exist
        updated_count = 0
        
        if has_by_hour:
            # Step 1: Aggregate route_stop_hour -> by_hour
            cur.execute("""
                INSERT INTO bunching_by_hour (stop_id, hour_of_day, avg_bunching_rate, total_count, last_updated)
                SELECT 
                    stop_id,
                    hour_of_day,
                    SUM(bunching_rate_pct * observation_count) / NULLIF(SUM(observation_count), 0) as avg_bunching_rate,
                    SUM(observation_count) as total_count,
                    MAX(last_updated) as last_updated
                FROM bunching_by_route_stop_hour
                WHERE last_updated > (
                    SELECT COALESCE(MAX(last_updated), '1970-01-01') 
                    FROM bunching_by_hour
                )
                GROUP BY stop_id, hour_of_day
                ON CONFLICT (stop_id, hour_of_day) 
                DO UPDATE SET
                    avg_bunching_rate = (
                        bunching_by_hour.avg_bunching_rate * bunching_by_hour.total_count + 
                        EXCLUDED.avg_bunching_rate * EXCLUDED.total_count
                    ) / (bunching_by_hour.total_count + EXCLUDED.total_count),
                    total_count = bunching_by_hour.total_count + EXCLUDED.total_count,
                    last_updated = GREATEST(bunching_by_hour.last_updated, EXCLUDED.last_updated)
            """)
            updated_hours = cur.rowcount
            conn.commit()
            print(f"✓ bunching_by_hour: Updated {updated_hours} records")
            updated_count += updated_hours
        
        if has_by_stop:
            # Step 2: Aggregate to bunching_by_stop
            if has_by_hour:
                # Aggregate from bunching_by_hour if it exists
                cur.execute("""
                    INSERT INTO bunching_by_stop (stop_id, stop_name, avg_bunching_rate, total_count, last_updated)
                    SELECT 
                        bh.stop_id,
                        ts.stop_name,
                        SUM(bh.avg_bunching_rate * bh.total_count) / NULLIF(SUM(bh.total_count), 0) as avg_bunching_rate,
                        SUM(bh.total_count) as total_count,
                        MAX(bh.last_updated) as last_updated
                    FROM bunching_by_hour bh
                    JOIN txc_stops ts ON bh.stop_id = ts.naptan_id
                    WHERE bh.last_updated > (
                        SELECT COALESCE(MAX(last_updated), '1970-01-01') 
                        FROM bunching_by_stop
                    )
                    GROUP BY bh.stop_id, ts.stop_name
                    ON CONFLICT (stop_id) 
                    DO UPDATE SET
                        avg_bunching_rate = (
                            bunching_by_stop.avg_bunching_rate * bunching_by_stop.total_count + 
                            EXCLUDED.avg_bunching_rate * EXCLUDED.total_count
                        ) / (bunching_by_stop.total_count + EXCLUDED.total_count),
                        total_count = bunching_by_stop.total_count + EXCLUDED.total_count,
                        last_updated = GREATEST(bunching_by_stop.last_updated, EXCLUDED.last_updated)
                """)
            else:
                # Aggregate directly from route_stop_hour
                cur.execute("""
                    INSERT INTO bunching_by_stop (stop_id, stop_name, avg_bunching_rate, total_count, last_updated)
                    SELECT 
                        brsh.stop_id,
                        ts.stop_name,
                        SUM(brsh.bunching_rate_pct * brsh.observation_count) / NULLIF(SUM(brsh.observation_count), 0) as avg_bunching_rate,
                        SUM(brsh.observation_count) as total_count,
                        MAX(brsh.last_updated) as last_updated
                    FROM bunching_by_route_stop_hour brsh
                    JOIN txc_stops ts ON brsh.stop_id = ts.naptan_id
                    WHERE brsh.last_updated > (
                        SELECT COALESCE(MAX(last_updated), '1970-01-01') 
                        FROM bunching_by_stop
                    )
                    GROUP BY brsh.stop_id, ts.stop_name
                    ON CONFLICT (stop_id) 
                    DO UPDATE SET
                        avg_bunching_rate = (
                            bunching_by_stop.avg_bunching_rate * bunching_by_stop.total_count + 
                            EXCLUDED.avg_bunching_rate * EXCLUDED.total_count
                        ) / (bunching_by_stop.total_count + EXCLUDED.total_count),
                        total_count = bunching_by_stop.total_count + EXCLUDED.total_count,
                        last_updated = GREATEST(bunching_by_stop.last_updated, EXCLUDED.last_updated)
                """)
            
            updated_stops = cur.rowcount
            conn.commit()
            print(f"✓ bunching_by_stop: Updated {updated_stops} records")
            updated_count += updated_stops
        
        if has_by_day:
            # Step 3: Aggregate by day of week
            cur.execute("""
                INSERT INTO bunching_by_day (
                    stop_id, route_id, operator, direction, day_of_week, 
                    avg_bunching_rate, total_count, last_updated
                )
                SELECT 
                    stop_id, route_id, 'Unknown' as operator, direction,
                    EXTRACT(DOW FROM last_updated)::INTEGER as day_of_week,
                    SUM(bunching_rate_pct * observation_count) / NULLIF(SUM(observation_count), 0) as avg_bunching_rate,
                    SUM(observation_count) as total_count,
                    MAX(last_updated) as last_updated
                FROM bunching_by_route_stop_hour
                WHERE last_updated > (SELECT COALESCE(MAX(last_updated), '1970-01-01') FROM bunching_by_day)
                GROUP BY stop_id, route_id, direction, EXTRACT(DOW FROM last_updated)
                HAVING SUM(observation_count) >= 5
                ON CONFLICT (stop_id, route_id, direction, day_of_week)
                DO UPDATE SET
                    avg_bunching_rate = (bunching_by_day.avg_bunching_rate * bunching_by_day.total_count + 
                                       EXCLUDED.avg_bunching_rate * EXCLUDED.total_count) / 
                                      (bunching_by_day.total_count + EXCLUDED.total_count),
                    total_count = bunching_by_day.total_count + EXCLUDED.total_count,
                    last_updated = GREATEST(bunching_by_day.last_updated, EXCLUDED.last_updated)
            """)
            conn.commit()
            print(f"✓ bunching_by_day: Updated {cur.rowcount} records")
        
        if has_by_month:
            # Step 4: Aggregate by month
            cur.execute("""
                INSERT INTO bunching_by_month (
                    stop_id, route_id, operator, direction, month,
                    avg_bunching_rate, total_count, last_updated
                )
                SELECT 
                    stop_id, route_id, 'Unknown' as operator, direction,
                    EXTRACT(MONTH FROM last_updated)::INTEGER as month,
                    SUM(bunching_rate_pct * observation_count) / NULLIF(SUM(observation_count), 0) as avg_bunching_rate,
                    SUM(observation_count) as total_count,
                    MAX(last_updated) as last_updated
                FROM bunching_by_route_stop_hour
                WHERE last_updated > (SELECT COALESCE(MAX(last_updated), '1970-01-01') FROM bunching_by_month)
                GROUP BY stop_id, route_id, direction, EXTRACT(MONTH FROM last_updated)
                HAVING SUM(observation_count) >= 10
                ON CONFLICT (stop_id, route_id, direction, month)
                DO UPDATE SET
                    avg_bunching_rate = (bunching_by_month.avg_bunching_rate * bunching_by_month.total_count + 
                                       EXCLUDED.avg_bunching_rate * EXCLUDED.total_count) / 
                                      (bunching_by_month.total_count + EXCLUDED.total_count),
                    total_count = bunching_by_month.total_count + EXCLUDED.total_count,
                    last_updated = GREATEST(bunching_by_month.last_updated, EXCLUDED.last_updated)
            """)
            conn.commit()
            print(f"✓ bunching_by_month: Updated {cur.rowcount} records")
        
        if has_by_hour_day:
            # Step 5: Aggregate by hour and day
            cur.execute("""
                INSERT INTO bunching_by_hour_day (
                    stop_id, route_id, operator, direction, hour_of_day, day_of_week,
                    avg_bunching_rate, total_count, last_updated
                )
                SELECT 
                    stop_id, route_id, 'Unknown' as operator, direction, hour_of_day,
                    EXTRACT(DOW FROM last_updated)::INTEGER as day_of_week,
                    SUM(bunching_rate_pct * observation_count) / NULLIF(SUM(observation_count), 0) as avg_bunching_rate,
                    SUM(observation_count) as total_count,
                    MAX(last_updated) as last_updated
                FROM bunching_by_route_stop_hour
                WHERE last_updated > (SELECT COALESCE(MAX(last_updated), '1970-01-01') FROM bunching_by_hour_day)
                GROUP BY stop_id, route_id, direction, hour_of_day, EXTRACT(DOW FROM last_updated)
                HAVING SUM(observation_count) >= 3
                ON CONFLICT (stop_id, route_id, direction, hour_of_day, day_of_week)
                DO UPDATE SET
                    avg_bunching_rate = (bunching_by_hour_day.avg_bunching_rate * bunching_by_hour_day.total_count + 
                                       EXCLUDED.avg_bunching_rate * EXCLUDED.total_count) / 
                                      (bunching_by_hour_day.total_count + EXCLUDED.total_count),
                    total_count = bunching_by_hour_day.total_count + EXCLUDED.total_count,
                    last_updated = GREATEST(bunching_by_hour_day.last_updated, EXCLUDED.last_updated)
            """)
            conn.commit()
            print(f"✓ bunching_by_hour_day: Updated {cur.rowcount} records")
        
        if updated_count == 0:
            print("\n⚠ No bunching aggregation tables available (post-migration)")
            print("  Only bunching_by_route_stop_hour and bunching_by_stop are kept")
        
    except Exception as e:
        print(f"Error during aggregation: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    aggregate_scores()
