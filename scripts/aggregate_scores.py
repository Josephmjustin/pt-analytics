"""
Aggregate bunching scores into running averages
Aggregates from bunching_by_route_stop_hour into multiple time dimensions
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

def aggregate_scores():
    """
    Aggregate bunching data in multiple dimensions:
    1. bunching_by_route_stop_hour (route + stop + hour) -> most detailed
    2. bunching_by_hour (stop + hour across routes)
    3. bunching_by_stop (stop overall)
    4. bunching_by_day (stop + day of week)
    5. bunching_by_month (stop + month)
    6. bunching_by_hour_day (stop + hour + day of week)
    """
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Step 1: Aggregate route_stop_hour -> by_hour (combine all routes for each stop+hour)
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
        
        # Step 2: Aggregate by_hour -> by_stop (combine all hours for each stop)
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
        
        updated_stops = cur.rowcount
        conn.commit()
        print(f"✓ bunching_by_stop: Updated {updated_stops} records")
        
        # Step 3: Aggregate by day of week (from bunching_by_route_stop_hour)
        cur.execute("""
            INSERT INTO bunching_by_day (
                stop_id,
                route_id,
                operator,
                direction,
                day_of_week, 
                avg_bunching_rate, 
                total_count, 
                last_updated
            )
            SELECT 
                stop_id,
                route_id,
                'Unknown' as operator,
                direction,
                EXTRACT(DOW FROM last_updated)::INTEGER as day_of_week,
                SUM(bunching_rate_pct * observation_count) / NULLIF(SUM(observation_count), 0) as avg_bunching_rate,
                SUM(observation_count) as total_count,
                MAX(last_updated) as last_updated
            FROM bunching_by_route_stop_hour
            WHERE last_updated > (
                SELECT COALESCE(MAX(last_updated), '1970-01-01') 
                FROM bunching_by_day
            )
            GROUP BY stop_id, route_id, direction, EXTRACT(DOW FROM last_updated)
            HAVING SUM(observation_count) >= 5
            ON CONFLICT (stop_id, route_id, direction, day_of_week)
            DO UPDATE SET
                avg_bunching_rate = (
                    bunching_by_day.avg_bunching_rate * bunching_by_day.total_count + 
                    EXCLUDED.avg_bunching_rate * EXCLUDED.total_count
                ) / (bunching_by_day.total_count + EXCLUDED.total_count),
                total_count = bunching_by_day.total_count + EXCLUDED.total_count,
                last_updated = GREATEST(bunching_by_day.last_updated, EXCLUDED.last_updated)
        """)
        
        updated_days = cur.rowcount
        conn.commit()
        print(f"✓ bunching_by_day: Updated {updated_days} records")
        
        # Step 4: Aggregate by month (from bunching_by_route_stop_hour)
        cur.execute("""
            INSERT INTO bunching_by_month (
                stop_id,
                route_id,
                operator,
                direction,
                month, 
                avg_bunching_rate, 
                total_count, 
                last_updated
            )
            SELECT 
                stop_id,
                route_id,
                'Unknown' as operator,
                direction,
                EXTRACT(MONTH FROM last_updated)::INTEGER as month,
                SUM(bunching_rate_pct * observation_count) / NULLIF(SUM(observation_count), 0) as avg_bunching_rate,
                SUM(observation_count) as total_count,
                MAX(last_updated) as last_updated
            FROM bunching_by_route_stop_hour
            WHERE last_updated > (
                SELECT COALESCE(MAX(last_updated), '1970-01-01') 
                FROM bunching_by_month
            )
            GROUP BY stop_id, route_id, direction, EXTRACT(MONTH FROM last_updated)
            HAVING SUM(observation_count) >= 10
            ON CONFLICT (stop_id, route_id, direction, month)
            DO UPDATE SET
                avg_bunching_rate = (
                    bunching_by_month.avg_bunching_rate * bunching_by_month.total_count + 
                    EXCLUDED.avg_bunching_rate * EXCLUDED.total_count
                ) / (bunching_by_month.total_count + EXCLUDED.total_count),
                total_count = bunching_by_month.total_count + EXCLUDED.total_count,
                last_updated = GREATEST(bunching_by_month.last_updated, EXCLUDED.last_updated)
        """)
        
        updated_months = cur.rowcount
        conn.commit()
        print(f"✓ bunching_by_month: Updated {updated_months} records")
        
        # Step 5: Aggregate by hour and day of week (from bunching_by_route_stop_hour)
        cur.execute("""
            INSERT INTO bunching_by_hour_day (
                stop_id,
                route_id,
                operator,
                direction,
                hour_of_day, 
                day_of_week, 
                avg_bunching_rate, 
                total_count, 
                last_updated
            )
            SELECT 
                stop_id,
                route_id,
                'Unknown' as operator,
                direction,
                hour_of_day,
                EXTRACT(DOW FROM last_updated)::INTEGER as day_of_week,
                SUM(bunching_rate_pct * observation_count) / NULLIF(SUM(observation_count), 0) as avg_bunching_rate,
                SUM(observation_count) as total_count,
                MAX(last_updated) as last_updated
            FROM bunching_by_route_stop_hour
            WHERE last_updated > (
                SELECT COALESCE(MAX(last_updated), '1970-01-01') 
                FROM bunching_by_hour_day
            )
            GROUP BY stop_id, route_id, direction, hour_of_day, EXTRACT(DOW FROM last_updated)
            HAVING SUM(observation_count) >= 3
            ON CONFLICT (stop_id, route_id, direction, hour_of_day, day_of_week)
            DO UPDATE SET
                avg_bunching_rate = (
                    bunching_by_hour_day.avg_bunching_rate * bunching_by_hour_day.total_count + 
                    EXCLUDED.avg_bunching_rate * EXCLUDED.total_count
                ) / (bunching_by_hour_day.total_count + EXCLUDED.total_count),
                total_count = bunching_by_hour_day.total_count + EXCLUDED.total_count,
                last_updated = GREATEST(bunching_by_hour_day.last_updated, EXCLUDED.last_updated)
        """)
        
        updated_hour_days = cur.rowcount
        conn.commit()
        print(f"✓ bunching_by_hour_day: Updated {updated_hour_days} records")
        
        # Show current state
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM bunching_by_route_stop_hour) as route_stop_hour_records,
                (SELECT COUNT(DISTINCT stop_id) FROM bunching_by_hour) as stops_with_hourly,
                (SELECT COUNT(*) FROM bunching_by_stop) as stops_overall,
                (SELECT COUNT(*) FROM bunching_by_day) as day_records,
                (SELECT COUNT(*) FROM bunching_by_month) as month_records,
                (SELECT COUNT(*) FROM bunching_by_hour_day) as hour_day_records,
                (SELECT ROUND(AVG(avg_bunching_rate)::numeric, 1) FROM bunching_by_stop) as avg_bunching
        """)
        stats = cur.fetchone()
        
        print(f"\nCurrent state:")
        print(f"  Route-stop-hour records: {stats[0]}")
        print(f"  Stops with hourly data: {stats[1]}")
        print(f"  Stops with overall data: {stats[2]}")
        print(f"  Day-of-week records: {stats[3]}")
        print(f"  Month records: {stats[4]}")
        print(f"  Hour-day records: {stats[5]}")
        print(f"  Avg bunching rate: {stats[6]}%")
        
    except Exception as e:
        print(f"Error during aggregation: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    aggregate_scores()
