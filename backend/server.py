from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
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
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import jwt

# HTML Sanitization config for eBay descriptions
ALLOWED_TAGS = ['p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i', 'h2', 'h3', 'h4', 'blockquote', 'hr']
ALLOWED_ATTRIBUTES = {}  # No attributes allowed

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
    item_type: str  # WHL, TRK, DCK
    category_id: str
    price: float
    image_urls: List[str] = []

class DraftUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    aspects: Optional[Dict[str, str]] = None
    condition: Optional[str] = None
    status: Optional[str] = None
    category_id: Optional[str] = None
    price: Optional[float] = None
    title_manually_edited: Optional[bool] = None

class DraftResponse(BaseModel):
    id: str
    sku: str
    item_type: str
    title: Optional[str] = None
    title_manually_edited: bool = False
    description: Optional[str] = None
    aspects: Optional[Dict[str, str]] = None
    condition: str = "USED_GOOD"
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
        "condition": "USED_GOOD",
        "title": None,
        "description": None,
        "aspects": None,
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
    
    # Build prompt
    system_message = """You are an eBay listing expert for vintage skateboard parts. Generate optimized eBay listings.

RULES:
- Title MUST be ≤80 characters
- Title order: Brand + Model + Era + OG/NOS + key specs (size/durometer)
- No ALL CAPS words, no keyword stuffing
- If information is not visible/certain, omit it or mark as "Unknown"
- Description sections: Overview, Specs (bullets), Condition notes, Shipping & Returns
- Always append these two lines at end of description:
  "Ships from Milan, Italy. Combined shipping available—please message before purchase."
  "International buyers: import duties/taxes are not included and are the buyer's responsibility."

OUTPUT FORMAT (JSON only):
{
  "title": "string (max 80 chars)",
  "description": "string (HTML formatted)",
  "aspects": {
    "Brand": "string or Unknown",
    "Model": "string or Unknown", 
    "Type": "string",
    "Size": "string or Unknown",
    "Era": "string or Unknown",
    "Material": "string or Unknown"
  }
}"""

    user_message = f"""Generate an eBay listing for this vintage {item_type_name}.

Item Type: {item_type_name}
Category ID: {draft['category_id']}
Images uploaded: {len(draft.get('image_urls', []))} photos

Based on the item type, generate appropriate title, description, and aspects.
Since I cannot see the actual photos, generate a template that I can customize.
Make reasonable assumptions for a vintage skateboard item from the 80s-90s era."""

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
