"""
Prefect Flow: Data Ingestion
Polls BODS API every 60 seconds
"""

from prefect import flow, task
from datetime import timedelta
import sys
import os

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

# Import the poll function from continuous_poller
import continuous_poller

@task(name="Poll BODS API", retries=3, retry_delay_seconds=10)
def ingest_data():
    """Fetch and store vehicle positions from BODS API"""
    print("Polling BODS API...")
    continuous_poller.poll_and_ingest()

@flow(name="PT Analytics - Data Ingestion")
def ingestion_pipeline():
    """Data ingestion pipeline - runs every 60 seconds"""
    ingest_data()

if __name__ == "__main__":
    ingestion_pipeline()
