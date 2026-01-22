from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from uuid import uuid4

app = FastAPI()

# --- CORS (OBBLIGATORIO) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELLI ---
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

# --- STORAGE IN MEMORIA ---
DRAFTS: List[Draft] = []

# --- ENDPOINTS ---
@app.post("/api/drafts", response_model=Draft)
def create_draft(data: DraftCreate):
    draft = Draft(
        id=str(uuid4()),
        **data.dict()
    )
    DRAFTS.append(draft)
    return draft

@app.get("/api/drafts", response_model=List[Draft])
def list_drafts():
    return DRAFTS
