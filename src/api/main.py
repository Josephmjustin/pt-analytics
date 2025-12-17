from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.api.routes import stops, vehicles, routes, test_txc
# from src.api.transxchange_loader import load_transxchange_data

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    import sys
    sys.stdout.flush()
    print("="*80, flush=True)
    print("PT ANALYTICS API STARTED", flush=True)
    print("TransXChange data will load on first API request (lazy loading)", flush=True)
    print("="*80, flush=True)
    yield
    # Shutdown
    print("Shutting down...", flush=True)

app = FastAPI(title="PT Analytics API", version="1.0.0", lifespan=lifespan)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ptstat.onrender.com",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(stops.router)
app.include_router(vehicles.router)
app.include_router(routes.router)
app.include_router(test_txc.router)

@app.get("/")
def root():
    return {"message": "PT Analytics API", "version": "1.0.0"}