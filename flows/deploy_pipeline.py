"""
Prefect Deployment: Main Pipeline
Runs ingestion (60s), analysis (5min), cleanup (10min), and aggregation (15min)
"""

from prefect import serve
from ingestion_flow import ingestion_pipeline
from analysis_flow import analysis_pipeline
from cleanup_flow import cleanup_pipeline
from aggregation_flow import aggregation_pipeline

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
    
    # Cleanup: every 10 minutes (after analyses accumulate)
    cleanup_deployment = cleanup_pipeline.to_deployment(
        name="cleanup-every-10min",
        interval=600,
        tags=["maintenance", "cleanup"]
    )
    
    # Aggregation: every 15 minutes
    aggregation_deployment = aggregation_pipeline.to_deployment(
        name="aggregation-every-15min",
        interval=900,
        tags=["aggregation", "patterns"]
    )
    
    # Serve all deployments
    print("Starting PT Analytics Pipeline...")
    print("- Ingestion: every 60 seconds")
    print("- Analysis: every 5 minutes")
    print("- Cleanup: every 10 minutes")
    print("- Aggregation: every 15 minutes")
    print("Press Ctrl+C to stop")
    
    serve(ingestion_deployment, analysis_deployment, cleanup_deployment, aggregation_deployment)
