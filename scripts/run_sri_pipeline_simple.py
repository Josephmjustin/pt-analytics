#!/usr/bin/env python3
"""
SRI Pipeline Runner
Runs all aggregation and calculation scripts in correct order
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def check_prerequisites():
    """Check if we have enough data to run SRI calculations"""
    from src.api.database import get_db_connection
    
    print("="*80)
    print("CHECKING PREREQUISITES")
    print("="*80)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check vehicle_arrivals
    cur.execute("SELECT COUNT(*) FROM vehicle_arrivals")
    arrivals_count = cur.fetchone()[0]
    
    print(f"\n1. Vehicle arrivals: {arrivals_count:,}")
    if arrivals_count < 100:
        print("   ✗ INSUFFICIENT DATA - Need at least 100 arrivals")
        print("   → Wait for more data collection or run analysis script")
        cur.close()
        conn.close()
        return False
    else:
        print("   ✓ Sufficient data")
    
    # Check operators
    cur.execute("""
        SELECT operator, COUNT(*) as count
        FROM vehicle_arrivals
        GROUP BY operator
        ORDER BY count DESC
    """)
    
    print("\n2. Operators in data:")
    unknown_count = 0
    for row in cur.fetchall():
        operator = row[0]
        count = row[1]
        if operator == 'Unknown':
            unknown_count = count
            print(f"   ⚠ {operator:20} {count:,} arrivals")
        else:
            print(f"   ✓ {operator:20} {count:,} arrivals")
    
    if unknown_count > arrivals_count * 0.5:
        print(f"\n   ⚠ WARNING: {unknown_count/arrivals_count*100:.1f}% of data has Unknown operator")
        print("   → Consider running: python scripts/map_operators.py")
    
    # Check routes
    cur.execute("""
        SELECT COUNT(DISTINCT route_name) as routes
        FROM vehicle_arrivals
    """)
    routes = cur.fetchone()[0]
    
    print(f"\n3. Unique routes: {routes}")
    if routes < 10:
        print("   ⚠ LOW ROUTE COUNT - Results may be limited")
    else:
        print("   ✓ Good route coverage")
    
    # Check date range
    cur.execute("""
        SELECT 
            MIN(timestamp) as earliest,
            MAX(timestamp) as latest,
            EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp)))/3600 as hours
        FROM vehicle_arrivals
    """)
    
    result = cur.fetchone()
    print(f"\n4. Data range:")
    print(f"   From: {result[0]}")
    print(f"   To:   {result[1]}")
    print(f"   Span: {result[2]:.1f} hours")
    
    if result[2] < 1:
        print("   ⚠ VERY LIMITED TIME RANGE - Results may not be meaningful")
    else:
        print("   ✓ Sufficient time span")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)
    return True

def run_pipeline():
    """Run complete SRI calculation pipeline"""
    
    print("\n" + "="*80)
    print("SRI PIPELINE EXECUTION")
    print("="*80)
    print(f"Started: {datetime.now()}")
    print("="*80)
    
    steps = [
        ("1/6", "Aggregating headway patterns", "scripts.aggregate_headway_patterns", "aggregate_headway_patterns"),
        ("2/6", "Aggregating schedule adherence", "scripts.aggregate_schedule_adherence_patterns", "aggregate_schedule_adherence_patterns"),
        ("3/6", "Aggregating journey times", "scripts.aggregate_journey_time_patterns", "aggregate_journey_time_patterns"),
        ("4/6", "Aggregating service delivery", "scripts.aggregate_service_delivery_patterns", "aggregate_service_delivery_patterns"),
        ("5/6", "Calculating component scores", "scripts.calculate_component_scores", "calculate_component_scores"),
        ("6/6", "Calculating final SRI scores", "scripts.calculate_sri_scores", "calculate_sri_scores"),
    ]
    
    results = []
    
    for step_num, description, module_path, function_name in steps:
        print(f"\n[{step_num}] {description}...")
        print("-" * 80)
        
        try:
            # Import module
            module = __import__(module_path, fromlist=[function_name])
            func = getattr(module, function_name)
            
            # Run function
            func()
            
            print(f"✓ {description} - COMPLETE")
            results.append((description, "SUCCESS"))
            
        except Exception as e:
            print(f"✗ {description} - FAILED")
            print(f"Error: {e}")
            results.append((description, f"FAILED: {e}"))
            
            # Ask if should continue
            print("\nContinue with remaining steps? (y/n): ", end='')
            response = input().strip().lower()
            if response != 'y':
                break
    
    # Summary
    print("\n" + "="*80)
    print("PIPELINE SUMMARY")
    print("="*80)
    
    success_count = sum(1 for _, status in results if status == "SUCCESS")
    total_count = len(results)
    
    for description, status in results:
        symbol = "✓" if status == "SUCCESS" else "✗"
        print(f"{symbol} {description}: {status}")
    
    print("\n" + "="*80)
    print(f"Completed: {datetime.now()}")
    print(f"Success: {success_count}/{total_count} steps")
    print("="*80)
    
    return success_count == total_count

def verify_results():
    """Verify that SRI tables are populated"""
    from src.api.database import get_db_connection
    
    print("\n" + "="*80)
    print("VERIFYING RESULTS")
    print("="*80)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    tables = [
        'headway_patterns',
        'schedule_adherence_patterns',
        'journey_time_patterns',
        'service_delivery_patterns',
        'headway_consistency_scores',
        'schedule_adherence_scores',
        'journey_time_consistency_scores',
        'service_delivery_scores',
        'service_reliability_index',
        'network_reliability_index'
    ]
    
    print("\nTable row counts:")
    all_empty = True
    
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            
            if count > 0:
                print(f"✓ {table:40} {count:,} rows")
                all_empty = False
            else:
                print(f"✗ {table:40} {count} rows (EMPTY)")
        except Exception as e:
            print(f"✗ {table:40} ERROR: {e}")
    
    if all_empty:
        print("\n⚠ All SRI tables are empty - pipeline may have failed")
        cur.close()
        conn.close()
        return False
    
    # Check network SRI
    print("\nNetwork SRI for current month:")
    cur.execute("""
        SELECT 
            network_name,
            network_sri_score,
            network_grade,
            total_routes,
            calculation_timestamp
        FROM network_reliability_index
        WHERE day_of_week IS NULL
          AND hour IS NULL
        ORDER BY year DESC, month DESC
        LIMIT 1
    """)
    
    result = cur.fetchone()
    if result:
        print(f"✓ Network: {result[0]}")
        print(f"  SRI Score: {result[1]}")
        print(f"  Grade: {result[2]}")
        print(f"  Routes: {result[3]}")
        print(f"  Updated: {result[4]}")
    else:
        print("✗ No network SRI found")
    
    # Sample route SRIs
    print("\nTop 5 routes by SRI:")
    cur.execute("""
        SELECT 
            route_name,
            operator,
            direction,
            sri_score,
            sri_grade
        FROM service_reliability_index
        WHERE day_of_week IS NULL
          AND hour IS NULL
        ORDER BY sri_score DESC
        LIMIT 5
    """)
    
    for row in cur.fetchall():
        print(f"  {row[0]:10} {row[1]:20} {row[2]:10} SRI: {row[3]:.1f} ({row[4]})")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)
    return True

if __name__ == "__main__":
    print("PT ANALYTICS - SRI PIPELINE RUNNER")
    print("="*80)
    
    # Step 1: Check prerequisites
    if not check_prerequisites():
        print("\n⚠ Prerequisites not met. Please resolve issues above.")
        sys.exit(1)
    
    # Step 2: Ask confirmation
    print("\nReady to run SRI pipeline.")
    print("This will:")
    print("  - Aggregate vehicle arrival data into patterns")
    print("  - Calculate component scores (headway, schedule, journey time, service)")
    print("  - Generate final SRI scores for all routes")
    print("  - Create network-level aggregates")
    print("\nEstimated time: 2-5 minutes")
    print("\nProceed? (y/n): ", end='')
    
    response = input().strip().lower()
    
    if response != 'y':
        print("Pipeline cancelled.")
        sys.exit(0)
    
    # Step 3: Run pipeline
    success = run_pipeline()
    
    # Step 4: Verify
    if success:
        verify_results()
        
        print("\n✓ SRI PIPELINE COMPLETE!")
        print("\nNext steps:")
        print("1. Test API: curl http://localhost:8000/sri/network")
        print("2. Start frontend: cd pt-analytics-frontend && npm run dev")
        print("3. View dashboard: http://localhost:5173")
    else:
        print("\n⚠ Pipeline completed with errors. Check logs above.")
        sys.exit(1)