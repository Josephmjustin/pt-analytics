"""
Prefect Flow: Data Ingestion
Polls BODS API every 10 seconds (changed from 60s)
"""

from prefect import flow, task
from datetime import timedelta
import sys
import os
import time

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

# Import the poll function
from scripts import continuous_poller

@task(name="Poll BODS API", retries=3, retry_delay_seconds=10)
def ingest_data():
    """Fetch and store vehicle positions from BODS API with TransXChange matching"""
    print("Polling BODS API...")
    continuous_poller.poll_and_ingest()

@flow(name="PT Analytics - Data Ingestion (10s)")
def ingestion_pipeline():
    """Data ingestion pipeline - runs every 10 seconds via Prefect schedule"""
    ingest_data()

if __name__ == "__main__":
    ingestion_pipeline()
