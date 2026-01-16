from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form, Query, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import base64
import secrets
import httpx
import uuid
import shutil
import json
import bleach
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import jwt

# HTML Sanitization config for eBay descriptions
# Allow div with inline styles for 90s sticker label design
ALLOWED_TAGS = ['p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i', 'h2', 'h3', 'h4', 'blockquote', 'hr', 'div', 'span']
ALLOWED_ATTRIBUTES = {
    'div': ['style'],
    'span': ['style'],
    'p': ['style'],
    'h2': ['style'],
}

def sanitize_html(html_content: str) -> str:
    """Sanitize HTML content to prevent XSS attacks"""
    if not html_content:
        return ""
    return bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Configuration
ADMIN_PASSWORD = os.environ.get('APP_ADMIN_PASSWORD', 'admin123')
JWT_SECRET = os.environ.get('JWT_SECRET', secrets.token_hex(32))
EBAY_CLIENT_ID = os.environ.get('EBAY_CLIENT_ID', '')
EBAY_CLIENT_SECRET = os.environ.get('EBAY_CLIENT_SECRET', '')
EBAY_REDIRECT_URI = os.environ.get('EBAY_REDIRECT_URI', '')
EBAY_SCOPES = os.environ.get('EBAY_SCOPES', 'https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.account')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

# eBay Sandbox URLs
EBAY_SANDBOX_AUTH_URL = "https://auth.sandbox.ebay.com/oauth2/authorize"
EBAY_SANDBOX_TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
EBAY_SANDBOX_API_URL = "https://api.sandbox.ebay.com"

# Create uploads directory
UPLOADS_DIR = ROOT_DIR / 'uploads'
UPLOADS_DIR.mkdir(exist_ok=True)

# App setup
app = FastAPI(title="Skateboard eBay Listing Manager")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============ MODELS ============

class LoginRequest(BaseModel):
    password: str

class LoginResponse(BaseModel):
    token: str
    message: str

class DraftCreate(BaseModel):
    item_type: str  # WHL, TRK, DCK, APP, MISC
    category_id: str
    price: float
    image_urls: List[str] = []
    condition: str = "NEW"  # Default condition is NEW

class DraftUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    aspects: Optional[Dict[str, str]] = None
    auto_filled_aspects: Optional[List[str]] = None  # Track which aspects were auto-filled
    condition: Optional[str] = None
    status: Optional[str] = None
    category_id: Optional[str] = None
    price: Optional[float] = None
    title_manually_edited: Optional[bool] = None
    description_manually_edited: Optional[bool] = None
    item_type: Optional[str] = None

class DraftResponse(BaseModel):
    id: str
    sku: str
    item_type: str
    title: Optional[str] = None
    title_manually_edited: bool = False
    description: Optional[str] = None
    description_manually_edited: bool = False
    aspects: Optional[Dict[str, str]] = None
    auto_filled_aspects: List[str] = []  # Track which aspects were auto-filled
    condition: str = "NEW"  # Default to NEW
    category_id: str
    price: float
    image_urls: List[str] = []
    status: str  # DRAFT, READY, PUBLISHED, ERROR
    offer_id: Optional[str] = None
    listing_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str

class SettingsUpdate(BaseModel):
    fulfillment_policy_id: Optional[str] = None
    return_policy_id: Optional[str] = None
    payment_policy_id: Optional[str] = None
    merchant_location_key: Optional[str] = None

class SettingsResponse(BaseModel):
    fulfillment_policy_id: Optional[str] = None
    return_policy_id: Optional[str] = None
    payment_policy_id: Optional[str] = None
    merchant_location_key: Optional[str] = None
    ebay_connected: bool = False


# ============ BATCH MODELS ============

class BatchCreate(BaseModel):
    name: Optional[str] = None

class BatchImageResponse(BaseModel):
    id: str
    url: str
    filename: str

class BatchGroupResponse(BaseModel):
    id: str
    image_ids: List[str]
    suggested_type: str
    confidence: float
    draft_id: Optional[str] = None

class BatchResponse(BaseModel):
    id: str
    name: Optional[str] = None
    status: str  # CREATED, UPLOADING, GROUPING, GENERATING, READY, ERROR
    image_count: int = 0
    group_count: int = 0
    draft_count: int = 0
    created_at: str
    updated_at: str

class JobResponse(BaseModel):
    id: str
    type: str  # auto_group, generate_drafts
    batch_id: str
    status: str  # PENDING, RUNNING, COMPLETED, ERROR
    progress: int = 0
    message: Optional[str] = None
    error: Optional[str] = None
    created_at: str

class GroupUpdateRequest(BaseModel):
    image_ids: Optional[List[str]] = None
    suggested_type: Optional[str] = None

class MergeGroupsRequest(BaseModel):
    group_ids: List[str]

class MoveImageRequest(BaseModel):
    image_id: str
    from_group_id: str
    to_group_id: Optional[str] = None  # None = create new group


# ============ AUTH HELPERS ============

def create_jwt_token(data: dict, expires_delta: timedelta = timedelta(hours=24)):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")

def verify_jwt_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return verify_jwt_token(credentials.credentials)


# ============ DESCRIPTION TEMPLATES ============

