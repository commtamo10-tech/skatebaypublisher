import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from uuid import uuid4

app = FastAPI()

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROOT (SERVE PER TEST) ---
@app.get("/")
def root():
    return {"status": "ok"}

# --- LOGIN ---
class LoginRequest(BaseModel):
    password: str

@app.post("/api/login")
def login(data: LoginRequest):
    admin_password = os.getenv("APP_ADMIN_PASSWORD")

    if not admin_password:
        raise HTTPException(status_code=500, detail="Admin password not set")

    if data.password != admin_password:
        raise HTTPException(status_code=401, detail="Wrong password")

    return {"success": True}

# --- DRAFT MODELS ---
class DraftCreate(BaseModel):
    item_type: str
    category_id: str
    price: float
    image_urls: List[str]
    condition: str

class Draft(BaseModel):
    id: str
    item_type: str
    category_id: str
    price: float
    image_urls: List[str]
    condition: str
    status: str = "DRAFT"

# --- STORAGE ---
DRAFTS: List[Draft] = []

# --- DRAFT ENDPOINTS ---
@app.post("/api/drafts", response_model=Draft)
def create_draft(data: DraftCreate):
    draft = Draft(id=str(uuid4()), **data.dict())
    DRAFTS.append(draft)
    return draft

@app.get("/api/drafts", response_model=List[Draft])
def list_drafts():
    return DRAFTS
