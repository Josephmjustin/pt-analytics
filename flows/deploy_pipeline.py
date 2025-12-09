"""  
Prefect Deployment: Main Pipeline
Runs ingestion (10s) and complete analysis (10min)
"""
import logging
import os
from prefect import serve
from ingestion_flow import ingestion_pipeline
from analysis_flow import analysis_pipeline

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
    
    # Complete Analysis: every 10 minutes
    # (stop detection, matching, bunching calc, aggregation, cleanup)
    analysis_deployment = analysis_pipeline.to_deployment(
        name="complete-analysis-every-10min",
        interval=600,
        tags=["analytics", "bunching", "aggregation", "cleanup"]
    )
    
    # Serve both deployments
    print("=" * 60)
    print("PT Analytics Pipeline Started")
    print("=" * 60)
    print("Ingestion: every 10 seconds (store positions)")
    print("Analysis:  every 10 minutes (complete pipeline)")
    print("  1. Detect stop events")
    print("  2. Match to TransXChange stops")
    print("  3. Calculate bunching")
    print("  4. Aggregate to running averages")
    print("  5. Cleanup analyzed data")
    print("=" * 60)
    print("Press Ctrl+C to stop cleanly")
    print("=" * 60)
    
    serve(ingestion_deployment, analysis_deployment)
