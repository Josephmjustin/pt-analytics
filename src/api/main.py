from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import stops, vehicles, routes
from src.api.transxchange_loader import load_transxchange_data

app = FastAPI(title="PT Analytics API", version="1.0.0")

# Load TransXChange data at startup
@app.on_event("startup")
async def startup_event():
    print("Starting up...")
    load_transxchange_data()
    print("Ready!")

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