def get_description_template(item_type: str) -> str:
    """Get description template structure based on item type"""
    
    if item_type == "APP":
        return """
(A) COLLECTOR INTRO (2-3 sentences):
Write for vintage streetwear/skateboard collectors. Mention it's a vintage/old school piece if era is known.
Invite buyers to check photos and tag/label carefully.

(B) QUICK SUMMARY:
<p><strong>Summary:</strong> [Paraphrase of title - clean, professional]</p>

<p><strong>Key Details:</strong></p>
<ul>
  [Only include fields that are known - OMIT any unknown fields entirely]
  <li><strong>Brand:</strong> [value]</li>
  <li><strong>Item Type:</strong> [T-shirt/Hoodie/Jacket/Pants/Cap/etc.]</li>
  <li><strong>Department:</strong> [Men/Women/Unisex]</li>
  <li><strong>Size:</strong> [tag size]</li>
  <li><strong>Measurements:</strong> [Chest, Length, Shoulder, Sleeve if known]</li>
  <li><strong>Color:</strong> [value]</li>
  <li><strong>Material:</strong> [fabric composition if known]</li>
  <li><strong>Style/Fit:</strong> [Regular/Oversized/Slim if known]</li>
  <li><strong>Country:</strong> [if known]</li>
</ul>

(C) CONDITION NOTES:
<p><strong>Condition:</strong> [Brief honest description]. Please review all photos carefully as they are part of the description.</p>
[If defects exist, list them. Otherwise omit defects section]

(D) CLOSING + SHIPPING (MANDATORY - include exactly):
"""
    
    elif item_type == "WHL":
        return """
(A) COLLECTOR INTRO (2-3 sentences):
Write for vintage skateboard wheel collectors. Mention era/brand heritage if known.

(B) QUICK SUMMARY:
<p><strong>Summary:</strong> [Paraphrase of title]</p>

<p><strong>Key Details:</strong></p>
<ul>
  [Only include fields that are known]
  <li><strong>Brand:</strong> [value]</li>
  <li><strong>Model:</strong> [value]</li>
  <li><strong>Size:</strong> [diameter in mm]</li>
  <li><strong>Durometer:</strong> [hardness rating]</li>
  <li><strong>Color:</strong> [value]</li>
  <li><strong>Era:</strong> [decade if known]</li>
  <li><strong>Quantity:</strong> [set of 4, pair, single]</li>
</ul>

(C) CONDITION NOTES:
<p><strong>Condition:</strong> [Brief description]. Please review all photos carefully as they are part of the description.</p>

(D) CLOSING + SHIPPING (MANDATORY)
"""
    
    elif item_type == "TRK":
        return """
(A) COLLECTOR INTRO (2-3 sentences):
Write for vintage skateboard truck collectors.

(B) QUICK SUMMARY:
<p><strong>Summary:</strong> [Paraphrase of title]</p>

<p><strong>Key Details:</strong></p>
<ul>
  [Only include fields that are known]
  <li><strong>Brand:</strong> [value]</li>
  <li><strong>Model:</strong> [value]</li>
  <li><strong>Size:</strong> [hanger width if known]</li>
  <li><strong>Era:</strong> [decade if known]</li>
  <li><strong>Color:</strong> [value]</li>
  <li><strong>Quantity:</strong> [pair or single]</li>
</ul>

(C) CONDITION NOTES:
<p><strong>Condition:</strong> [Brief description]. Please review all photos carefully as they are part of the description.</p>

(D) CLOSING + SHIPPING (MANDATORY)
"""
    
    elif item_type == "DCK":
        return """
(A) COLLECTOR INTRO (2-3 sentences):
Write for vintage skateboard deck collectors.

(B) QUICK SUMMARY:
<p><strong>Summary:</strong> [Paraphrase of title]</p>

<p><strong>Key Details:</strong></p>
<ul>
  [Only include fields that are known]
  <li><strong>Brand:</strong> [value]</li>
  <li><strong>Model/Series:</strong> [value]</li>
  <li><strong>Size:</strong> [width in inches]</li>
  <li><strong>Era:</strong> [decade if known]</li>
  <li><strong>Artist:</strong> [if known]</li>
  <li><strong>Type:</strong> [OG/Reissue if known]</li>
</ul>

(C) CONDITION NOTES:
<p><strong>Condition:</strong> [Brief description]. Please review all photos carefully as they are part of the description.</p>

(D) CLOSING + SHIPPING (MANDATORY)
"""
    
    else:  # MISC
        return """
(A) COLLECTOR INTRO (2-3 sentences):
Write for vintage skateboard collectors.

(B) QUICK SUMMARY:
<p><strong>Summary:</strong> [Paraphrase of title]</p>

<p><strong>Key Details:</strong></p>
<ul>
  [Only include fields that are known]
  <li><strong>Brand:</strong> [value if known]</li>
  <li><strong>Type:</strong> [value]</li>
  <li><strong>Era:</strong> [decade if known]</li>
</ul>

(C) CONDITION NOTES:
<p><strong>Condition:</strong> [Brief description]. Please review all photos carefully as they are part of the description.</p>

(D) CLOSING + SHIPPING (MANDATORY)
"""


# ============ SKU GENERATION ============

