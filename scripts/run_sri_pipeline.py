#!/usr/bin/env python3
"""
Master SRI Calculation Pipeline
Runs complete SRI calculation in sequence:
1. Aggregate pattern data
2. Calculate component scores
3. Calculate final SRI scores

Run this after analysis completes (after vehicle arrivals are populated)
"""

import sys
import os
from datetime import datetime

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.append(os.path.join(project_root, 'scripts'))

# Import all SRI scripts
try:
    from scripts.aggregate_headway_patterns import aggregate_headway_patterns
    from scripts.aggregate_schedule_adherence_patterns import aggregate_schedule_adherence_patterns
    from scripts.aggregate_journey_time_patterns import aggregate_journey_time_patterns
    from scripts.aggregate_service_delivery_patterns import aggregate_service_delivery_patterns
    from scripts.calculate_component_scores import calculate_component_scores
    from scripts.calculate_sri_scores import calculate_sri_scores
    HAS_ALL_MODULES = True
except ImportError as e:
    print(f"ERROR: Missing required modules - {e}")
    print("Make sure all SRI scripts are in the scripts/ directory")
    HAS_ALL_MODULES = False
    sys.exit(1)

def run_sri_pipeline():
    """
    Execute complete SRI calculation pipeline
    """
    print("="*70)
    print("PT ANALYTICS - SERVICE RELIABILITY INDEX CALCULATION")
    print("="*70)
    print(f"Started at: {datetime.now()}")
    print()
    
    try:
        # PHASE 1: Aggregate Pattern Data
        print("="*70)
        print("PHASE 1: AGGREGATING PATTERN DATA")
        print("="*70)
        print()
        
        print("Step 1/4: Aggregating headway patterns...")
        aggregate_headway_patterns()
        print()
        
        print("Step 2/4: Aggregating schedule adherence patterns...")
        aggregate_schedule_adherence_patterns()
        print()
        
        print("Step 3/4: Aggregating journey time patterns...")
        aggregate_journey_time_patterns()
        print()
        
        print("Step 4/4: Aggregating service delivery patterns...")
        aggregate_service_delivery_patterns()
        print()
        
        # PHASE 2: Calculate Component Scores
        print("="*70)
        print("PHASE 2: CALCULATING COMPONENT SCORES")
        print("="*70)
        print()
        
        calculate_component_scores()
        print()
        
        # PHASE 3: Calculate Final SRI
        print("="*70)
        print("PHASE 3: CALCULATING FINAL SRI SCORES")
        print("="*70)
        print()
        
        calculate_sri_scores()
        print()
        
        # COMPLETE
        print("="*70)
        print("✓ SRI PIPELINE COMPLETE")
        print("="*70)
        print(f"Finished at: {datetime.now()}")
        print()
        print("Next steps:")
        print("  1. Check service_reliability_index table for route scores")
        print("  2. Check network_reliability_index table for network aggregates")
        print("  3. Build API endpoints to expose SRI data")
        print("  4. Build frontend dashboard to visualize SRI")
        
    except Exception as e:
        print("="*70)
        print("✗ SRI PIPELINE FAILED")
        print("="*70)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    if not HAS_ALL_MODULES:
        print("Cannot run - missing required modules")
        sys.exit(1)
    
    run_sri_pipeline()
