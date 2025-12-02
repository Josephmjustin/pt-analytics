"""
Prefect Flow: PT Analytics Pipeline
Orchestrates data ingestion and analysis
"""

from prefect import flow, task
from prefect.tasks import task_input_hash
from datetime import timedelta
import sys
import os

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from calculate_bunching_scores_osm import calculate_bunching_scores_osm

@task(name="Calculate Bunching Scores (OSM)", retries=2, retry_delay_seconds=30)
def run_analysis():
    """Run OSM-based bunching score calculation"""
    print("Starting OSM-based bunching analysis...")
    calculate_bunching_scores_osm()
    print("Analysis complete")

@flow(name="PT Analytics - Analysis Pipeline")
def analysis_pipeline():
    """Main analysis pipeline - runs every 5 minutes"""
    run_analysis()

if __name__ == "__main__":
    analysis_pipeline()
