"""
Prefect Flow: Data Cleanup
Runs after analysis to delete old vehicle positions
"""

from prefect import flow, task
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from cleanup_old_data import cleanup_old_data

@task(name="Cleanup Old Data", retries=2, retry_delay_seconds=30)
def run_cleanup():
    """Delete vehicle positions older than last analysis"""
    print("Starting data cleanup...")
    cleanup_old_data()
    print("Cleanup complete")

@flow(name="PT Analytics - Data Cleanup")
def cleanup_pipeline():
    """Data cleanup pipeline - runs after analysis"""
    run_cleanup()

if __name__ == "__main__":
    cleanup_pipeline()
