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
    # Ingestion: every 10 seconds (BODS API refresh rate)
    ingestion_deployment = ingestion_pipeline.to_deployment(
        name="ingestion-every-10s",
        interval=10,
        tags=["ingestion", "realtime"]
    )
    
    # Analysis: every 10 minutes (process stop events)
    analysis_deployment = analysis_pipeline.to_deployment(
        name="analysis-every-10min",
        interval=600,
        tags=["analytics", "bunching", "stop-detection"]
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
    print("Ingestion:   every 10 seconds (store positions)")
    print("Analysis:    every 10 minutes (detect stops + match)")
    print("Aggregation: every 10 minutes (learn patterns)")
    print("Cleanup:     every 15 minutes (delete analyzed data)")
    print("=" * 60)
    print("Press Ctrl+C to stop cleanly")
    print("=" * 60)
    
    serve(ingestion_deployment, analysis_deployment, cleanup_deployment, aggregation_deployment)
