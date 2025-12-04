"""
Prefect Deployment: Main Pipeline
Runs ingestion (60s), analysis (5min), cleanup (10min), and aggregation (15min)
"""
import logging
import os
from prefect import serve
from ingestion_flow import ingestion_pipeline
from analysis_flow import analysis_pipeline
from cleanup_flow import cleanup_pipeline
from aggregation_flow import aggregation_pipeline

# Suppress excessive Prefect logging
logging.getLogger("prefect").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
os.environ["PREFECT_LOGGING_LEVEL"] = "WARNING"

if __name__ == "__main__":
    # Ingestion: every 60 seconds
    ingestion_deployment = ingestion_pipeline.to_deployment(
        name="ingestion-every-60s",
        interval=60,
        tags=["ingestion", "realtime"]
    )
    
    # Analysis: every 5 minutes
    analysis_deployment = analysis_pipeline.to_deployment(
        name="analysis-every-5min",
        interval=300,
        tags=["analytics", "bunching"]
    )
    
    # Aggregation: every 10 minutes (before cleanup)
    aggregation_deployment = aggregation_pipeline.to_deployment(
        name="aggregation-every-10min",
        interval=600,
        tags=["aggregation", "patterns"]
    )
    
    # Cleanup: every 15 minutes (after aggregation)
    cleanup_deployment = cleanup_pipeline.to_deployment(
        name="cleanup-every-15min",
        interval=900,
        tags=["maintenance", "cleanup"]
    )
    
    # Serve all deployments
    print("=" * 60)
    print("PT Analytics Pipeline Started")
    print("=" * 60)
    print("Ingestion:   every 60 seconds")
    print("Analysis:    every 5 minutes")
    print("Aggregation: every 10 minutes (learn patterns)")
    print("Cleanup:     every 15 minutes (delete old data)")
    print("=" * 60)
    print("Press Ctrl+C to stop cleanly")
    print("=" * 60)
    
    serve(ingestion_deployment, analysis_deployment, cleanup_deployment, aggregation_deployment)
