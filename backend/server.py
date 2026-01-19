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

# eBay Sandbox credentials
EBAY_CLIENT_ID = os.environ.get('EBAY_CLIENT_ID', '')
EBAY_CLIENT_SECRET = os.environ.get('EBAY_CLIENT_SECRET', '')
EBAY_REDIRECT_URI = os.environ.get('EBAY_REDIRECT_URI', '')
EBAY_RUNAME = os.environ.get('EBAY_RUNAME', '')

# eBay Production credentials
EBAY_PROD_CLIENT_ID = os.environ.get('EBAY_PROD_CLIENT_ID', '')
EBAY_PROD_CLIENT_SECRET = os.environ.get('EBAY_PROD_CLIENT_SECRET', '')
EBAY_PROD_REDIRECT_URI = os.environ.get('EBAY_PROD_REDIRECT_URI', '')
EBAY_PROD_RUNAME = os.environ.get('EBAY_PROD_RUNAME', '')

EBAY_SCOPES = os.environ.get('EBAY_SCOPES', 'https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.account')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

# eBay Sandbox URLs
EBAY_SANDBOX_AUTH_URL = "https://auth.sandbox.ebay.com/oauth2/authorize"
EBAY_SANDBOX_TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
EBAY_SANDBOX_API_URL = "https://api.sandbox.ebay.com"

# eBay Production URLs
EBAY_PROD_AUTH_URL = "https://auth.ebay.com/oauth2/authorize"
EBAY_PROD_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_PROD_API_URL = "https://api.ebay.com"

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


# ============ EBAY ENVIRONMENT HELPERS ============

async def get_ebay_environment():
    """Get current eBay environment (sandbox or production) from settings"""
    settings = await db.settings.find_one({"_id": "app_settings"})
    return settings.get("ebay_environment", "sandbox") if settings else "sandbox"

def get_ebay_config(environment: str):
    """Get eBay configuration for the specified environment"""
    if environment == "production":
        return {
            "client_id": EBAY_PROD_CLIENT_ID,
            "client_secret": EBAY_PROD_CLIENT_SECRET,
            "redirect_uri": EBAY_PROD_REDIRECT_URI,
            "runame": EBAY_PROD_RUNAME,
            "auth_url": EBAY_PROD_AUTH_URL,
            "token_url": EBAY_PROD_TOKEN_URL,
            "api_url": EBAY_PROD_API_URL,
            "marketplace_id": "EBAY_IT",  # Italian marketplace
            "country_code": "IT",
            "currency": "EUR"
        }
    else:  # sandbox
        return {
            "client_id": EBAY_CLIENT_ID,
            "client_secret": EBAY_CLIENT_SECRET,
            "redirect_uri": EBAY_REDIRECT_URI,
            "runame": EBAY_RUNAME,
            "auth_url": EBAY_SANDBOX_AUTH_URL,
            "token_url": EBAY_SANDBOX_TOKEN_URL,
            "api_url": EBAY_SANDBOX_API_URL,
            "marketplace_id": "EBAY_US",
            "country_code": "US",
            "currency": "USD"
        }


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
    aspects_metadata: Optional[Dict[str, Dict]] = None  # {field: {source, confidence}}
    condition: Optional[str] = None
    status: Optional[str] = None
    category_id: Optional[str] = None
    price: Optional[float] = None
    title_manually_edited: Optional[bool] = None
    description_manually_edited: Optional[bool] = None
    item_type: Optional[str] = None
    # Core Details fields (always present)
    brand: Optional[str] = None
    model: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    era: Optional[str] = None

class DraftResponse(BaseModel):
    id: str
    sku: str
    item_type: str
    title: Optional[str] = None
    title_manually_edited: bool = False
    description: Optional[str] = None
    description_manually_edited: bool = False
    aspects: Optional[Dict[str, str]] = None
    aspects_metadata: Optional[Dict[str, Dict]] = None  # {field: {source, confidence}}
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
    # Core Details (always present, mapped from aspects)
    brand: Optional[str] = None
    model: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    era: Optional[str] = None

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


# ============ VERSION/HEALTH ROUTES ============

BUILD_TIME = datetime.now(timezone.utc).isoformat()
BUILD_COMMIT = "local-dev"  # In production, this would be set via env var

@api_router.get("/version")
async def get_version():
    """Get build version info for debugging which deployment is running"""
    return {
        "build_time": BUILD_TIME,
        "commit_hash": os.environ.get("GIT_COMMIT", BUILD_COMMIT),
        "environment": "sandbox",
        "mongo_db": os.environ.get("DB_NAME", "unknown"),
        "frontend_url": FRONTEND_URL,
        "ebay_redirect_uri": EBAY_REDIRECT_URI,
        "pod_start_time": BUILD_TIME
    }

