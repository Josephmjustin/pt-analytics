#!/usr/bin/env python3
"""
Calculate Schedule Adherence Component Score
Matches real-time vehicle arrivals with scheduled times to determine on-time performance

On-time definition: -1 minute early to +5 minutes late
Calculates adherence rate for each route-direction-operator combination
"""

import psycopg2
from datetime import datetime, time, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Database connections
SUPABASE_CONFIG = {
    'host': os.getenv('SUPABASE_HOST'),
    'port': '5432',
    'database': 'postgres',
    'user': 'postgres',
    'password': os.getenv('SUPABASE_PASSWORD')
}

SCHEDULE_DB_CONFIG = {
    'host': '141.147.106.59',
    'port': '5432',
    'database': 'pt_analytics_schedules',
    'user': 'pt_api',
    'password': os.getenv('ORACLE_VM2_PASSWORD')
}

def get_pattern_id(route_name, direction, operator):
    """
    Get pattern_id for a route-direction-operator combination
    Returns None if not found
    """
    conn = psycopg2.connect(**SCHEDULE_DB_CONFIG)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT pattern_id
            FROM txc_route_patterns
            WHERE route_name = %s
              AND direction = %s
              AND operator_name LIKE %s
            LIMIT 1
        """, (route_name, direction, f'%{operator}%'))
        
        result = cur.fetchone()
        return result[0] if result else None
        
    finally:
        cur.close()
        conn.close()

def get_scheduled_times(pattern_id, naptan_id, day_of_week, hour):
    """
    Get scheduled arrival times for a specific stop-hour
    Returns list of TIME objects or empty list
    """
    conn = psycopg2.connect(**SCHEDULE_DB_CONFIG)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT scheduled_arrivals
            FROM stop_schedule
            WHERE pattern_id = %s
              AND naptan_id = %s
              AND day_of_week = %s
              AND hour = %s
              AND CURRENT_DATE BETWEEN valid_from AND valid_to
            LIMIT 1
        """, (pattern_id, naptan_id, day_of_week, hour))
        
        result = cur.fetchone()
        return list(result[0]) if result and result[0] else []
        
    finally:
        cur.close()
        conn.close()

