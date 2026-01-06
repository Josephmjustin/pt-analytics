from fastapi import FastAPI, Header, HTTPException
from dotenv import load_dotenv
import os

load_dotenv()  # load API_TOKEN from .env

app = FastAPI()
API_TOKEN = os.getenv("API_TOKEN")

def verify_token(x_token: str = Header(None)):
    if not x_token or x_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized access")

@app.get("/data")
def get_data(token: str = Header(None)):
    verify_token(token)
    return {"message": "Authorized access"}