@api_router.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


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
    # Get current environment
    environment = await get_ebay_environment()
    config = get_ebay_config(environment)
    
    if not config["client_id"]:
        raise HTTPException(status_code=400, detail=f"eBay {environment} credentials not configured. Please add EBAY_{'PROD_' if environment == 'production' else ''}CLIENT_ID to .env")
    
    # Use RuName if available, otherwise fall back to redirect_uri
    redirect_uri_param = config["runame"] if config["runame"] else config["redirect_uri"]
    if not redirect_uri_param:
        raise HTTPException(status_code=400, detail=f"eBay {environment} RuName or Redirect URI not configured.")
    
    state = secrets.token_urlsafe(32)
    await db.oauth_states.insert_one({
        "state": state,
        "environment": environment,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    })
    
    from urllib.parse import urlencode
    
    params = {
        "client_id": config["client_id"],
        "response_type": "code",
        "redirect_uri": redirect_uri_param,
        "scope": EBAY_SCOPES,
        "state": state
    }
    
    query_string = urlencode(params)
    auth_url = f"{config['auth_url']}?{query_string}"
    
    logger.info("=" * 60)
    logger.info(f"EBAY OAUTH AUTHORIZE URL GENERATED ({environment.upper()}):")
    logger.info(f"Base URL: {config['auth_url']}")
    logger.info(f"client_id: {config['client_id']}")
    logger.info(f"redirect_uri: {redirect_uri_param}")
    logger.info(f"marketplace: {config['marketplace_id']}")
    logger.info("=" * 60)
    
    return {"auth_url": auth_url, "environment": environment}