def find_closest_scheduled_time(actual_time, scheduled_times):
    """
    Find closest scheduled time to actual arrival
    Returns (scheduled_time, diff_minutes) or (None, None)
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

def classify_adherence(diff_minutes):
    """
    Classify adherence based on difference
    Returns: 'on_time', 'early', or 'late'
    """
    if diff_minutes is None:
        return 'no_schedule'
    elif -1 <= diff_minutes <= 5:
        return 'on_time'
    elif diff_minutes < -1:
        return 'early'
    else:
        return 'late'

def calculate_adherence_for_period(start_time, end_time):
    """
    Calculate schedule adherence for all arrivals in time period
    
    Returns summary statistics by route-direction-operator
    """
    print(f"\n{'='*70}")
    print(f"SCHEDULE ADHERENCE CALCULATION")
    print(f"Period: {start_time} to {end_time}")
    print(f"{'='*70}\n")
    
    # Connect to Supabase
    conn_rt = psycopg2.connect(**SUPABASE_CONFIG)
    cur_rt = conn_rt.cursor()
    
    # Get all vehicle arrivals in period
    cur_rt.execute("""
        SELECT 
            route_name,
            operator,
            direction,
            naptan_id,
            timestamp
        FROM vehicle_arrivals
        WHERE timestamp >= %s
          AND timestamp < %s
        ORDER BY timestamp
    """, (start_time, end_time))
    
    arrivals = cur_rt.fetchall()
    total_arrivals = len(arrivals)
    
    print(f"Processing {total_arrivals:,} vehicle arrivals...")
    
    # Statistics by route-direction-operator
    route_stats = {}
    
    # Overall stats
    overall = {
        'total': 0,
        'on_time': 0,
        'early': 0,
        'late': 0,
        'no_schedule': 0,
        'no_pattern': 0
    }
    
    processed = 0
    for route_name, operator, direction, naptan_id, timestamp in arrivals:
        processed += 1
        
        if processed % 1000 == 0:
            print(f"  Processed {processed:,}/{total_arrivals:,} arrivals...")
        
        # Convert timestamp to components
        day_of_week = (timestamp.weekday() + 6) % 7  # Convert Python weekday to schedule format
        hour = timestamp.hour
        arrival_time = timestamp.time()
        
        # Get pattern_id
        pattern_id = get_pattern_id(route_name, direction, operator)
        if pattern_id is None:
            overall['no_pattern'] += 1
            continue
        
        # Get scheduled times
        scheduled_times = get_scheduled_times(pattern_id, naptan_id, day_of_week, hour)
        
        if not scheduled_times:
            overall['no_schedule'] += 1
            continue
        
        # Find closest scheduled time and calculate difference
        closest_time, diff_minutes = find_closest_scheduled_time(arrival_time, scheduled_times)
        
        # Classify adherence
        status = classify_adherence(diff_minutes)
        
        # Update overall stats
        overall['total'] += 1
        overall[status] += 1
        
        # Update route-specific stats
        route_key = (route_name, direction, operator)
        if route_key not in route_stats:
            route_stats[route_key] = {
                'total': 0,
                'on_time': 0,
                'early': 0,
                'late': 0
            }
        
        route_stats[route_key]['total'] += 1
        route_stats[route_key][status] += 1
    
    cur_rt.close()
    conn_rt.close()
    
    return overall, route_stats

def display_results(overall, route_stats):
    """
    Display adherence calculation results
    """
    print(f"\n{'='*70}")
    print("OVERALL RESULTS")
    print(f"{'='*70}")
    print(f"Total Arrivals Processed:  {overall['total']:,}")
    print(f"No Pattern Match:          {overall['no_pattern']:,}")
    print(f"No Schedule Data:          {overall['no_schedule']:,}")
    print()
    
    if overall['total'] > 0:
        on_time_pct = (overall['on_time'] / overall['total']) * 100
        early_pct = (overall['early'] / overall['total']) * 100
        late_pct = (overall['late'] / overall['total']) * 100
        
        print(f"On-Time (-1 to +5 min):    {overall['on_time']:,} ({on_time_pct:.1f}%)")
        print(f"Early (< -1 min):          {overall['early']:,} ({early_pct:.1f}%)")
        print(f"Late (> +5 min):           {overall['late']:,} ({late_pct:.1f}%)")
        print()
        print(f"Overall Adherence Rate:    {on_time_pct:.1f}%")
    
    # Show top/bottom routes
    if route_stats:
        print(f"\n{'='*70}")
        print("TOP 10 BEST PERFORMING ROUTES")
        print(f"{'='*70}")
        
        sorted_routes = sorted(
            [(k, v) for k, v in route_stats.items() if v['total'] >= 10],
            key=lambda x: x[1]['on_time'] / x[1]['total'],
            reverse=True
        )[:10]
        
        for (route, direction, operator), stats in sorted_routes:
            adherence = (stats['on_time'] / stats['total']) * 100
            print(f"{route:>6} {direction:>9} {operator:<20} {adherence:>5.1f}% ({stats['on_time']}/{stats['total']})")
        
        print(f"\n{'='*70}")
        print("TOP 10 WORST PERFORMING ROUTES")
        print(f"{'='*70}")
        
        worst_routes = sorted(
            [(k, v) for k, v in route_stats.items() if v['total'] >= 10],
            key=lambda x: x[1]['on_time'] / x[1]['total']
        )[:10]
        
        for (route, direction, operator), stats in worst_routes:
            adherence = (stats['on_time'] / stats['total']) * 100
            print(f"{route:>6} {direction:>9} {operator:<20} {adherence:>5.1f}% ({stats['on_time']}/{stats['total']})")

def main():
    """
    Calculate schedule adherence for last 24 hours
    """
    # Calculate for last 24 hours
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)
    
    overall, route_stats = calculate_adherence_for_period(start_time, end_time)
    
    display_results(overall, route_stats)
    
    print(f"\n{'='*70}")
    print("✓ Schedule Adherence Calculation Complete")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
