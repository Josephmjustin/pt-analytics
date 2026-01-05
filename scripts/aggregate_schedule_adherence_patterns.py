"""
Aggregate Schedule Adherence Patterns for SRI Platform
Populates schedule_adherence_patterns table

Uses REAL TransXChange scheduled times from VM #2

Calculates:
- Average deviation from schedule (minutes)
- Standard deviation of deviations
- On-time percentage (within -1 to +5 minutes)
- Early/late counts
"""

import psycopg2
import os
import sys
from datetime import datetime

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.api.database import get_db_connection
from dotenv import load_dotenv

load_dotenv()

# VM #2 connection (schedules) - separate database
SCHEDULE_DB_CONFIG = {
    'host': '141.147.106.59',
    'port': '5432',
    'database': 'pt_analytics_schedules',
    'user': 'pt_api',
    'password': os.getenv('ORACLE_VM2_PASSWORD')
}

def get_pattern_id_map():
    """
    Build map of (route, direction, operator) -> pattern_id
    Returns: dict
    """
    conn = psycopg2.connect(**SCHEDULE_DB_CONFIG)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            route_name,
            direction,
            operator_name,
            pattern_id
        FROM txc_route_patterns
    """)
    
    pattern_map = {}
    for route, direction, operator, pattern_id in cur.fetchall():
        key = (route, direction, operator)
        pattern_map[key] = pattern_id
    
    cur.close()
    conn.close()
    
    return pattern_map

def get_scheduled_times_batch(arrivals_batch):
    """
    Get scheduled times for a batch of arrivals from VM #2
    
    Args:
        arrivals_batch: list of (route, direction, operator, naptan_id, dow, hour, arrival_time)
    
    Returns:
        dict: key=(route,dir,op,naptan,dow,hour) -> list of scheduled times
    """
    if not arrivals_batch:
        return {}
    
    conn = psycopg2.connect(**SCHEDULE_DB_CONFIG)
    cur = conn.cursor()
    
    # Get pattern_ids first
    pattern_map = {}
    unique_routes = set((r, d, o) for r, d, o, _, _, _, _ in arrivals_batch)
    
    for route, direction, operator in unique_routes:
        cur.execute("""
            SELECT pattern_id
            FROM txc_route_patterns
            WHERE route_name = %s
              AND direction = %s
              AND operator_name LIKE %s
            LIMIT 1
        """, (route, direction, f'%{operator}%'))
        
        result = cur.fetchone()
        if result:
            pattern_map[(route, direction, operator)] = result[0]
    
    # Now get schedules
    schedule_map = {}
    
    for route, direction, operator, naptan_id, dow, hour, _ in arrivals_batch:
        pattern_id = pattern_map.get((route, direction, operator))
        if not pattern_id:
            continue
        
        cur.execute("""
            SELECT scheduled_arrivals
            FROM stop_schedule
            WHERE pattern_id = %s
              AND naptan_id = %s
              AND day_of_week = %s
              AND hour = %s
              AND CURRENT_DATE BETWEEN valid_from AND valid_to
            LIMIT 1
        """, (pattern_id, naptan_id, dow, hour))
        
        result = cur.fetchone()
        if result and result[0]:
            key = (route, direction, operator, naptan_id, dow, hour)
            schedule_map[key] = list(result[0])
    
    cur.close()
    conn.close()
    
    return schedule_map

def find_closest_scheduled_time(actual_time, scheduled_times):
    """
    Find closest scheduled time to actual arrival
    Returns: (scheduled_time, diff_minutes) or (None, None)
    """
    if not scheduled_times:
        return None, None
    
    # Convert actual time to minutes since midnight
    actual_minutes = actual_time.hour * 60 + actual_time.minute + actual_time.second / 60
    
    closest_time = None
    min_diff = float('inf')
    
    for sched_time in scheduled_times:
        sched_minutes = sched_time.hour * 60 + sched_time.minute
        diff = actual_minutes - sched_minutes
        
        if abs(diff) < abs(min_diff):
            min_diff = diff
            closest_time = sched_time
    
    return closest_time, min_diff

def aggregate_schedule_adherence_patterns():
    """
    Calculate schedule adherence patterns using TransXChange schedules from VM #2
    """
    
    conn_rt = None
    try:
        conn_rt = get_db_connection()
        cur_rt = conn_rt.cursor()
        
        print(f"[{datetime.now()}] Aggregating schedule adherence patterns...")
        print("="*60)
        print("Using TransXChange scheduled times from VM #2")
        print()
        
        # Get recent arrivals (last 10 minutes - incremental processing)
        cur_rt.execute("""
            SELECT 
                route_name,
                direction,
                operator,
                naptan_id,
                timestamp
            FROM vehicle_arrivals
            WHERE direction IS NOT NULL
              AND timestamp >= NOW() - INTERVAL '10 minutes'
            ORDER BY timestamp
        """)
        
        arrivals = cur_rt.fetchall()
        total_arrivals = len(arrivals)
        
        print(f"Processing {total_arrivals:,} vehicle arrivals...")
        
        if total_arrivals == 0:
            print("No arrivals to process")
            return
        
        # Process in batches to avoid memory issues
        batch_size = 1000
        adherence_data = []
        
        for batch_start in range(0, total_arrivals, batch_size):
            batch_end = min(batch_start + batch_size, total_arrivals)
            batch = arrivals[batch_start:batch_end]
            
            print(f"  Batch {batch_start//batch_size + 1}/{(total_arrivals + batch_size - 1)//batch_size}...")
            
            # Convert to format needed for schedule lookup
            arrivals_batch = []
            for row in batch:
                route = row['route_name']
                direction = row['direction']
                operator = row['operator']
                naptan_id = row['naptan_id']
                timestamp = row['timestamp']
                
                arrivals_batch.append((
                    route, direction, operator, naptan_id,
                    timestamp.weekday(),  # Monday=0, same as schedule format
                    timestamp.hour,
                    timestamp.time()
                ))
            
            # Get schedules for this batch
            schedules = get_scheduled_times_batch(arrivals_batch)
            
            # Calculate adherence for each arrival
            for row, (route, direction, operator, naptan_id, dow, hour, arrival_time) in zip(batch, arrivals_batch):
                schedule_key = (route, direction, operator, naptan_id, dow, hour)
                scheduled_times = schedules.get(schedule_key)
                
                if not scheduled_times:
                    continue  # Skip if no schedule data
                
                # Find closest scheduled time
                _, diff_minutes = find_closest_scheduled_time(arrival_time, scheduled_times)
                
                if diff_minutes is None:
                    continue
                
                # Classify
                if -1 <= diff_minutes <= 5:
                    status = 'on_time'
                elif diff_minutes < -1:
                    status = 'early'
                else:
                    status = 'late'
                
                # Store for aggregation
                timestamp = row['timestamp']
                adherence_data.append({
                    'route': route,
                    'direction': direction,
                    'operator': operator,
                    'naptan_id': naptan_id,
                    'year': timestamp.year,
                    'month': timestamp.month,
                    'dow': dow,
                    'hour': hour,
                    'deviation': diff_minutes,
                    'status': status
                })
        
        print(f"\nCalculated adherence for {len(adherence_data):,} arrivals with schedule data")
        
        if not adherence_data:
            print("No schedule matches found")
            return
        
        # Aggregate by route/direction/stop/hour
        from collections import defaultdict
        
        aggregates = defaultdict(lambda: {
            'deviations': [],
            'on_time': 0,
            'early': 0,
            'late': 0
        })
        
        for d in adherence_data:
            key = (d['route'], d['direction'], d['operator'], d['naptan_id'], 
                   d['year'], d['month'], d['dow'], d['hour'])
            
            aggregates[key]['deviations'].append(d['deviation'])
            aggregates[key][d['status']] += 1
        
        # Calculate statistics and insert
        print("\nInserting aggregated patterns...")
        
        for key, stats in aggregates.items():
            route, direction, operator, naptan, year, month, dow, hour = key
            
            deviations = stats['deviations']
            total = len(deviations)
            
            avg_deviation = sum(deviations) / total
            
            # Calculate standard deviation
            variance = sum((x - avg_deviation) ** 2 for x in deviations) / total
            std_deviation = variance ** 0.5
            
            # Median
            sorted_devs = sorted(deviations)
            median_deviation = sorted_devs[len(sorted_devs) // 2]
            
            on_time_pct = (stats['on_time'] / total) * 100
            
            cur_rt.execute("""
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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (route_name, direction, operator, stop_id, year, month, day_of_week, hour)
                DO UPDATE SET
                    -- Just update deviation stats (for info only, not used in scoring)
                    avg_deviation_minutes = EXCLUDED.avg_deviation_minutes,
                    std_deviation_minutes = EXCLUDED.std_deviation_minutes,
                    median_deviation_minutes = EXCLUDED.median_deviation_minutes,
                    
                    -- Accumulate counts (this is what matters!)
                    on_time_count = schedule_adherence_patterns.on_time_count + EXCLUDED.on_time_count,
                    early_count = schedule_adherence_patterns.early_count + EXCLUDED.early_count,
                    late_count = schedule_adherence_patterns.late_count + EXCLUDED.late_count,
                    
                    -- Recalculate percentage from accumulated counts (true running average)
                    on_time_percentage = ROUND(
                        (schedule_adherence_patterns.on_time_count + EXCLUDED.on_time_count)::NUMERIC / 
                        (schedule_adherence_patterns.observation_count + EXCLUDED.observation_count) * 100,
                        2
                    ),
                    
                    -- Accumulate observations
                    observation_count = schedule_adherence_patterns.observation_count + EXCLUDED.observation_count,
                    
                    last_updated = NOW()
            """, (
                route, direction, operator, naptan, year, month, dow, hour,
                round(avg_deviation, 2),
                round(std_deviation, 2),
                round(median_deviation, 2),
                stats['on_time'],
                stats['early'],
                stats['late'],
                round(on_time_pct, 2),
                total,
                datetime.now()
            ))
        
        conn_rt.commit()
        
        inserted = len(aggregates)
        print(f"✓ Upserted {inserted:,} schedule adherence pattern records")
        
        # Show summary
        cur_rt.execute("""
            SELECT 
                COUNT(*) as total_patterns,
                COUNT(DISTINCT route_name) as unique_routes,
                COUNT(DISTINCT stop_id) as unique_stops,
                ROUND(AVG(on_time_percentage)::numeric, 1) as avg_on_time_pct,
                ROUND(AVG(avg_deviation_minutes)::numeric, 1) as avg_deviation_min
            FROM schedule_adherence_patterns
        """)
        
        stats = cur_rt.fetchone()
        print(f"\nCurrent schedule_adherence_patterns state:")
        print(f"  Total patterns: {stats['total_patterns']:,}")
        print(f"  Unique routes: {stats['unique_routes']}")
        print(f"  Unique stops: {stats['unique_stops']}")
        print(f"  Avg on-time rate: {stats['avg_on_time_pct']}% (-1 to +5 min)")
        print(f"  Avg deviation: {stats['avg_deviation_min']} minutes")
        
        print("\n📋 Using TransXChange Scheduled Times")
        print("  - On-time: -1 minute early to +5 minutes late")
        print("  - Data source: VM #2 stop_schedule table")
        
        print("="*60)
        print(f"✓ Complete at {datetime.now()}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        if conn_rt:
            conn_rt.rollback()
        raise
    finally:
        if conn_rt:
            cur_rt.close()
            conn_rt.close()

if __name__ == "__main__":
    aggregate_schedule_adherence_patterns()