@api_router.get("/ebay/auth/callback")
async def ebay_auth_callback(code: str = Query(None), state: str = Query(None), error: str = Query(None), error_description: str = Query(None)):
    """Handle eBay OAuth callback"""
    logger.info("=" * 60)
    logger.info("EBAY OAUTH CALLBACK RECEIVED")
    logger.info(f"code: {code[:30] if code else 'NONE'}...")
    logger.info(f"state: {state}")
    logger.info(f"error: {error}")
    logger.info(f"error_description: {error_description}")
    logger.info("=" * 60)
    
    # Handle OAuth errors from eBay
    if error:
        logger.error(f"eBay OAuth error: {error} - {error_description}")
        return RedirectResponse(url=f"{FRONTEND_URL}/settings?ebay_error={error}&ebay_error_desc={error_description or 'Unknown error'}")
    
    if not code or not state:
        logger.error("Missing code or state in callback")
        return RedirectResponse(url=f"{FRONTEND_URL}/settings?ebay_error=missing_params&ebay_error_desc=Missing code or state")
    
    state_doc = await db.oauth_states.find_one({"state": state})
    if not state_doc:
        logger.error(f"Invalid or expired state: {state}")
        return RedirectResponse(url=f"{FRONTEND_URL}/settings?ebay_error=invalid_state&ebay_error_desc=State expired or invalid. Please try again.")
    
    # Get environment from state document
    environment = state_doc.get("environment", "sandbox")
    config = get_ebay_config(environment)
    
    await db.oauth_states.delete_one({"state": state})
    
    # Use RuName if available for token exchange
    redirect_uri_param = config["runame"] if config["runame"] else config["redirect_uri"]
    
    credentials = base64.b64encode(f"{config['client_id']}:{config['client_secret']}".encode()).decode()
    
    logger.info("=" * 60)
    logger.info(f"EBAY TOKEN EXCHANGE ({environment.upper()}):")
    logger.info(f"Token URL: {config['token_url']}")
    logger.info(f"redirect_uri: {redirect_uri_param}")
    logger.info(f"code: {code[:30]}...")
    logger.info("=" * 60)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                config["token_url"],
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri_param
                }
            )
        
        logger.info(f"Token exchange response: status={response.status_code}")
        logger.info(f"Token exchange body: {response.text[:500]}")
        
        if response.status_code != 200:
            logger.error(f"eBay token exchange failed: {response.status_code} - {response.text}")
            error_msg = response.text[:200].replace('"', "'")
            return RedirectResponse(url=f"{FRONTEND_URL}/settings?ebay_error=token_exchange_failed&ebay_error_desc={error_msg}")
        
        token_data = response.json()
        
        # Save tokens to database (separate collection for each environment)
        token_collection_id = f"ebay_tokens_{environment}"
        await db.ebay_tokens.update_one(
            {"_id": token_collection_id},
            {
                "$set": {
                    "access_token": token_data["access_token"],
                    "refresh_token": token_data.get("refresh_token"),
                    "token_expiry": (datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 7200))).isoformat(),
                    "scopes": token_data.get("scope", "").split() if token_data.get("scope") else [],
                    "environment": environment,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        
        # Verify tokens were saved
        saved_tokens = await db.ebay_tokens.find_one({"_id": token_collection_id})
        if saved_tokens and saved_tokens.get("access_token"):
            logger.info(f"eBay OAuth successful! Tokens saved for {environment}.")
            return RedirectResponse(url=f"{FRONTEND_URL}/settings?ebay_connected=true&environment={environment}")
        else:
            logger.error("Tokens not saved correctly to database!")
            return RedirectResponse(url=f"{FRONTEND_URL}/settings?ebay_error=db_save_failed&ebay_error_desc=Failed to save tokens to database")
            
    except Exception as e:
        logger.error(f"Exception during token exchange: {str(e)}")
        return RedirectResponse(url=f"{FRONTEND_URL}/settings?ebay_error=exception&ebay_error_desc={str(e)[:100]}")


@api_router.get("/ebay/debug")
async def ebay_debug_status(user = Depends(get_current_user)):
    """Debug endpoint to check eBay OAuth status - does not expose tokens"""
    environment = await get_ebay_environment()
    token_collection_id = f"ebay_tokens_{environment}"
    tokens = await db.ebay_tokens.find_one({"_id": token_collection_id})
    
    if not tokens:
        return {
            "connected": False,
            "environment": environment,
            "has_access_token": False,
            "has_refresh_token": False,
            "token_expires_at": None,
            "scopes": [],
            "updated_at": None,
            "message": f"No tokens found for {environment}. Please complete OAuth flow."
        }
    
    # Check if expired
    expiry_str = tokens.get("token_expiry", "2000-01-01T00:00:00+00:00")
    try:
        expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        is_expired = expiry < datetime.now(timezone.utc)
    except:
        is_expired = True
        expiry = None
    
    return {
        "connected": bool(tokens.get("access_token")) and not is_expired,
        "environment": environment,
        "has_access_token": bool(tokens.get("access_token")),
        "has_refresh_token": bool(tokens.get("refresh_token")),
        "token_expires_at": expiry_str,
        "is_expired": is_expired,
        "scopes": tokens.get("scopes", []),
        "updated_at": tokens.get("updated_at"),
        "message": "Tokens found" if tokens.get("access_token") else "Tokens incomplete"
    }

@api_router.get("/ebay/status")
async def ebay_status(user = Depends(get_current_user)):
    """Check eBay connection status"""
    environment = await get_ebay_environment()
    token_collection_id = f"ebay_tokens_{environment}"
    tokens = await db.ebay_tokens.find_one({"_id": token_collection_id}, {"_id": 0})
    if not tokens:
        return {"connected": False, "environment": environment}
    
    expiry = datetime.fromisoformat(tokens.get("token_expiry", "2000-01-01T00:00:00+00:00").replace("Z", "+00:00"))
    if expiry < datetime.now(timezone.utc):
        return {"connected": False, "expired": True, "environment": environment}
    
    return {"connected": True, "expires_at": tokens.get("token_expiry"), "environment": environment}


async def get_ebay_access_token() -> str:
    """Get valid eBay access token, refresh if needed"""
    environment = await get_ebay_environment()
    token_collection_id = f"ebay_tokens_{environment}"
    tokens = await db.ebay_tokens.find_one({"_id": token_collection_id})
    if not tokens:
        raise HTTPException(status_code=401, detail=f"eBay not connected ({environment}). Please authorize first.")
    
    expiry = datetime.fromisoformat(tokens.get("token_expiry", "2000-01-01T00:00:00+00:00").replace("Z", "+00:00"))
    
    if expiry > datetime.now(timezone.utc):
        return tokens["access_token"]
    
    # Refresh token
    config = get_ebay_config(environment)
    credentials = base64.b64encode(f"{config['client_id']}:{config['client_secret']}".encode()).decode()
    
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            config["token_url"],
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
        await db.ebay_tokens.delete_one({"_id": token_collection_id})
        raise HTTPException(status_code=401, detail="eBay session expired. Please re-authorize.")
    
    new_data = response.json()
    await db.ebay_tokens.update_one(
        {"_id": token_collection_id},
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


async def get_ebay_api_url() -> str:
    """Get the correct eBay API URL based on environment"""
    environment = await get_ebay_environment()
    config = get_ebay_config(environment)
    return config["api_url"]


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

def extract_core_details(aspects: dict) -> dict:
    """Extract core details from aspects dict"""
    if not aspects:
        return {"brand": None, "model": None, "size": None, "color": None, "era": None}
    return {
        "brand": aspects.get("Brand"),
        "model": aspects.get("Model"),
        "size": aspects.get("Size") or aspects.get("Width"),
        "color": aspects.get("Color"),
        "era": aspects.get("Era") or aspects.get("Decade")
    }

def merge_core_to_aspects(aspects: dict, brand: str, model: str, size: str, color: str, era: str) -> dict:
    """Merge core details back into aspects dict"""
    if aspects is None:
        aspects = {}
    if brand:
        aspects["Brand"] = brand
    if model:
        aspects["Model"] = model
    if size:
        aspects["Size"] = size
    if color:
        aspects["Color"] = color
    if era:
        aspects["Era"] = era
    return aspects

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
        "aspects": {},  # Initialize as empty dict, not None
        "aspects_metadata": {},  # {field: {source, confidence}}
        # Core details (always present)
        "brand": None,
        "model": None,
        "size": None,
        "color": None,
        "era": None,
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
    
    # Ensure core details are extracted for each draft
    result = []
    for d in drafts:
        # Extract core details from aspects if not present at top level
        if not d.get("brand") and d.get("aspects"):
            core = extract_core_details(d.get("aspects", {}))
            d.update(core)
        result.append(DraftResponse(**d))
    return result

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
    
    # Filter out unwanted aspects (Model, Color, Type, Item Type, Material, Notes)
    excluded_aspects = ["Model", "Color", "Type", "Item Type", "Material", "Notes"]
    filtered_aspects = {k: v for k, v in (draft.get("aspects") or {}).items() if k not in excluded_aspects}
    
    return {
        "id": draft["id"],
        "sku": draft["sku"],
        "title": draft.get("title") or "Untitled Draft",
        "price": draft.get("price", 0),
        "categoryId": draft.get("category_id", ""),
        "condition": draft.get("condition", "USED_GOOD"),
        "images": images,
        "aspects": filtered_aspects,
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
    
    # Extract core details from aspects if not present at top level
    if not draft.get("brand") and draft.get("aspects"):
        core = extract_core_details(draft.get("aspects", {}))
        draft.update(core)
    
    return DraftResponse(**draft)

@api_router.patch("/drafts/{draft_id}", response_model=DraftResponse)
async def update_draft(draft_id: str, update: DraftUpdate, user = Depends(get_current_user)):
    """Update draft with partial update support"""
    update_dict = update.model_dump(exclude_unset=True)
    
    # Handle core details -> merge into aspects
    core_fields = ["brand", "model", "size", "color", "era"]
    core_updates = {k: update_dict.pop(k) for k in core_fields if k in update_dict}
    
    # Get existing draft to merge aspects
    existing = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # Handle aspects merge properly
    # If aspects are provided in the update, use them as base (they include custom fields)
    # Otherwise, use existing aspects
    if "aspects" in update_dict and update_dict["aspects"] is not None:
        merged_aspects = update_dict["aspects"]
    else:
        merged_aspects = existing.get("aspects") or {}
    
    # Merge core fields into aspects
    if core_updates:
        for field, value in core_updates.items():
            if value is not None:
                # Map field name to aspect key
                aspect_key = field.capitalize() if field != "era" else "Era"
                merged_aspects[aspect_key] = value
                # Also update top-level core field
                update_dict[field] = value
    
    update_dict["aspects"] = merged_aspects
    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.drafts.find_one_and_update(
        {"id": draft_id},
        {"$set": update_dict},
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    result.pop("_id", None)
    
    # Extract core details for response
    if not result.get("brand") and result.get("aspects"):
        core = extract_core_details(result.get("aspects", {}))
        result.update(core)
    
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
async def autofill_draft_aspects(draft_id: str, force: bool = False, user = Depends(get_current_user)):
    """Auto-fill item specifics using LLM vision analysis of images.
    If force=True, re-fills all fields including manually edited ones.
    """
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=400, detail="LLM API key not configured")
    
    image_urls = draft.get("image_urls", [])
    existing_title = draft.get("title", "")
    
    # If no images, try to extract from title as fallback
    if not image_urls and not existing_title:
        raise HTTPException(status_code=400, detail="No images or title available for analysis")
    
    item_type = draft["item_type"]
    backend_url = os.environ.get('REACT_APP_BACKEND_URL', FRONTEND_URL.replace(':3000', ':8001'))
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        
        extracted_aspects = {}
        source = "photo"
        
        # Try vision analysis first if images available
        if image_urls:
            extraction_prompt = get_aspects_prompt_for_type(item_type)
            
            # Prepare image URLs and convert to base64
            import base64
            import httpx
            
            image_contents = []
            for url in image_urls[:3]:  # Limit to first 3 images for speed
                try:
                    # Make URL absolute
                    if url.startswith("http"):
                        img_url = url
                    else:
                        img_url = f"{backend_url}{url}"
                    
                    # Download image
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(img_url, timeout=10)
                        if resp.status_code == 200:
                            img_base64 = base64.b64encode(resp.content).decode('utf-8')
                            image_contents.append(ImageContent(image_base64=img_base64))
                except Exception as img_err:
                    logger.warning(f"Failed to download image {url}: {img_err}")
            
            if not image_contents:
                # No images could be downloaded, try title fallback
                pass
            else:
                # Create chat with vision model
                chat = LlmChat(
                    api_key=EMERGENT_LLM_KEY,
                    session_id=f"autofill-{draft_id}",
                    system_message="You are an expert at identifying vintage skateboard items from photos. Analyze images carefully and extract item specifics. Only provide values you can actually see or read from the images. Never guess or assume values. For each field, also provide a confidence score between 0 and 1."
                ).with_model("openai", "gpt-5.2")
                
                # Enhanced prompt to get confidence scores
                enhanced_prompt = extraction_prompt + """

ALSO include a "confidence" object with confidence scores (0-1) for each extracted field:
{
  "Brand": "...",
  "Model": "...",
  ...
  "confidence": {
    "Brand": 0.95,
    "Model": 0.8,
    ...
  }
}"""
                
                user_message = UserMessage(
                    text=f"Analyze these images of a vintage skateboard item and extract the item specifics.\n\n{enhanced_prompt}",
                    images=image_contents
                )
                
                response = await chat.send_message(user_message)
                source = "photo"
                
                # Parse JSON from response
                try:
                    json_start = response.find("{")
                    json_end = response.rfind("}") + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = response[json_start:json_end]
                        extracted_aspects = json.loads(json_str)
                except (json.JSONDecodeError, ValueError):
                    logger.warning("Failed to parse LLM vision response, trying title fallback")
        
        # Fallback to title extraction if vision didn't work or no images
        if not extracted_aspects and existing_title:
            source = "title"
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"autofill-title-{draft_id}",
                system_message="Extract item specifics from this skateboard listing title. Only extract values that are clearly present in the title. Never guess."
            ).with_model("openai", "gpt-5.2")
            
            title_prompt = f"""Extract item specifics from this title: "{existing_title}"

For item type {item_type}, extract: Brand, Model, Size, Color, Era/Decade.
Only include values clearly present in the title.

OUTPUT FORMAT (JSON):
{{
  "Brand": "",
  "Model": "",
  "Size": "",
  "Color": "",
  "Era": "",
  "confidence": {{
    "Brand": 0.0,
    "Model": 0.0,
    ...
  }}
}}"""
            
            response = await chat.send_message(title_prompt)
            try:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    extracted_aspects = json.loads(response[json_start:json_end])
            except (json.JSONDecodeError, ValueError):
                pass
        
        if not extracted_aspects:
            raise HTTPException(status_code=500, detail="Could not extract any aspects from images or title")
        
        # Extract confidence scores
        confidence_scores = extracted_aspects.pop("confidence", {})
        
        # Filter out empty values and "Unknown" type values
        invalid_values = ["unknown", "n/a", "na", "none", "", "assumed", "estimate", "possibly", "maybe", "unclear", "not visible", "cannot determine"]
        clean_aspects = {}
        aspects_metadata = {}
        auto_filled_keys = []
        
        for key, value in extracted_aspects.items():
            if key == "confidence":
                continue
            if value and str(value).strip().lower() not in invalid_values:
                clean_value = str(value).strip()
                conf = confidence_scores.get(key, 0.7)  # Default confidence
                
                # Skip low confidence values
                if isinstance(conf, (int, float)) and conf < 0.3:
                    continue
                
                clean_aspects[key] = clean_value
                aspects_metadata[key] = {
                    "source": source,
                    "confidence": conf if isinstance(conf, (int, float)) else 0.7
                }
                auto_filled_keys.append(key)
        
        # Merge with existing aspects
        existing_aspects = draft.get("aspects") or {}
        existing_metadata = draft.get("aspects_metadata") or {}
        
        # Only update aspects that haven't been manually edited (unless force=True)
        merged_aspects = existing_aspects.copy()
        merged_metadata = existing_metadata.copy()
        
        for key, value in clean_aspects.items():
            # Check if field was manually edited
            existing_source = existing_metadata.get(key, {}).get("source")
            if force or existing_source != "manual":
                merged_aspects[key] = value
                merged_metadata[key] = aspects_metadata[key]
        
        # Extract core details
        core_details = extract_core_details(merged_aspects)
        
        # Update draft
        update_data = {
            "aspects": merged_aspects,
            "aspects_metadata": merged_metadata,
            **core_details,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = await db.drafts.find_one_and_update(
            {"id": draft_id},
            {"$set": update_data},
            return_document=True
        )
        result.pop("_id", None)
        
        # Ensure core details in response
        if not result.get("brand"):
            result.update(core_details)
        
        return {
            "message": f"Auto-filled {len(auto_filled_keys)} aspects from {source}",
            "extracted_aspects": clean_aspects,
            "aspects_metadata": aspects_metadata,
            "auto_filled_keys": auto_filled_keys,
            "source": source,
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
    logger.info("=" * 60)
    logger.info(f"PUBLISHING DRAFT: {draft_id}")
    
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    logger.info(f"Draft SKU: {draft.get('sku')}")
    logger.info(f"Draft title: {draft.get('title', '')[:50]}...")
    
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
        logger.error(f"Validation errors: {errors}")
        await db.drafts.update_one(
            {"id": draft_id},
            {"$set": {"status": "ERROR", "error_message": "; ".join(errors), "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        raise HTTPException(status_code=400, detail={"errors": errors})
    
    logger.info(f"Validation passed. Policy IDs: fulfillment={settings.get('fulfillment_policy_id')}, return={settings.get('return_policy_id')}, payment={settings.get('payment_policy_id')}")
    
    # Check if merchant location exists, create if not
    if not settings.get("merchant_location_key"):
        logger.info("No merchant location set, creating one...")
        try:
            access_token = await get_ebay_access_token()
            location_key = "default_location"
            
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                # Try to create location
                location_payload = {
                    "location": {
                        "address": {
                            "addressLine1": "Via Roma 1",
                            "city": "Milan",
                            "stateOrProvince": "MI",
                            "postalCode": "20100",
                            "country": "IT"
                        }
                    },
                    "locationTypes": ["WAREHOUSE"],
                    "name": "Main Warehouse",
                    "merchantLocationStatus": "ENABLED"
                }
                
                create_resp = await http_client.post(
                    f"{EBAY_SANDBOX_API_URL}/sell/inventory/v1/location/{location_key}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json=location_payload
                )
                
                logger.info(f"Auto-create location: status={create_resp.status_code}")
                
                if create_resp.status_code in [200, 201, 204, 409]:  # 409 = already exists
                    settings["merchant_location_key"] = location_key
                    await db.settings.update_one(
                        {"_id": "app_settings"},
                        {"$set": {"merchant_location_key": location_key}},
                        upsert=True
                    )
                    logger.info(f"Location set to: {location_key}")
                else:
                    logger.warning(f"Could not create location: {create_resp.text[:200]}")
        except Exception as loc_err:
            logger.warning(f"Location creation failed: {loc_err}")
    
    try:
        access_token = await get_ebay_access_token()
        
        # Get backend URL for image URLs - use FRONTEND_URL for public access
        backend_url = FRONTEND_URL
        
        # Convert relative URLs to absolute
        image_urls = []
        for url in draft.get("image_urls", []):
            if url.startswith("/api/"):
                image_urls.append(f"{backend_url}{url}")
            elif url.startswith("http"):
                image_urls.append(url)
            else:
                image_urls.append(f"{backend_url}/api/uploads/{url}")
        
        logger.info(f"Image URLs: {image_urls}")
        
        # Build aspects dict - filter out empty values
        aspects = {}
        for k, v in (draft.get("aspects") or {}).items():
            if v and str(v).strip():
                aspects[k] = [str(v)]
        
        logger.info(f"Aspects: {aspects}")
        
        # 1. Create Inventory Item
        inventory_payload = {
            "product": {
                "title": draft["title"],
                "description": draft.get("description", ""),
                "aspects": aspects,
                "imageUrls": image_urls
            },
            "condition": draft.get("condition", "USED_GOOD"),
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": 1
                }
            }
        }
        
        logger.info(f"Step 1: Creating inventory item for SKU {draft['sku']}")
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
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
            
            logger.info(f"createOrReplaceInventoryItem: status={inv_response.status_code}")
            logger.info(f"  Response: {inv_response.text[:500] if inv_response.text else 'empty'}")
            
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
            
            logger.info(f"Step 2: Creating offer...")
            
            # Clean categoryId - remove any text description, keep only the number
            raw_category_id = str(draft["category_id"])
            # Extract just the numeric part
            category_id = ''.join(c for c in raw_category_id.split()[0] if c.isdigit())
            if not category_id:
                category_id = ''.join(c for c in raw_category_id if c.isdigit())
            
            logger.info(f"Category ID: raw='{raw_category_id}' -> cleaned='{category_id}'")
            
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
                "categoryId": category_id,
                "listingPolicies": {
                    "fulfillmentPolicyId": settings["fulfillment_policy_id"],
                    "returnPolicyId": settings["return_policy_id"],
                    "paymentPolicyId": settings["payment_policy_id"]
                },
                "countryCode": "US",
                "listingDescription": draft.get("description", "")
            }
            
            if settings.get("merchant_location_key"):
                offer_payload["merchantLocationKey"] = settings["merchant_location_key"]
            
            logger.info(f"Offer payload: {str(offer_payload)[:300]}...")
            
            # First, check if an offer already exists for this SKU
            offer_id = draft.get("offer_id")
            
            if not offer_id:
                # Try to get existing offers for this SKU
                logger.info(f"Checking for existing offers for SKU {draft['sku']}...")
                get_offers_resp = await http_client.get(
                    f"{EBAY_SANDBOX_API_URL}/sell/inventory/v1/offer",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"sku": draft["sku"]}
                )
                
                if get_offers_resp.status_code == 200:
                    offers_data = get_offers_resp.json()
                    existing_offers = offers_data.get("offers", [])
                    if existing_offers:
                        offer_id = existing_offers[0].get("offerId")
                        logger.info(f"Found existing offer: {offer_id}")
            
            if offer_id:
                # Update existing offer
                logger.info(f"Updating existing offer {offer_id}...")
                offer_response = await http_client.put(
                    f"{EBAY_SANDBOX_API_URL}/sell/inventory/v1/offer/{offer_id}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "Content-Language": "en-US"
                    },
                    json=offer_payload
                )
                
                logger.info(f"updateOffer: status={offer_response.status_code}")
                logger.info(f"  Response: {offer_response.text[:500] if offer_response.text else 'empty'}")
                
                if offer_response.status_code not in [200, 204]:
                    # If update fails, try to publish anyway
                    logger.warning(f"Update offer failed, trying to publish existing offer...")
            else:
                # Create new offer
                offer_response = await http_client.post(
                    f"{EBAY_SANDBOX_API_URL}/sell/inventory/v1/offer",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "Content-Language": "en-US"
                    },
                    json=offer_payload
                )
                
                logger.info(f"createOffer: status={offer_response.status_code}")
                logger.info(f"  Response: {offer_response.text[:500] if offer_response.text else 'empty'}")
                
                await db.api_logs.insert_one({
                    "endpoint": "createOffer",
                    "sku": draft["sku"],
                    "status_code": offer_response.status_code,
                    "response": offer_response.text[:1000] if offer_response.text else None,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                
                if offer_response.status_code == 201:
                    offer_data = offer_response.json()
                    offer_id = offer_data["offerId"]
                elif offer_response.status_code == 400:
                    # Check if "already exists" error
                    try:
                        err_data = offer_response.json()
                        for err in err_data.get("errors", []):
                            if "already exists" in err.get("message", "").lower():
                                # Extract offerId from parameters
                                for param in err.get("parameters", []):
                                    if param.get("name") == "offerId":
                                        offer_id = param.get("value")
                                        logger.info(f"Offer already exists, using: {offer_id}")
                                        break
                    except:
                        pass
                
                if not offer_id:
                    raise Exception(f"Offer creation failed: {offer_response.text}")
            
            logger.info(f"Step 3: Publishing offer {offer_id}...")
            
            # 3. Publish Offer
            publish_response = await http_client.post(
                f"{EBAY_SANDBOX_API_URL}/sell/inventory/v1/offer/{offer_id}/publish",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            logger.info(f"publishOffer: status={publish_response.status_code}")
            logger.info(f"  Response: {publish_response.text[:500] if publish_response.text else 'empty'}")
            
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
            
            logger.info(f"SUCCESS! Listing ID: {listing_id}")
            logger.info("=" * 60)
            
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
    """Fetch business policies from eBay, create defaults if none exist"""
    try:
        access_token = await get_ebay_access_token()
        marketplace_id = "EBAY_US"
        
        logger.info("=" * 60)
        logger.info(f"FETCHING EBAY POLICIES for marketplace: {marketplace_id}")
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Content-Language": "en-US"
            }
            
            # 0. First, opt-in to Business Policies (SELLING_POLICY_MANAGEMENT)
            logger.info("Step 0: Opting in to Business Policies...")
            opt_in_resp = await http_client.post(
                f"{EBAY_SANDBOX_API_URL}/sell/account/v1/program/opt_in",
                headers=headers,
                json={"programType": "SELLING_POLICY_MANAGEMENT"}
            )
            logger.info(f"POST opt_in: status={opt_in_resp.status_code}")
            logger.info(f"  Response body: {opt_in_resp.text[:500] if opt_in_resp.text else 'empty'}")
            
            # If opt-in succeeded or already opted in, continue
            if opt_in_resp.status_code in [200, 204]:
                logger.info("  Opt-in successful!")
            elif opt_in_resp.status_code == 400:
                # Check if already opted in
                try:
                    err_data = opt_in_resp.json()
                    err_msg = str(err_data)
                    if "already" in err_msg.lower() or "opted" in err_msg.lower():
                        logger.info("  Already opted in to Business Policies")
                    else:
                        logger.warning(f"  Opt-in failed: {err_msg}")
                except:
                    logger.warning(f"  Opt-in returned 400: {opt_in_resp.text[:200]}")
            else:
                logger.warning(f"  Opt-in returned {opt_in_resp.status_code}")
            
            # Small delay after opt-in
            await asyncio.sleep(1)
            
            # 1. Fetch Fulfillment Policies
            fulfillment_resp = await http_client.get(
                f"{EBAY_SANDBOX_API_URL}/sell/account/v1/fulfillment_policy",
                headers=headers,
                params={"marketplace_id": marketplace_id}
            )
            logger.info(f"GET fulfillment_policy: status={fulfillment_resp.status_code}")
            logger.info(f"  Response body: {fulfillment_resp.text[:500]}")
            
            # 2. Fetch Payment Policies
            payment_resp = await http_client.get(
                f"{EBAY_SANDBOX_API_URL}/sell/account/v1/payment_policy",
                headers=headers,
                params={"marketplace_id": marketplace_id}
            )
            logger.info(f"GET payment_policy: status={payment_resp.status_code}")
            logger.info(f"  Response body: {payment_resp.text[:500]}")
            
            # 3. Fetch Return Policies
            return_resp = await http_client.get(
                f"{EBAY_SANDBOX_API_URL}/sell/account/v1/return_policy",
                headers=headers,
                params={"marketplace_id": marketplace_id}
            )
            logger.info(f"GET return_policy: status={return_resp.status_code}")
            logger.info(f"  Response body: {return_resp.text[:500]}")
            
            # Parse responses
            fulfillment_policies = fulfillment_resp.json().get("fulfillmentPolicies", []) if fulfillment_resp.status_code == 200 else []
            payment_policies = payment_resp.json().get("paymentPolicies", []) if payment_resp.status_code == 200 else []
            return_policies = return_resp.json().get("returnPolicies", []) if return_resp.status_code == 200 else []
            
            logger.info(f"Found: {len(fulfillment_policies)} fulfillment, {len(payment_policies)} payment, {len(return_policies)} return policies")
            
            # Create default policies if any are missing
            created_policies = {"fulfillment": None, "payment": None, "return": None}
            
            # Create default Fulfillment Policy if none exist
            if not fulfillment_policies:
                logger.info("No fulfillment policies found, creating default...")
                create_resp = await http_client.post(
                    f"{EBAY_SANDBOX_API_URL}/sell/account/v1/fulfillment_policy",
                    headers=headers,
                    json={
                        "name": "Standard Shipping - International",
                        "marketplaceId": marketplace_id,
                        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                        "handlingTime": {"value": 3, "unit": "DAY"},
                        "shippingOptions": [{
                            "optionType": "DOMESTIC",
                            "costType": "FLAT_RATE",
                            "shippingServices": [{
                                "sortOrder": 1,
                                "shippingCarrierCode": "USPS",
                                "shippingServiceCode": "USPSPriority",
                                "shippingCost": {"value": "10.00", "currency": "USD"},
                                "additionalShippingCost": {"value": "5.00", "currency": "USD"},
                                "freeShipping": False,
                                "shipToLocations": {"regionIncluded": [{"regionName": "WORLDWIDE"}]}
                            }]
                        }]
                    }
                )
                logger.info(f"CREATE fulfillment_policy: status={create_resp.status_code}")
                logger.info(f"  Response: {create_resp.text[:500]}")
                if create_resp.status_code in [200, 201]:
                    created_policy = create_resp.json()
                    created_policies["fulfillment"] = created_policy.get("fulfillmentPolicyId")
                    fulfillment_policies = [created_policy]
            
            # Create default Payment Policy if none exist
            if not payment_policies:
                logger.info("No payment policies found, creating default...")
                # For Sandbox: use minimal payment policy without specific payment methods
                # eBay managed payments is the default for most marketplaces now
                create_resp = await http_client.post(
                    f"{EBAY_SANDBOX_API_URL}/sell/account/v1/payment_policy",
                    headers=headers,
                    json={
                        "name": "Standard Payment Policy",
                        "marketplaceId": marketplace_id,
                        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                        "immediatePay": False
                    }
                )
                logger.info(f"CREATE payment_policy: status={create_resp.status_code}")
                logger.info(f"  Response: {create_resp.text[:500]}")
                if create_resp.status_code in [200, 201]:
                    created_policy = create_resp.json()
                    created_policies["payment"] = created_policy.get("paymentPolicyId")
                    payment_policies = [created_policy]
            
            # Create default Return Policy if none exist
            if not return_policies:
                logger.info("No return policies found, creating default...")
                create_resp = await http_client.post(
                    f"{EBAY_SANDBOX_API_URL}/sell/account/v1/return_policy",
                    headers=headers,
                    json={
                        "name": "30 Day Returns",
                        "marketplaceId": marketplace_id,
                        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                        "returnsAccepted": True,
                        "returnPeriod": {"value": 30, "unit": "DAY"},
                        "refundMethod": "MONEY_BACK",
                        "returnShippingCostPayer": "BUYER"
                    }
                )
                logger.info(f"CREATE return_policy: status={create_resp.status_code}")
                logger.info(f"  Response: {create_resp.text[:500]}")
                if create_resp.status_code in [200, 201]:
                    created_policy = create_resp.json()
                    created_policies["return"] = created_policy.get("returnPolicyId")
                    return_policies = [created_policy]
            
            logger.info("=" * 60)
        
        return {
            "fulfillment_policies": fulfillment_policies,
            "payment_policies": payment_policies,
            "return_policies": return_policies,
            "created_policies": created_policies,
            "marketplace_id": marketplace_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch/create policies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/ebay/create-location")
async def create_merchant_location(user = Depends(get_current_user)):
    """Create a merchant location for eBay (required for publishing)"""
    try:
        access_token = await get_ebay_access_token()
        location_key = "default_location"
        
        logger.info("Creating merchant location...")
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # First check if location exists
            check_resp = await http_client.get(
                f"{EBAY_SANDBOX_API_URL}/sell/inventory/v1/location/{location_key}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if check_resp.status_code == 200:
                logger.info("Location already exists")
                # Save to settings
                await db.settings.update_one(
                    {"_id": "app_settings"},
                    {"$set": {"merchant_location_key": location_key}},
                    upsert=True
                )
                return {"message": "Location already exists", "location_key": location_key}
            
            # Create new location
            location_payload = {
                "location": {
                    "address": {
                        "addressLine1": "Via Roma 1",
                        "city": "Milan",
                        "stateOrProvince": "MI",
                        "postalCode": "20100",
                        "country": "IT"
                    }
                },
                "locationTypes": ["WAREHOUSE"],
                "name": "Main Warehouse",
                "merchantLocationStatus": "ENABLED"
            }
            
            create_resp = await http_client.post(
                f"{EBAY_SANDBOX_API_URL}/sell/inventory/v1/location/{location_key}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=location_payload
            )
            
            logger.info(f"Create location: status={create_resp.status_code}")
            logger.info(f"  Response: {create_resp.text[:500] if create_resp.text else 'empty'}")
            
            if create_resp.status_code in [200, 201, 204]:
                # Save to settings
                await db.settings.update_one(
                    {"_id": "app_settings"},
                    {"$set": {"merchant_location_key": location_key}},
                    upsert=True
                )
                return {"message": "Location created", "location_key": location_key}
            else:
                raise Exception(f"Failed to create location: {create_resp.text}")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create location error: {str(e)}")
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
                    except (json.JSONDecodeError, ValueError):
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
                "condition": "NEW",  # Default to NEW
                "title": title,
                "title_manually_edited": False,
                "description": description,
                "description_manually_edited": False,
                "aspects": aspects,
                "auto_filled_aspects": [],
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
