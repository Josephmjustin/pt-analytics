"""
Prefect Deployment: Main Pipeline
Runs both ingestion (60s) and analysis (5min)
"""

from prefect import serve
from ingestion_flow import ingestion_pipeline
from analysis_flow import analysis_pipeline

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
    
    # Serve both deployments
    print("Starting PT Analytics Pipeline...")
    print("- Ingestion: every 60 seconds")
    print("- Analysis: every 5 minutes")
    print("Press Ctrl+C to stop")
    
    serve(ingestion_deployment, analysis_deployment)