async def generate_sku(item_type: str) -> str:
    """Generate unique SKU: OSS-<CODE>-<SEQ>"""
    type_codes = {"WHL": "WHL", "TRK": "TRK", "DCK": "DCK", "APP": "APP", "MISC": "MISC"}
    code = type_codes.get(item_type, "MISC")
    
    counter = await db.sku_counter.find_one_and_update(
        {"_id": "sku_counter"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    seq = counter.get("seq", 1)
    return f"OSS-{code}-{seq:06d}"


# ============ AUTH ROUTES ============

@api_router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    if request.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    token = create_jwt_token({"sub": "admin", "role": "admin"})
    return LoginResponse(token=token, message="Login successful")

@api_router.get("/auth/me")
async def get_me(user = Depends(get_current_user)):
    return {"user": "admin", "role": user.get("role")}


# ============ EBAY OAUTH ROUTES ============

@api_router.get("/ebay/auth/start")
async def ebay_auth_start(user = Depends(get_current_user)):
    """Start eBay OAuth flow"""
    if not EBAY_CLIENT_ID or not EBAY_REDIRECT_URI:
        raise HTTPException(status_code=400, detail="eBay credentials not configured. Please add EBAY_CLIENT_ID and EBAY_REDIRECT_URI to .env")
    
    state = secrets.token_urlsafe(32)
    await db.oauth_states.insert_one({
        "state": state,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    })
    
    params = {
        "client_id": EBAY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": EBAY_REDIRECT_URI,
        "scope": EBAY_SCOPES,
        "state": state
    }
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    auth_url = f"{EBAY_SANDBOX_AUTH_URL}?{query_string}"
    
    return {"auth_url": auth_url}

@api_router.get("/ebay/auth/callback")
async def ebay_auth_callback(code: str = Query(...), state: str = Query(...)):
    """Handle eBay OAuth callback"""
    state_doc = await db.oauth_states.find_one({"state": state})
    if not state_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    
    await db.oauth_states.delete_one({"state": state})
    
    credentials = base64.b64encode(f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}".encode()).decode()
    
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            EBAY_SANDBOX_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": EBAY_REDIRECT_URI
            }
        )
    
    if response.status_code != 200:
        logger.error(f"eBay token exchange failed: {response.text}")
        raise HTTPException(status_code=400, detail="Failed to exchange code for tokens")
    
    token_data = response.json()
    
    await db.ebay_tokens.update_one(
        {"_id": "ebay_tokens"},
        {
            "$set": {
                "access_token": token_data["access_token"],
                "refresh_token": token_data["refresh_token"],
                "token_expiry": (datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])).isoformat(),
                "scopes": token_data.get("scope", "").split(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
    # Redirect to frontend settings page
    return RedirectResponse(url=f"{FRONTEND_URL}/settings?ebay_connected=true")

@api_router.get("/ebay/status")
async def ebay_status(user = Depends(get_current_user)):
    """Check eBay connection status"""
    tokens = await db.ebay_tokens.find_one({"_id": "ebay_tokens"}, {"_id": 0})
    if not tokens:
        return {"connected": False}
    
    expiry = datetime.fromisoformat(tokens.get("token_expiry", "2000-01-01T00:00:00+00:00").replace("Z", "+00:00"))
    if expiry < datetime.now(timezone.utc):
        return {"connected": False, "expired": True}
    
    return {"connected": True, "expires_at": tokens.get("token_expiry")}


async def get_ebay_access_token() -> str:
    """Get valid eBay access token, refresh if needed"""
    tokens = await db.ebay_tokens.find_one({"_id": "ebay_tokens"})
    if not tokens:
        raise HTTPException(status_code=401, detail="eBay not connected. Please authorize first.")
    
    expiry = datetime.fromisoformat(tokens.get("token_expiry", "2000-01-01T00:00:00+00:00").replace("Z", "+00:00"))
    
    if expiry > datetime.now(timezone.utc):
        return tokens["access_token"]
    
    # Refresh token
    credentials = base64.b64encode(f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}".encode()).decode()
    
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            EBAY_SANDBOX_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "scope": " ".join(tokens.get("scopes", []))
            }
        )
    
    if response.status_code != 200:
        await db.ebay_tokens.delete_one({"_id": "ebay_tokens"})
        raise HTTPException(status_code=401, detail="eBay session expired. Please re-authorize.")
    
    new_data = response.json()
    await db.ebay_tokens.update_one(
        {"_id": "ebay_tokens"},
        {
            "$set": {
                "access_token": new_data["access_token"],
                "refresh_token": new_data.get("refresh_token", tokens["refresh_token"]),
                "token_expiry": (datetime.now(timezone.utc) + timedelta(seconds=new_data["expires_in"])).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    return new_data["access_token"]


# ============ FILE UPLOAD ROUTES ============

@api_router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...), user = Depends(get_current_user)):
    """Upload images and return public URLs"""
    uploaded_urls = []
    
    for file in files:
        if not file.content_type.startswith("image/"):
            continue
        
        ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = UPLOADS_DIR / filename
        
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Generate public URL (will be served via static files)
        url = f"/api/uploads/{filename}"
        uploaded_urls.append(url)
    
    return {"urls": uploaded_urls}


# ============ DRAFT ROUTES ============

@api_router.post("/drafts", response_model=DraftResponse)
async def create_draft(draft: DraftCreate, user = Depends(get_current_user)):
    """Create new draft"""
    sku = await generate_sku(draft.item_type)
    now = datetime.now(timezone.utc).isoformat()
    
    doc = {
        "id": str(uuid.uuid4()),
        "sku": sku,
        "item_type": draft.item_type,
        "category_id": draft.category_id,
        "price": draft.price,
        "image_urls": draft.image_urls,
        "status": "DRAFT",
        "condition": draft.condition,  # Use condition from request (default NEW)
        "title": None,
        "title_manually_edited": False,
        "description": None,
        "description_manually_edited": False,
        "aspects": None,
        "auto_filled_aspects": [],
        "offer_id": None,
        "listing_id": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now
    }
    
    await db.drafts.insert_one(doc)
    doc.pop("_id", None)
    return DraftResponse(**doc)

@api_router.get("/drafts", response_model=List[DraftResponse])
async def list_drafts(
    status: Optional[str] = None,
    item_type: Optional[str] = None,
    search: Optional[str] = None,
    user = Depends(get_current_user)
):
    """List all drafts with optional filters"""
    query = {}
    if status:
        query["status"] = status
    if item_type:
        query["item_type"] = item_type
    if search:
        query["sku"] = {"$regex": search, "$options": "i"}
    
    cursor = db.drafts.find(query, {"_id": 0}).sort("created_at", -1)
    drafts = await cursor.to_list(1000)
    return [DraftResponse(**d) for d in drafts]

@api_router.get("/drafts/{draft_id}/preview")
async def get_draft_preview(draft_id: str, user = Depends(get_current_user)):
    """Get draft preview data with sanitized HTML"""
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # Get backend URL for image URLs
    backend_url = os.environ.get('REACT_APP_BACKEND_URL', FRONTEND_URL.replace(':3000', ':8001'))
    
    # Convert relative URLs to absolute
    images = []
    for url in draft.get("image_urls", []):
        if url.startswith("/api/"):
            images.append(f"{backend_url}{url}")
        elif url.startswith("http"):
            images.append(url)
        else:
            images.append(f"{backend_url}/api/uploads/{url}")
    
    # Sanitize HTML description server-side
    raw_description = draft.get("description", "")
    sanitized_description = sanitize_html(raw_description)
    
    return {
        "id": draft["id"],
        "sku": draft["sku"],
        "title": draft.get("title") or "Untitled Draft",
        "price": draft.get("price", 0),
        "categoryId": draft.get("category_id", ""),
        "condition": draft.get("condition", "USED_GOOD"),
        "images": images,
        "aspects": draft.get("aspects") or {},
        "descriptionHtml": sanitized_description,
        "descriptionRaw": raw_description,
        "status": draft.get("status", "DRAFT"),
        "itemType": draft.get("item_type", "")
    }

@api_router.get("/drafts/{draft_id}", response_model=DraftResponse)
async def get_draft(draft_id: str, user = Depends(get_current_user)):
    """Get single draft"""
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return DraftResponse(**draft)

@api_router.patch("/drafts/{draft_id}", response_model=DraftResponse)
async def update_draft(draft_id: str, update: DraftUpdate, user = Depends(get_current_user)):
    """Update draft"""
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.drafts.find_one_and_update(
        {"id": draft_id},
        {"$set": update_data},
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    result.pop("_id", None)
    return DraftResponse(**result)

@api_router.delete("/drafts/{draft_id}")
async def delete_draft(draft_id: str, user = Depends(get_current_user)):
    """Delete draft"""
    result = await db.drafts.delete_one({"id": draft_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"message": "Draft deleted"}


# ============ LLM GENERATION ============

@api_router.post("/drafts/{draft_id}/generate")
async def generate_draft_content(draft_id: str, user = Depends(get_current_user)):
    """Generate title, description, aspects using LLM"""
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=400, detail="LLM API key not configured")
    
    item_types_full = {"WHL": "Skateboard Wheels", "TRK": "Skateboard Trucks", "DCK": "Skateboard Deck"}
    item_type_name = item_types_full.get(draft["item_type"], "Skateboard Part")
    
    # Build description template based on item type
    description_structure = get_description_template(draft["item_type"])
    
    # Build prompt
    system_message = f"""You are an eBay listing expert for vintage skateboard items and apparel. Generate optimized eBay listings.

CRITICAL RULES:
- Title MUST be ≤80 characters
- NEVER include "Unknown", "N/A", "assumed", "estimate", "(Unknown)", or empty values in title or description
- If a value is not known, simply OMIT that field entirely
- No ALL CAPS words, no keyword stuffing

TITLE ORDER BY TYPE:
- Wheels (WHL): Brand + Model + Era + OG/NOS + Color + Size(mm) + Durometer(A) + "Skateboard Wheels"
- Trucks (TRK): Brand + Model + Size + Era + OG/NOS + "Skateboard Trucks"
- Decks (DCK): Brand + Model/Series + Era + OG/Reissue + Size(in) + "Skateboard Deck"
- Apparel (APP): Brand + Item Type + Size + Era/Vintage + Color + "Skateboard" + category

DESCRIPTION STRUCTURE (HTML format):
{description_structure}

MANDATORY CLOSING (always include exactly these lines at the end):
<p>Questions? Feel free to message—happy to help.</p>
<p>Ships from Milan, Italy. Combined shipping available—please message before purchase.</p>
<p>International buyers: import duties/taxes are not included and are the buyer's responsibility.</p>
<p>Thanks for looking!</p>

OUTPUT FORMAT (JSON only, NO "Unknown" values anywhere):
{{
  "title": "string (max 80 chars, no Unknown)",
  "description": "string (HTML formatted, no Unknown)",
  "aspects": {{
    "Brand": "string (only if known)",
    "Model": "string (only if known)",
    ... other fields only if known
  }}
}}"""

    user_message = f"""Generate an eBay listing for this vintage {item_type_name}.

Item Type: {item_type_name} ({draft['item_type']})
Category ID: {draft['category_id']}
Images uploaded: {len(draft.get('image_urls', []))} photos

Generate a professional listing. Remember:
- NEVER use "Unknown" or placeholder values
- Only include aspects that are actually known
- Description must follow the exact structure provided"""

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"draft-{draft_id}",
            system_message=system_message
        ).with_model("openai", "gpt-5.2")
        
        response = await chat.send_message(UserMessage(text=user_message))
        
        # Parse JSON from response
        try:
            # Try to extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                generated = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {response}")
            raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {str(e)}")
        
        # Validate title length
        title = generated.get("title", "")[:80]
        
        # Update draft
        update_data = {
            "title": title,
            "description": generated.get("description", ""),
            "aspects": generated.get("aspects", {}),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = await db.drafts.find_one_and_update(
            {"id": draft_id},
            {"$set": update_data},
            return_document=True
        )
        result.pop("_id", None)
        
        return {"message": "Content generated successfully", "draft": DraftResponse(**result)}
        
    except ImportError:
        raise HTTPException(status_code=500, detail="emergentintegrations library not available")
    except Exception as e:
        logger.error(f"LLM generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


# ============ AUTO-FILL SPECIFICS (VISION LLM) ============

def get_aspects_prompt_for_type(item_type: str) -> str:
    """Get the extraction prompt based on item type"""
    base_rules = """
CRITICAL RULES:
- Extract ONLY values you can see or read from the image
- NEVER invent or guess values
- If uncertain, leave the field empty (do NOT write "Unknown", "N/A", "assumed", etc.)
- For Era/Decade, only specify if you can see date indicators (copyright year, design style, etc.)
- Normalize values: Size with units (e.g., "63mm", "8.5in"), Era as "1980s", "1990s", or "1980s-1990s"
"""
    
    if item_type == "WHL":
        return base_rules + """
Extract these aspects for SKATEBOARD WHEELS:
- Brand: Look for brand name on wheel sidewall, graphics, or labels
- Model: Look for model name on wheel
- Size: Diameter in mm (e.g., "63mm", "60mm")
- Durometer: Hardness rating (e.g., "95A", "97A")
- Color: Main wheel color (e.g., "White", "Yellow", "Clear")
- Era: Decade if identifiable from copyright, design, or known vintage models (e.g., "1980s", "1990s")
- Core: Core type if visible (e.g., "Conical", "Standard")
- Material: If identifiable (e.g., "Urethane")
- MPN: Manufacturer part number if visible
- Country: Country of manufacture if visible on label

OUTPUT FORMAT (JSON only, empty string for unknown values):
{
  "Brand": "",
  "Model": "",
  "Size": "",
  "Durometer": "",
  "Color": "",
  "Era": "",
  "Core": "",
  "Material": "",
  "MPN": "",
  "Country": ""
}"""
    
    elif item_type == "TRK":
        return base_rules + """
Extract these aspects for SKATEBOARD TRUCKS:
- Brand: Look for brand name on hanger, baseplate, or pivot cup
- Model: Look for model name
- Size: Hanger width (e.g., "149mm", "8.0")
- Color: Main color/finish (e.g., "Silver", "Black", "Gold")
- Era: Decade if identifiable
- Material: If identifiable (e.g., "Aluminum", "Magnesium")
- MPN: Manufacturer part number if visible
- Country: Country of manufacture if visible

OUTPUT FORMAT (JSON only):
{
  "Brand": "",
  "Model": "",
  "Size": "",
  "Color": "",
  "Era": "",
  "Material": "",
  "MPN": "",
  "Country": ""
}"""
    
    elif item_type == "DCK":
        return base_rules + """
Extract these aspects for SKATEBOARD DECKS:
- Brand: Look for brand name/logo on deck
- Model: Model or series name
- Series: Series name if different from model
- Width: Deck width in inches (e.g., "8.5", "10")
- Length: Deck length if visible
- Era: Decade if identifiable from graphics, shape, or copyright
- Artist: Artist name if signed or credited
- Type: OG (original) or Reissue if identifiable
- Material: Construction type if known (e.g., "7-ply Maple")
- MPN: If visible
- Country: Country of manufacture if visible

OUTPUT FORMAT (JSON only):
{
  "Brand": "",
  "Model": "",
  "Series": "",
  "Width": "",
  "Length": "",
  "Era": "",
  "Artist": "",
  "Type": "",
  "Material": "",
  "MPN": "",
  "Country": ""
}"""
    
    elif item_type == "APP":
        return base_rules + """
Extract these aspects for SKATEBOARD APPAREL:
- Brand: Look for brand name on tags, labels, prints
- Item Type: Type of garment (T-shirt, Hoodie, Jacket, Pants, Cap, etc.)
- Department: Men, Women, or Unisex
- Size: Tag size (S, M, L, XL, etc.)
- Measurements: If visible on tag (e.g., "Chest: 22in")
- Color: Main color(s)
- Material: Fabric composition if on tag (e.g., "100% Cotton")
- Style: Fit style if identifiable (Regular, Oversized, Slim)
- Era: Decade if identifiable from tags, design, or copyright
- Country: Country of manufacture if on tag
- MPN: Style number if on tag
- UPC: Barcode if visible

OUTPUT FORMAT (JSON only):
{
  "Brand": "",
  "Item Type": "",
  "Department": "",
  "Size": "",
  "Measurements": "",
  "Color": "",
  "Material": "",
  "Style": "",
  "Era": "",
  "Country": "",
  "MPN": "",
  "UPC": ""
}"""
    
    else:  # MISC
        return base_rules + """
Extract these aspects for this SKATEBOARD ITEM:
- Brand: Look for brand name
- Item Type: What type of item is this
- Era: Decade if identifiable
- Color: Main color(s)
- Material: Material if identifiable
- Notes: Any other relevant details visible

OUTPUT FORMAT (JSON only):
{
  "Brand": "",
  "Item Type": "",
  "Era": "",
  "Color": "",
  "Material": "",
  "Notes": ""
}"""


@api_router.post("/drafts/{draft_id}/autofill_aspects")
async def autofill_draft_aspects(draft_id: str, user = Depends(get_current_user)):
    """Auto-fill item specifics using LLM vision analysis of images"""
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=400, detail="LLM API key not configured")
    
    image_urls = draft.get("image_urls", [])
    if not image_urls:
        raise HTTPException(status_code=400, detail="No images available for analysis")
    
    item_type = draft["item_type"]
    backend_url = os.environ.get('REACT_APP_BACKEND_URL', FRONTEND_URL.replace(':3000', ':8001'))
    
    # Get the prompt for this item type
    extraction_prompt = get_aspects_prompt_for_type(item_type)
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        
        # Prepare image URLs (make them absolute)
        abs_image_urls = []
        for url in image_urls[:5]:  # Limit to first 5 images
            if url.startswith("http"):
                abs_image_urls.append(url)
            else:
                abs_image_urls.append(f"{backend_url}{url}")
        
        # Create chat with vision model
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"autofill-{draft_id}",
            system_message="You are an expert at identifying vintage skateboard items from photos. Analyze images carefully and extract item specifics. Only provide values you can actually see or read from the images. Never guess or assume values."
        ).with_model("openai", "gpt-5.2")
        
        # Build the message with images
        image_contents = [ImageContent(url=url) for url in abs_image_urls]
        
        user_message = UserMessage(
            text=f"Analyze these images of a vintage skateboard item and extract the item specifics.\n\n{extraction_prompt}",
            images=image_contents
        )
        
        response = await chat.send_message(user_message)
        
        # Parse JSON from response
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                extracted_aspects = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {response}")
            raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {str(e)}")
        
        # Filter out empty values and "Unknown" type values
        invalid_values = ["unknown", "n/a", "na", "none", "", "assumed", "estimate", "possibly", "maybe", "unclear"]
        clean_aspects = {}
        auto_filled_keys = []
        
        for key, value in extracted_aspects.items():
            if value and str(value).strip().lower() not in invalid_values:
                clean_value = str(value).strip()
                clean_aspects[key] = clean_value
                auto_filled_keys.append(key)
        
        # Merge with existing aspects (don't overwrite manually edited ones)
        existing_aspects = draft.get("aspects") or {}
        existing_auto_filled = draft.get("auto_filled_aspects") or []
        
        # Only update aspects that haven't been manually edited
        merged_aspects = existing_aspects.copy()
        new_auto_filled = list(set(existing_auto_filled))  # Keep track of auto-filled keys
        
        for key, value in clean_aspects.items():
            # If this key was previously auto-filled or doesn't exist, we can update it
            if key not in existing_aspects or key in existing_auto_filled:
                merged_aspects[key] = value
                if key not in new_auto_filled:
                    new_auto_filled.append(key)
        
        # Update draft
        update_data = {
            "aspects": merged_aspects,
            "auto_filled_aspects": new_auto_filled,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = await db.drafts.find_one_and_update(
            {"id": draft_id},
            {"$set": update_data},
            return_document=True
        )
        result.pop("_id", None)
        
        return {
            "message": f"Auto-filled {len(auto_filled_keys)} aspects from images",
            "extracted_aspects": clean_aspects,
            "auto_filled_keys": auto_filled_keys,
            "draft": DraftResponse(**result)
        }
        
    except ImportError:
        raise HTTPException(status_code=500, detail="emergentintegrations library not available")
    except Exception as e:
        logger.error(f"Auto-fill aspects error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Auto-fill failed: {str(e)}")


# ============ EBAY INVENTORY API ============

@api_router.post("/drafts/{draft_id}/publish")
async def publish_draft(draft_id: str, user = Depends(get_current_user)):
    """Publish draft to eBay"""
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # Validation
    errors = []
    if not draft.get("title"):
        errors.append("Title is required")
    elif len(draft["title"]) > 80:
        errors.append("Title must be ≤80 characters")
    if not draft.get("image_urls") or len(draft["image_urls"]) == 0:
        errors.append("At least one image is required")
    if not draft.get("category_id"):
        errors.append("Category ID is required")
    if not draft.get("price") or draft["price"] <= 0:
        errors.append("Valid price is required")
    
    settings = await db.settings.find_one({"_id": "app_settings"}, {"_id": 0})
    if not settings:
        errors.append("Business policies not configured. Go to Settings.")
    elif not all([settings.get("fulfillment_policy_id"), settings.get("return_policy_id"), settings.get("payment_policy_id")]):
        errors.append("All business policy IDs required in Settings")
    
    if errors:
        await db.drafts.update_one(
            {"id": draft_id},
            {"$set": {"status": "ERROR", "error_message": "; ".join(errors), "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        raise HTTPException(status_code=400, detail={"errors": errors})
    
    try:
        access_token = await get_ebay_access_token()
        
        # Get backend URL for image URLs
        backend_url = os.environ.get('REACT_APP_BACKEND_URL', FRONTEND_URL.replace(':3000', ':8001'))
        
        # Convert relative URLs to absolute
        image_urls = []
        for url in draft.get("image_urls", []):
            if url.startswith("/api/"):
                image_urls.append(f"{backend_url}{url}")
            elif url.startswith("http"):
                image_urls.append(url)
            else:
                image_urls.append(f"{backend_url}/api/uploads/{url}")
        
        # 1. Create Inventory Item
        inventory_payload = {
            "product": {
                "title": draft["title"],
                "description": draft.get("description", ""),
                "aspects": {k: [v] for k, v in (draft.get("aspects") or {}).items()},
                "imageUrls": image_urls
            },
            "condition": draft.get("condition", "USED_GOOD"),
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": 1
                }
            }
        }
        
        async with httpx.AsyncClient() as http_client:
            # Create/Update inventory item
            inv_response = await http_client.put(
                f"{EBAY_SANDBOX_API_URL}/sell/inventory/v1/inventory_item/{draft['sku']}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "Content-Language": "en-US"
                },
                json=inventory_payload
            )
            
            # Log API call
            await db.api_logs.insert_one({
                "endpoint": "createOrReplaceInventoryItem",
                "sku": draft["sku"],
                "status_code": inv_response.status_code,
                "response": inv_response.text[:1000] if inv_response.text else None,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            if inv_response.status_code not in [200, 204]:
                raise Exception(f"Inventory creation failed: {inv_response.text}")
            
            # 2. Create Offer
            offer_payload = {
                "sku": draft["sku"],
                "marketplaceId": "EBAY_US",
                "format": "FIXED_PRICE",
                "pricingSummary": {
                    "price": {
                        "value": str(draft["price"]),
                        "currency": "USD"
                    }
                },
                "availableQuantity": 1,
                "categoryId": draft["category_id"],
                "listingPolicies": {
                    "fulfillmentPolicyId": settings["fulfillment_policy_id"],
                    "returnPolicyId": settings["return_policy_id"],
                    "paymentPolicyId": settings["payment_policy_id"]
                }
            }
            
            if settings.get("merchant_location_key"):
                offer_payload["merchantLocationKey"] = settings["merchant_location_key"]
            
            offer_response = await http_client.post(
                f"{EBAY_SANDBOX_API_URL}/sell/inventory/v1/offer",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "Content-Language": "en-US"
                },
                json=offer_payload
            )
            
            await db.api_logs.insert_one({
                "endpoint": "createOffer",
                "sku": draft["sku"],
                "status_code": offer_response.status_code,
                "response": offer_response.text[:1000] if offer_response.text else None,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            if offer_response.status_code != 201:
                raise Exception(f"Offer creation failed: {offer_response.text}")
            
            offer_data = offer_response.json()
            offer_id = offer_data["offerId"]
            
            # 3. Publish Offer
            publish_response = await http_client.post(
                f"{EBAY_SANDBOX_API_URL}/sell/inventory/v1/offer/{offer_id}/publish",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            await db.api_logs.insert_one({
                "endpoint": "publishOffer",
                "sku": draft["sku"],
                "offer_id": offer_id,
                "status_code": publish_response.status_code,
                "response": publish_response.text[:1000] if publish_response.text else None,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            if publish_response.status_code not in [200, 204]:
                raise Exception(f"Publish failed: {publish_response.text}")
            
            publish_data = publish_response.json() if publish_response.text else {}
            listing_id = publish_data.get("listingId")
            
            # Update draft
            await db.drafts.update_one(
                {"id": draft_id},
                {"$set": {
                    "status": "PUBLISHED",
                    "offer_id": offer_id,
                    "listing_id": listing_id,
                    "error_message": None,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            return {"message": "Published successfully", "offer_id": offer_id, "listing_id": listing_id}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Publish error: {str(e)}")
        await db.drafts.update_one(
            {"id": draft_id},
            {"$set": {"status": "ERROR", "error_message": str(e), "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        raise HTTPException(status_code=500, detail=str(e))


# ============ SETTINGS ROUTES ============

@api_router.get("/settings", response_model=SettingsResponse)
async def get_settings(user = Depends(get_current_user)):
    """Get app settings"""
    settings = await db.settings.find_one({"_id": "app_settings"}, {"_id": 0})
    if not settings:
        settings = {}
    
    # Check eBay connection
    tokens = await db.ebay_tokens.find_one({"_id": "ebay_tokens"})
    settings["ebay_connected"] = bool(tokens)
    
    return SettingsResponse(**settings)

@api_router.patch("/settings", response_model=SettingsResponse)
async def update_settings(update: SettingsUpdate, user = Depends(get_current_user)):
    """Update app settings"""
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    
    await db.settings.update_one(
        {"_id": "app_settings"},
        {"$set": update_data},
        upsert=True
    )
    
    settings = await db.settings.find_one({"_id": "app_settings"}, {"_id": 0})
    tokens = await db.ebay_tokens.find_one({"_id": "ebay_tokens"})
    settings["ebay_connected"] = bool(tokens)
    
    return SettingsResponse(**settings)

@api_router.get("/ebay/policies")
async def get_ebay_policies(user = Depends(get_current_user)):
    """Fetch business policies from eBay"""
    try:
        access_token = await get_ebay_access_token()
        
        async with httpx.AsyncClient() as http_client:
            fulfillment_resp = await http_client.get(
                f"{EBAY_SANDBOX_API_URL}/sell/account/v1/fulfillment_policy",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"marketplace_id": "EBAY_US"}
            )
            
            payment_resp = await http_client.get(
                f"{EBAY_SANDBOX_API_URL}/sell/account/v1/payment_policy",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"marketplace_id": "EBAY_US"}
            )
            
            return_resp = await http_client.get(
                f"{EBAY_SANDBOX_API_URL}/sell/account/v1/return_policy",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"marketplace_id": "EBAY_US"}
            )
        
        return {
            "fulfillment_policies": fulfillment_resp.json().get("fulfillmentPolicies", []) if fulfillment_resp.status_code == 200 else [],
            "payment_policies": payment_resp.json().get("paymentPolicies", []) if payment_resp.status_code == 200 else [],
            "return_policies": return_resp.json().get("returnPolicies", []) if return_resp.status_code == 200 else []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch policies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ STATS ============

@api_router.get("/stats")
async def get_stats(user = Depends(get_current_user)):
    """Get dashboard stats"""
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    results = await db.drafts.aggregate(pipeline).to_list(100)
    
    stats = {"DRAFT": 0, "READY": 0, "PUBLISHED": 0, "ERROR": 0}
    for r in results:
        if r["_id"] in stats:
            stats[r["_id"]] = r["count"]
    
    stats["total"] = sum(stats.values())
    return stats


# ============ BATCH UPLOAD & AUTO-GROUP ============

@api_router.post("/batches", response_model=BatchResponse)
async def create_batch(batch: BatchCreate, user = Depends(get_current_user)):
    """Create a new batch for multi-image upload"""
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "name": batch.name or f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "status": "CREATED",
        "image_count": 0,
        "group_count": 0,
        "draft_count": 0,
        "created_at": now,
        "updated_at": now
    }
    await db.batches.insert_one(doc)
    doc.pop("_id", None)
    return BatchResponse(**doc)

@api_router.get("/batches", response_model=List[BatchResponse])
async def list_batches(user = Depends(get_current_user)):
    """List all batches"""
    cursor = db.batches.find({}, {"_id": 0}).sort("created_at", -1)
    batches = await cursor.to_list(100)
    return [BatchResponse(**b) for b in batches]

@api_router.get("/batches/{batch_id}", response_model=BatchResponse)
async def get_batch(batch_id: str, user = Depends(get_current_user)):
    """Get batch details"""
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return BatchResponse(**batch)

@api_router.post("/batches/{batch_id}/upload")
async def upload_batch_images(
    batch_id: str,
    files: List[UploadFile] = File(...),
    user = Depends(get_current_user)
):
    """Upload multiple images to a batch"""
    batch = await db.batches.find_one({"id": batch_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    uploaded = []
    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            continue
        
        ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        image_id = str(uuid.uuid4())
        filename = f"{image_id}.{ext}"
        filepath = UPLOADS_DIR / filename
        
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        url = f"/api/uploads/{filename}"
        
        # Save to batch_images collection
        await db.batch_images.insert_one({
            "id": image_id,
            "batch_id": batch_id,
            "url": url,
            "filename": file.filename,
            "group_id": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        uploaded.append({"id": image_id, "url": url, "filename": file.filename})
    
    # Update batch image count
    new_count = batch.get("image_count", 0) + len(uploaded)
    await db.batches.update_one(
        {"id": batch_id},
        {"$set": {"image_count": new_count, "status": "UPLOADING", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"uploaded": uploaded, "count": len(uploaded)}

@api_router.get("/batches/{batch_id}/images")
async def get_batch_images(batch_id: str, user = Depends(get_current_user)):
    """Get all images in a batch"""
    cursor = db.batch_images.find({"batch_id": batch_id}, {"_id": 0})
    images = await cursor.to_list(500)
    return {"images": images}

@api_router.get("/batches/{batch_id}/groups")
async def get_batch_groups(batch_id: str, user = Depends(get_current_user)):
    """Get all groups in a batch"""
    cursor = db.batch_groups.find({"batch_id": batch_id}, {"_id": 0})
    groups = await cursor.to_list(100)
    return {"groups": groups}


# Background task for auto-grouping
async def run_auto_group(batch_id: str, job_id: str):
    """Background task to auto-group images using LLM vision"""
    try:
        await db.jobs.update_one({"id": job_id}, {"$set": {"status": "RUNNING", "progress": 10}})
        
        # Get all images in batch
        cursor = db.batch_images.find({"batch_id": batch_id}, {"_id": 0})
        images = await cursor.to_list(500)
        
        if not images:
            await db.jobs.update_one({"id": job_id}, {"$set": {"status": "ERROR", "error": "No images found"}})
            return
        
        await db.jobs.update_one({"id": job_id}, {"$set": {"progress": 20, "message": f"Analyzing {len(images)} images..."}})
        
        # For MVP: Use LLM to classify each image and group by type
        # Since we don't have CLIP embeddings, we'll use filename patterns + LLM classification
        
        groups_by_type = {"WHL": [], "TRK": [], "DCK": [], "APP": [], "MISC": []}
        
        backend_url = os.environ.get('REACT_APP_BACKEND_URL', FRONTEND_URL.replace(':3000', ':8001'))
        
        # Process images in batches of 5 for LLM classification
        batch_size = 5
        for i in range(0, len(images), batch_size):
            batch_images = images[i:i+batch_size]
            progress = 20 + int((i / len(images)) * 60)
            await db.jobs.update_one({"id": job_id}, {"$set": {"progress": progress}})
            
            for img in batch_images:
                # Get full URL for image
                img_url = img["url"]
                if not img_url.startswith("http"):
                    img_url = f"{backend_url}{img_url}"
                
                # Use LLM to classify the image
                try:
                    if EMERGENT_LLM_KEY:
                        from emergentintegrations.llm.chat import LlmChat, UserMessage
                        
                        chat = LlmChat(
                            api_key=EMERGENT_LLM_KEY,
                            session_id=f"classify-{img['id']}",
                            system_message="You are an expert at identifying vintage skateboard parts. Classify images into: WHL (wheels), TRK (trucks), DCK (decks), APP (apparel), MISC (other). Respond with ONLY the 3-4 letter code."
                        ).with_model("openai", "gpt-5.2")
                        
                        # For text-only model, use filename hints
                        filename_lower = img.get("filename", "").lower()
                        
                        prompt = f"Based on this skateboard item image filename '{img.get('filename', 'unknown')}', what type is it? Respond with ONLY one of: WHL, TRK, DCK, APP, MISC"
                        
                        response = await chat.send_message(UserMessage(text=prompt))
                        item_type = response.strip().upper()[:4]
                        
                        if item_type not in groups_by_type:
                            item_type = "MISC"
                    else:
                        # Fallback: use filename patterns
                        filename_lower = img.get("filename", "").lower()
                        if any(w in filename_lower for w in ["wheel", "whl", "ruota"]):
                            item_type = "WHL"
                        elif any(w in filename_lower for w in ["truck", "trk", "asse"]):
                            item_type = "TRK"
                        elif any(w in filename_lower for w in ["deck", "dck", "tavola", "board"]):
                            item_type = "DCK"
                        elif any(w in filename_lower for w in ["shirt", "tee", "hat", "cap", "apparel"]):
                            item_type = "APP"
                        else:
                            item_type = "MISC"
                    
                    groups_by_type[item_type].append(img["id"])
                    
                except Exception as e:
                    logger.error(f"Classification error for {img['id']}: {e}")
                    groups_by_type["MISC"].append(img["id"])
        
        await db.jobs.update_one({"id": job_id}, {"$set": {"progress": 85, "message": "Creating groups..."}})
        
        # Create groups in DB
        group_count = 0
        for item_type, image_ids in groups_by_type.items():
            if not image_ids:
                continue
            
            # For large groups, split into chunks of ~5 images per group
            chunk_size = 5
            for chunk_start in range(0, len(image_ids), chunk_size):
                chunk = image_ids[chunk_start:chunk_start + chunk_size]
                group_id = str(uuid.uuid4())
                
                await db.batch_groups.insert_one({
                    "id": group_id,
                    "batch_id": batch_id,
                    "image_ids": chunk,
                    "suggested_type": item_type,
                    "confidence": 0.7 if item_type != "MISC" else 0.3,
                    "draft_id": None,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                
                # Update images with group_id
                await db.batch_images.update_many(
                    {"id": {"$in": chunk}},
                    {"$set": {"group_id": group_id}}
                )
                
                group_count += 1
        
        # Update batch
        await db.batches.update_one(
            {"id": batch_id},
            {"$set": {"status": "GROUPED", "group_count": group_count, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        await db.jobs.update_one({"id": job_id}, {"$set": {"status": "COMPLETED", "progress": 100, "message": f"Created {group_count} groups"}})
        
    except Exception as e:
        logger.error(f"Auto-group error: {e}")
        await db.jobs.update_one({"id": job_id}, {"$set": {"status": "ERROR", "error": str(e)}})
        await db.batches.update_one({"id": batch_id}, {"$set": {"status": "ERROR"}})


@api_router.post("/batches/{batch_id}/auto_group")
async def auto_group_batch(batch_id: str, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    """Start auto-grouping of images (background task)"""
    batch = await db.batches.find_one({"id": batch_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Create job
    job_id = str(uuid.uuid4())
    await db.jobs.insert_one({
        "id": job_id,
        "type": "auto_group",
        "batch_id": batch_id,
        "status": "PENDING",
        "progress": 0,
        "message": "Starting auto-group...",
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Start background task
    background_tasks.add_task(run_auto_group, batch_id, job_id)
    
    return {"job_id": job_id, "message": "Auto-grouping started"}


# Background task for generating drafts
async def run_generate_drafts(batch_id: str, job_id: str):
    """Background task to generate drafts from groups"""
    try:
        await db.jobs.update_one({"id": job_id}, {"$set": {"status": "RUNNING", "progress": 10}})
        
        # Get all groups
        cursor = db.batch_groups.find({"batch_id": batch_id, "draft_id": None}, {"_id": 0})
        groups = await cursor.to_list(100)
        
        if not groups:
            await db.jobs.update_one({"id": job_id}, {"$set": {"status": "ERROR", "error": "No groups to process"}})
            return
        
        await db.jobs.update_one({"id": job_id}, {"$set": {"progress": 15, "message": f"Generating {len(groups)} drafts..."}})
        
        backend_url = os.environ.get('REACT_APP_BACKEND_URL', FRONTEND_URL.replace(':3000', ':8001'))
        draft_count = 0
        
        for idx, group in enumerate(groups):
            progress = 15 + int((idx / len(groups)) * 80)
            await db.jobs.update_one({"id": job_id}, {"$set": {"progress": progress, "message": f"Processing group {idx + 1}/{len(groups)}"}})
            
            # Get images for this group
            image_cursor = db.batch_images.find({"id": {"$in": group["image_ids"]}}, {"_id": 0})
            images = await image_cursor.to_list(50)
            image_urls = [img["url"] for img in images]
            
            item_type = group["suggested_type"]
            
            # Generate SKU
            sku = await generate_sku(item_type)
            
            # Generate content using LLM
            title = ""
            description = ""
            aspects = {}
            
            try:
                if EMERGENT_LLM_KEY:
                    from emergentintegrations.llm.chat import LlmChat, UserMessage
                    
                    item_types_full = {"WHL": "Skateboard Wheels", "TRK": "Skateboard Trucks", "DCK": "Skateboard Deck", "APP": "Skateboard Apparel", "MISC": "Skateboard Part"}
                    item_type_name = item_types_full.get(item_type, "Skateboard Part")
                    
                    system_message = """You are an eBay listing expert for vintage skateboard parts. Generate optimized eBay listings.

RULES:
- Title MUST be ≤80 characters
- Title order: Brand + Model + Era + OG/NOS + key specs (size/durometer)
- NEVER use "Unknown", "N/A", "(Unknown)", or leave empty fields in title
- If information is not certain, simply omit it
- Description sections: Overview, Specs (bullets), Condition notes, Shipping & Returns
- Always append these two lines at end of description:
  "Ships from Milan, Italy. Combined shipping available—please message before purchase."
  "International buyers: import duties/taxes are not included and are the buyer's responsibility."

OUTPUT FORMAT (JSON only):
{
  "title": "string (max 80 chars, no Unknown)",
  "description": "string (HTML formatted)",
  "aspects": {
    "Brand": "string (only if known)",
    "Model": "string (only if known)", 
    "Type": "string",
    "Size": "string (only if known)",
    "Era": "string (only if known)"
  }
}"""

                    user_message = f"""Generate an eBay listing for vintage {item_type_name}.
Item Type: {item_type_name}
Number of images: {len(image_urls)}
Generate a professional listing template. Do NOT include Unknown values."""

                    chat = LlmChat(
                        api_key=EMERGENT_LLM_KEY,
                        session_id=f"draft-gen-{group['id']}",
                        system_message=system_message
                    ).with_model("openai", "gpt-5.2")
                    
                    response = await chat.send_message(UserMessage(text=user_message))
                    
                    # Parse JSON from response
                    try:
                        json_start = response.find("{")
                        json_end = response.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            generated = json.loads(response[json_start:json_end])
                            title = generated.get("title", "")[:80]
                            description = generated.get("description", "")
                            aspects = generated.get("aspects", {})
                            # Remove any Unknown values from aspects
                            aspects = {k: v for k, v in aspects.items() if v and "unknown" not in v.lower()}
                    except:
                        pass
                        
            except Exception as e:
                logger.error(f"LLM generation error for group {group['id']}: {e}")
            
            # Fallback title if LLM failed
            if not title:
                type_names = {"WHL": "Vintage Skateboard Wheels", "TRK": "Vintage Skateboard Trucks", "DCK": "Vintage Skateboard Deck", "APP": "Vintage Skateboard Apparel", "MISC": "Vintage Skateboard Part"}
                title = type_names.get(item_type, "Vintage Skateboard Part")
            
            # Create draft
            now = datetime.now(timezone.utc).isoformat()
            draft_id = str(uuid.uuid4())
            
            draft_doc = {
                "id": draft_id,
                "sku": sku,
                "item_type": item_type,
                "category_id": "",
                "price": 0,
                "image_urls": image_urls,
                "status": "DRAFT",
                "condition": "USED_GOOD",
                "title": title,
                "title_manually_edited": False,
                "description": description,
                "description_manually_edited": False,
                "aspects": aspects,
                "offer_id": None,
                "listing_id": None,
                "error_message": None,
                "batch_id": batch_id,
                "group_id": group["id"],
                "confidence": group["confidence"],
                "created_at": now,
                "updated_at": now
            }
            
            await db.drafts.insert_one(draft_doc)
            
            # Update group with draft_id
            await db.batch_groups.update_one(
                {"id": group["id"]},
                {"$set": {"draft_id": draft_id}}
            )
            
            draft_count += 1
        
        # Update batch
        await db.batches.update_one(
            {"id": batch_id},
            {"$set": {"status": "READY", "draft_count": draft_count, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        await db.jobs.update_one({"id": job_id}, {"$set": {"status": "COMPLETED", "progress": 100, "message": f"Created {draft_count} drafts"}})
        
    except Exception as e:
        logger.error(f"Generate drafts error: {e}")
        await db.jobs.update_one({"id": job_id}, {"$set": {"status": "ERROR", "error": str(e)}})


@api_router.post("/batches/{batch_id}/generate_drafts")
async def generate_batch_drafts(batch_id: str, background_tasks: BackgroundTasks, user = Depends(get_current_user)):
    """Generate drafts from groups (background task)"""
    batch = await db.batches.find_one({"id": batch_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Create job
    job_id = str(uuid.uuid4())
    await db.jobs.insert_one({
        "id": job_id,
        "type": "generate_drafts",
        "batch_id": batch_id,
        "status": "PENDING",
        "progress": 0,
        "message": "Starting draft generation...",
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Start background task
    background_tasks.add_task(run_generate_drafts, batch_id, job_id)
    
    return {"job_id": job_id, "message": "Draft generation started"}


@api_router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, user = Depends(get_current_user)):
    """Get job status and progress"""
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**job)


# Group management endpoints
@api_router.patch("/batches/{batch_id}/groups/{group_id}")
async def update_group(batch_id: str, group_id: str, update: GroupUpdateRequest, user = Depends(get_current_user)):
    """Update a group (change type or images)"""
    group = await db.batch_groups.find_one({"id": group_id, "batch_id": batch_id})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    update_data = {}
    if update.image_ids is not None:
        update_data["image_ids"] = update.image_ids
    if update.suggested_type is not None:
        update_data["suggested_type"] = update.suggested_type
    
    if update_data:
        await db.batch_groups.update_one({"id": group_id}, {"$set": update_data})
    
    updated = await db.batch_groups.find_one({"id": group_id}, {"_id": 0})
    return updated


@api_router.post("/batches/{batch_id}/groups/{group_id}/split")
async def split_group(batch_id: str, group_id: str, image_ids: List[str], user = Depends(get_current_user)):
    """Split images from a group into a new group"""
    group = await db.batch_groups.find_one({"id": group_id, "batch_id": batch_id})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Remove images from original group
    remaining_ids = [img_id for img_id in group["image_ids"] if img_id not in image_ids]
    
    if not remaining_ids:
        raise HTTPException(status_code=400, detail="Cannot remove all images from group")
    
    await db.batch_groups.update_one({"id": group_id}, {"$set": {"image_ids": remaining_ids}})
    
    # Create new group
    new_group_id = str(uuid.uuid4())
    await db.batch_groups.insert_one({
        "id": new_group_id,
        "batch_id": batch_id,
        "image_ids": image_ids,
        "suggested_type": group["suggested_type"],
        "confidence": 0.5,
        "draft_id": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Update images
    await db.batch_images.update_many({"id": {"$in": image_ids}}, {"$set": {"group_id": new_group_id}})
    
    # Update batch group count
    await db.batches.update_one({"id": batch_id}, {"$inc": {"group_count": 1}})
    
    return {"new_group_id": new_group_id, "original_group_remaining": len(remaining_ids)}


@api_router.post("/batches/{batch_id}/merge_groups")
async def merge_groups(batch_id: str, request: MergeGroupsRequest, user = Depends(get_current_user)):
    """Merge multiple groups into one"""
    if len(request.group_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 groups to merge")
    
    # Get all groups
    cursor = db.batch_groups.find({"id": {"$in": request.group_ids}, "batch_id": batch_id}, {"_id": 0})
    groups = await cursor.to_list(100)
    
    if len(groups) != len(request.group_ids):
        raise HTTPException(status_code=404, detail="Some groups not found")
    
    # Merge all images into first group
    main_group = groups[0]
    all_image_ids = []
    for g in groups:
        all_image_ids.extend(g["image_ids"])
    
    await db.batch_groups.update_one(
        {"id": main_group["id"]},
        {"$set": {"image_ids": all_image_ids}}
    )
    
    # Delete other groups
    other_group_ids = request.group_ids[1:]
    await db.batch_groups.delete_many({"id": {"$in": other_group_ids}})
    
    # Update images
    await db.batch_images.update_many({"id": {"$in": all_image_ids}}, {"$set": {"group_id": main_group["id"]}})
    
    # Update batch group count
    await db.batches.update_one({"id": batch_id}, {"$inc": {"group_count": -(len(other_group_ids))}})
    
    return {"merged_group_id": main_group["id"], "total_images": len(all_image_ids)}


@api_router.post("/batches/{batch_id}/move_image")
async def move_image(batch_id: str, request: MoveImageRequest, user = Depends(get_current_user)):
    """Move an image from one group to another (or create new group)"""
    # Remove from source group
    from_group = await db.batch_groups.find_one({"id": request.from_group_id, "batch_id": batch_id})
    if not from_group:
        raise HTTPException(status_code=404, detail="Source group not found")
    
    if request.image_id not in from_group["image_ids"]:
        raise HTTPException(status_code=400, detail="Image not in source group")
    
    # Update source group
    new_from_ids = [img_id for img_id in from_group["image_ids"] if img_id != request.image_id]
    if new_from_ids:
        await db.batch_groups.update_one({"id": request.from_group_id}, {"$set": {"image_ids": new_from_ids}})
    else:
        # Delete empty group
        await db.batch_groups.delete_one({"id": request.from_group_id})
        await db.batches.update_one({"id": batch_id}, {"$inc": {"group_count": -1}})
    
    # Add to target group or create new
    if request.to_group_id:
        to_group = await db.batch_groups.find_one({"id": request.to_group_id, "batch_id": batch_id})
        if not to_group:
            raise HTTPException(status_code=404, detail="Target group not found")
        
        await db.batch_groups.update_one(
            {"id": request.to_group_id},
            {"$push": {"image_ids": request.image_id}}
        )
        await db.batch_images.update_one({"id": request.image_id}, {"$set": {"group_id": request.to_group_id}})
        
        return {"moved_to": request.to_group_id}
    else:
        # Create new group
        new_group_id = str(uuid.uuid4())
        await db.batch_groups.insert_one({
            "id": new_group_id,
            "batch_id": batch_id,
            "image_ids": [request.image_id],
            "suggested_type": from_group["suggested_type"],
            "confidence": 0.5,
            "draft_id": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        await db.batch_images.update_one({"id": request.image_id}, {"$set": {"group_id": new_group_id}})
        await db.batches.update_one({"id": batch_id}, {"$inc": {"group_count": 1}})
        
        return {"moved_to": new_group_id, "new_group": True}


@api_router.delete("/batches/{batch_id}/groups/{group_id}")
async def delete_group(batch_id: str, group_id: str, user = Depends(get_current_user)):
    """Delete a group (images become unassigned)"""
    group = await db.batch_groups.find_one({"id": group_id, "batch_id": batch_id})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Unassign images
    await db.batch_images.update_many({"group_id": group_id}, {"$set": {"group_id": None}})
    
    # Delete associated draft if exists
    if group.get("draft_id"):
        await db.drafts.delete_one({"id": group["draft_id"]})
        await db.batches.update_one({"id": batch_id}, {"$inc": {"draft_count": -1}})
    
    # Delete group
    await db.batch_groups.delete_one({"id": group_id})
    await db.batches.update_one({"id": batch_id}, {"$inc": {"group_count": -1}})
    
    return {"message": "Group deleted"}


@api_router.delete("/batches/{batch_id}")
async def delete_batch(batch_id: str, user = Depends(get_current_user)):
    """Delete entire batch with all images, groups and drafts"""
    batch = await db.batches.find_one({"id": batch_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Delete drafts
    await db.drafts.delete_many({"batch_id": batch_id})
    
    # Delete groups
    await db.batch_groups.delete_many({"batch_id": batch_id})
    
    # Delete images (files on disk too)
    cursor = db.batch_images.find({"batch_id": batch_id}, {"_id": 0})
    images = await cursor.to_list(500)
    for img in images:
        filepath = UPLOADS_DIR / img["url"].split("/")[-1]
        if filepath.exists():
            filepath.unlink()
    await db.batch_images.delete_many({"batch_id": batch_id})
    
    # Delete batch
    await db.batches.delete_one({"id": batch_id})
    
    return {"message": "Batch deleted"}


# ============ SETUP ============

# Include router
app.include_router(api_router)

# Serve uploaded files
app.mount("/api/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
