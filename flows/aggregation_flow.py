"""
Prefect Flow: Score Aggregation
Aggregates bunching scores into pattern tables
"""

from prefect import flow, task
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from aggregate_scores import aggregate_scores

@task(name="Aggregate Scores", retries=2, retry_delay_seconds=30)
def run_aggregation():
    """Aggregate bunching scores into running averages"""
    print("Starting score aggregation...")
    aggregate_scores()
    print("Aggregation complete")

@flow(name="PT Analytics - Score Aggregation")
def aggregation_pipeline():
    """Score aggregation pipeline - runs every 15 minutes"""
    run_aggregation()

if __name__ == "__main__":
    aggregation_pipeline()
