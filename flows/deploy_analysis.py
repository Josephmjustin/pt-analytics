"""
Prefect Deployment: Schedule analysis every 5 minutes
"""

from prefect import serve
from analysis_flow import analysis_pipeline

if __name__ == "__main__":
    # Create deployment that runs every 5 minutes
    analysis_deployment = analysis_pipeline.to_deployment(
        name="analysis-every-5min",
        interval=300,  # seconds (5 minutes)
        tags=["analytics", "bunching"]
    )
    
    # Serve the deployment (keeps running)
    serve(analysis_deployment)
