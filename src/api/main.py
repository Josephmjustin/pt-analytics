from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.api.routes import stops, vehicles, routes
from src.api.transxchange_loader import load_transxchange_data

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    import sys
    sys.stdout.flush()
    print("="*80, flush=True)
    print("STARTING UP PT ANALYTICS API", flush=True)
    print("="*80, flush=True)
    try:
        load_transxchange_data()
        print("✓ TransXChange data loaded successfully!", flush=True)
    except Exception as e:
        print(f"✗ ERROR loading TransXChange data: {e}", flush=True)
        import traceback
        traceback.print_exc()
    print("="*80, flush=True)
    yield
    # Shutdown (if needed)
    print("Shutting down...", flush=True)

app = FastAPI(title="PT Analytics API", version="1.0.0", lifespan=lifespan)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(stops.router)
app.include_router(vehicles.router)
app.include_router(routes.router)

@app.get("/")
def root():
    return {"message": "PT Analytics API", "version": "1.0.0"}