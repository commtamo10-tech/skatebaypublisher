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
import random
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
import jwt

# Import marketplace configuration
from ebay_config import (
    MARKETPLACE_CONFIG, 
    get_marketplace_config, 
    get_default_marketplace_config,
    get_all_marketplaces,
    get_category_for_item,
    validate_marketplace_config,
    FALLBACK_SHIPPING_SERVICES,
    DEFAULT_HANDLING_TIME,
    get_marketplace_domain
)

# Import exchange rates module
from exchange_rates import get_shipping_rates_for_marketplace, fetch_bce_rates

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

# eBay Environment from .env (can be overridden by DB settings)
EBAY_ENV_DEFAULT = os.environ.get('EBAY_ENV', 'sandbox')

EBAY_SCOPES = os.environ.get('EBAY_SCOPES', 'https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.account')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

# eBay OAuth URLs - MUST be exact
EBAY_SANDBOX_AUTH_URL = "https://auth.sandbox.ebay.com/oauth2/authorize"
EBAY_SANDBOX_TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
EBAY_SANDBOX_API_URL = "https://api.sandbox.ebay.com"

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


# ============ TAXONOMY LAYER - Category Validation per Marketplace ============

# Marketplace to Category Tree ID mapping (eBay Taxonomy API)
MARKETPLACE_CATEGORY_TREE = {
    "EBAY_US": "0",
    "EBAY_DE": "77",
    "EBAY_ES": "186",
    "EBAY_AU": "15",
    "EBAY_IT": "101",
    "EBAY_UK": "3",
}

# Cache for category suggestions to avoid repeated API calls
_category_cache = {}

async def get_category_suggestion_for_marketplace(
    http_client: httpx.AsyncClient,
    api_url: str,
    access_token: str,
    marketplace_id: str,
    query: str
) -> Optional[str]:
    """
    Get category suggestion from eBay Taxonomy API for a specific marketplace.
    Uses getCategorySuggestions to find the best category for the item.
    """
    cache_key = f"{marketplace_id}:{query}"
    if cache_key in _category_cache:
        logger.info(f"  Using cached category for {marketplace_id}: {_category_cache[cache_key]}")
        return _category_cache[cache_key]
    
    category_tree_id = MARKETPLACE_CATEGORY_TREE.get(marketplace_id)
    if not category_tree_id:
        logger.warning(f"  No category tree ID for {marketplace_id}")
        return None
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Use Commerce Taxonomy API to get category suggestions
    taxonomy_url = f"{api_url}/commerce/taxonomy/v1/category_tree/{category_tree_id}/get_category_suggestions"
    
    try:
        logger.info(f"  Fetching category suggestion for '{query}' on {marketplace_id}...")
        resp = await http_client.get(
            taxonomy_url,
            headers=headers,
            params={"q": query}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            suggestions = data.get("categorySuggestions", [])
            if suggestions:
                # Get the first (best) suggestion
                best_category = suggestions[0].get("category", {})
                category_id = best_category.get("categoryId")
                category_name = best_category.get("categoryName", "Unknown")
                logger.info(f"  Found category for {marketplace_id}: {category_id} ({category_name})")
                _category_cache[cache_key] = category_id
                return category_id
        else:
            logger.warning(f"  Taxonomy API error for {marketplace_id}: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        logger.error(f"  Error getting category suggestion: {e}")
    
    return None

async def get_valid_category_for_marketplace(
    http_client: httpx.AsyncClient,
    api_url: str,
    access_token: str,
    marketplace_id: str,
    item_type: str,
    title: str
) -> str:
    """
    Get a valid category ID for a specific marketplace.
    First tries to get a suggestion from eBay Taxonomy API,
    falls back to hardcoded mapping if API fails.
    """
    # Build search query based on item type and title
    type_queries = {
        "WHL": "skateboard wheels",
        "TRK": "skateboard trucks",
        "DCK": "skateboard deck",
        "APP": "skateboard clothing",
        "MISC": "skateboard accessories"
    }
    query = type_queries.get(item_type, "skateboard")
    
    # Try to get category from Taxonomy API
    suggested_category = await get_category_suggestion_for_marketplace(
        http_client, api_url, access_token, marketplace_id, query
    )
    
    if suggested_category:
        return suggested_category
    
    # Fallback to hardcoded categories
    from ebay_config import get_category_for_item
    fallback = get_category_for_item(item_type, marketplace_id)
    logger.info(f"  Using fallback category for {marketplace_id}: {fallback}")
    return fallback


# ============ RETRY HELPER WITH EXPONENTIAL BACKOFF ============

async def retry_with_backoff(
    http_client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict,
    json_body: dict = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
    context: str = ""
) -> Tuple[httpx.Response, int]:
    """
    Execute HTTP request with retry on 429 and 5xx errors.
    Uses exponential backoff with jitter.
    Respects Retry-After header for 429 responses.
    
    Returns: (response, attempt_number)
    """
    last_response = None
    
    for attempt in range(1, max_retries + 1):
        try:
            if method.upper() == "POST":
                response = await http_client.post(url, headers=headers, json=json_body)
            elif method.upper() == "PUT":
                response = await http_client.put(url, headers=headers, json=json_body)
            elif method.upper() == "GET":
                response = await http_client.get(url, headers=headers)
            elif method.upper() == "DELETE":
                response = await http_client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            last_response = response
            
            # Check if we should retry
            if response.status_code == 429 or response.status_code >= 500:
                error_body = response.text[:300] if response.text else "No body"
                logger.warning(f"🔄 RETRY {attempt}/{max_retries} [{context}] - Status: {response.status_code}")
                logger.warning(f"   Error body: {error_body}")
                
                if attempt < max_retries:
                    # Calculate delay
                    if response.status_code == 429:
                        # Respect Retry-After header if present
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = float(retry_after)
                                logger.info(f"   Using Retry-After header: {delay}s")
                            except ValueError:
                                delay = base_delay * (2 ** (attempt - 1))
                        else:
                            delay = base_delay * (2 ** (attempt - 1))
                    else:
                        # Exponential backoff with jitter for 5xx
                        delay = base_delay * (2 ** (attempt - 1))
                    
                    # Add jitter (±25%)
                    jitter = delay * 0.25 * (random.random() * 2 - 1)
                    delay = max(0.5, delay + jitter)
                    
                    logger.info(f"   Waiting {delay:.2f}s before retry...")
                    await asyncio.sleep(delay)
                    continue
            
            # Success or non-retryable error
            return response, attempt
            
        except httpx.TimeoutException as e:
            logger.warning(f"🔄 RETRY {attempt}/{max_retries} [{context}] - Timeout: {str(e)}")
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                jitter = delay * 0.25 * (random.random() * 2 - 1)
                delay = max(0.5, delay + jitter)
                logger.info(f"   Waiting {delay:.2f}s before retry...")
                await asyncio.sleep(delay)
            else:
                raise
    
    # Return last response after all retries exhausted
    return last_response, max_retries


# ============ EBAY ENVIRONMENT HELPERS ============

async def get_ebay_environment():
    """Get current eBay environment (sandbox or production) from settings or env"""
    settings = await db.settings.find_one({"_id": "app_settings"})
    if settings and settings.get("ebay_environment"):
        return settings.get("ebay_environment")
    # Fall back to env variable
    return EBAY_ENV_DEFAULT

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
    listing_id: Optional[str] = None
    # Core Details fields (always present)
    brand: Optional[str] = None
    model: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    era: Optional[str] = None
    # NEW: Category per marketplace
    category_by_marketplace: Optional[Dict[str, str]] = None  # {EBAY_US: "123", EBAY_DE: "456", ...}

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
    # Multi-marketplace support
    marketplace_listings: Optional[Dict[str, Dict[str, Any]]] = None
    multi_marketplace_results: Optional[Dict[str, Any]] = None

class SettingsUpdate(BaseModel):
    fulfillment_policy_id: Optional[str] = None
    return_policy_id: Optional[str] = None
    payment_policy_id: Optional[str] = None
    merchant_location_key: Optional[str] = None
    ebay_environment: Optional[str] = None  # "sandbox" or "production"
    # Per-marketplace settings (nested dict)
    marketplaces: Optional[Dict[str, Dict[str, Any]]] = None

class SettingsResponse(BaseModel):
    fulfillment_policy_id: Optional[str] = None
    return_policy_id: Optional[str] = None
    payment_policy_id: Optional[str] = None
    merchant_location_key: Optional[str] = None
    ebay_connected: bool = False
    ebay_environment: str = "sandbox"
    marketplaces: Optional[Dict[str, Dict[str, Any]]] = None


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
    """Get description template structure based on item type - Clean minimal style"""
    
    # Clean minimal header
    header = """<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
"""

    footer = """
<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">

<p style="font-size: 13px; color: #666;">
<strong>Shipping:</strong> Ships from Milan, Italy. Combined shipping available—message before purchase.<br>
International buyers: import duties/taxes not included.
</p>

<p style="font-size: 13px; color: #666;">
Questions? Message me! Thanks for looking! 🛹
</p>

</div>
"""
    
    if item_type == "APP":
        return f"""{header}
<p>[Write 2-3 sentences for vintage streetwear collectors. Mention the era/brand heritage.]</p>

<h3 style="border-bottom: 2px solid #333; padding-bottom: 5px;">Details</h3>
<ul style="line-height: 1.8;">
  <li><strong>Brand:</strong> [value]</li>
  <li><strong>Type:</strong> [T-shirt/Hoodie/etc.]</li>
  <li><strong>Size:</strong> [tag size]</li>
  <li><strong>Color:</strong> [value]</li>
  <li><strong>Era:</strong> [decade if known]</li>
</ul>

<h3 style="border-bottom: 2px solid #333; padding-bottom: 5px;">Condition</h3>
<p>[Brief honest description]. Please review all photos carefully.</p>
{footer}"""
    
    elif item_type == "WHL":
        return f"""{header}
<p>[Write 2-3 sentences for vintage wheel collectors. Mention brand heritage.]</p>

<h3 style="border-bottom: 2px solid #333; padding-bottom: 5px;">Wheel Specs</h3>
<ul style="line-height: 1.8;">
  <li><strong>Brand:</strong> [value]</li>
  <li><strong>Model:</strong> [value]</li>
  <li><strong>Size:</strong> [diameter mm]</li>
  <li><strong>Durometer:</strong> [hardness A]</li>
  <li><strong>Color:</strong> [value]</li>
  <li><strong>Quantity:</strong> [set of 4/pair/single]</li>
</ul>

<h3 style="border-bottom: 2px solid #333; padding-bottom: 5px;">Condition</h3>
<p>[Brief description]. Please review all photos carefully.</p>
{footer}"""
    
    elif item_type == "TRK":
        return f"""{header}
<p>[Write 2-3 sentences for vintage truck collectors.]</p>

<h3 style="border-bottom: 2px solid #333; padding-bottom: 5px;">Truck Specs</h3>
<ul style="line-height: 1.8;">
  <li><strong>Brand:</strong> [value]</li>
  <li><strong>Model:</strong> [value]</li>
  <li><strong>Hanger Width:</strong> [size]</li>
  <li><strong>Color:</strong> [value]</li>
  <li><strong>Quantity:</strong> [pair/single]</li>
</ul>

<h3 style="border-bottom: 2px solid #333; padding-bottom: 5px;">Condition</h3>
<p>[Brief description]. Please review all photos carefully.</p>
{footer}"""
    
    elif item_type == "DCK":
        return f"""{header}
<p>[Write 2-3 sentences for vintage deck collectors. Mention artist, rarity.]</p>

<h3 style="border-bottom: 2px solid #333; padding-bottom: 5px;">Deck Specs</h3>
<ul style="line-height: 1.8;">
  <li><strong>Brand:</strong> [value]</li>
  <li><strong>Model/Series:</strong> [value]</li>
  <li><strong>Size:</strong> [width inches]</li>
  <li><strong>Era:</strong> [decade]</li>
  <li><strong>Type:</strong> [OG/Reissue]</li>
</ul>

<h3 style="border-bottom: 2px solid #333; padding-bottom: 5px;">Condition</h3>
<p>[Brief description]. Please review all photos carefully.</p>
{footer}"""
    
    else:
        return f"""{header}
<p>[Write 2-3 sentences for vintage skateboard collectors.]</p>

<h3 style="border-bottom: 2px solid #333; padding-bottom: 5px;">Details</h3>
<ul style="line-height: 1.8;">
  <li><strong>Brand:</strong> [value]</li>
  <li><strong>Type:</strong> [value]</li>
  <li><strong>Era:</strong> [decade if known]</li>
</ul>

<h3 style="border-bottom: 2px solid #333; padding-bottom: 5px;">Condition</h3>
<p>[Brief description]. Please review all photos carefully.</p>
{footer}"""


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

@api_router.get("/ebay/oauth/config")
async def get_ebay_oauth_config(user = Depends(get_current_user)):
    """Debug endpoint to check OAuth configuration"""
    environment = await get_ebay_environment()
    config = get_ebay_config(environment)
    
    # Check what's configured
    sandbox_configured = bool(EBAY_CLIENT_ID and EBAY_REDIRECT_URI)
    prod_configured = bool(EBAY_PROD_CLIENT_ID and EBAY_PROD_REDIRECT_URI)
    
    return {
        "current_environment": environment,
        "env_default": EBAY_ENV_DEFAULT,
        "sandbox": {
            "configured": sandbox_configured,
            "client_id": EBAY_CLIENT_ID[:20] + "..." if EBAY_CLIENT_ID else None,
            "redirect_uri": EBAY_REDIRECT_URI,
            "runame": EBAY_RUNAME or None,
            "auth_url": EBAY_SANDBOX_AUTH_URL,
            "token_url": EBAY_SANDBOX_TOKEN_URL
        },
        "production": {
            "configured": prod_configured,
            "client_id": EBAY_PROD_CLIENT_ID[:20] + "..." if EBAY_PROD_CLIENT_ID else None,
            "redirect_uri": EBAY_PROD_REDIRECT_URI,
            "runame": EBAY_PROD_RUNAME or None,
            "auth_url": EBAY_PROD_AUTH_URL,
            "token_url": EBAY_PROD_TOKEN_URL
        },
        "scopes": EBAY_SCOPES.split(" "),
        "active_config": {
            "auth_url": config["auth_url"],
            "token_url": config["token_url"],
            "redirect_uri": config["runame"] or config["redirect_uri"]
        }
    }

@api_router.get("/ebay/auth/start")
async def ebay_auth_start(user = Depends(get_current_user)):
    """Start eBay OAuth flow"""
    from urllib.parse import quote
    
    # Get current environment
    environment = await get_ebay_environment()
    config = get_ebay_config(environment)
    
    logger.info("=" * 60)
    logger.info(f"🔐 EBAY OAUTH START - Environment: {environment.upper()}")
    logger.info("=" * 60)
    
    # Validate client_id
    if not config["client_id"]:
        error_msg = f"eBay {environment} credentials not configured. Please add EBAY_{'PROD_' if environment == 'production' else ''}CLIENT_ID to .env"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    
    # For OAuth2, redirect_uri must be the FULL URL, not the RuName
    # The RuName is just an identifier in eBay's system
    # The redirect_uri in the authorize request must match EXACTLY what's registered
    redirect_uri = config["redirect_uri"]
    if not redirect_uri:
        error_msg = f"eBay {environment} Redirect URI not configured in .env"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Validate scopes
    if not EBAY_SCOPES:
        error_msg = "eBay scopes not configured"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Generate random state for CSRF protection
    state = secrets.token_urlsafe(32)
    await db.oauth_states.insert_one({
        "state": state,
        "environment": environment,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    })
    
    # Build authorize URL with ALL required parameters
    # Reference: https://developer.ebay.com/api-docs/static/oauth-authorization-code-grant.html
    # IMPORTANT: scope must be space-separated and URL-encoded with %20 (not +)
    auth_base_url = config["auth_url"]
    
    # Build query string manually to ensure correct encoding
    # - scope: spaces become %20 (not +)
    # - redirect_uri: must be exactly as registered
    query_parts = [
        f"client_id={quote(config['client_id'], safe='')}",
        "response_type=code",
        f"redirect_uri={quote(redirect_uri, safe='')}",
        f"scope={quote(EBAY_SCOPES, safe='')}",  # Spaces become %20
        f"state={quote(state, safe='')}"
    ]
    query_string = "&".join(query_parts)
    auth_url = f"{auth_base_url}?{query_string}"
    
    # Detailed logging (no secrets)
    logger.info("📋 OAuth Parameters:")
    logger.info(f"   auth_base_url: {auth_base_url}")
    logger.info(f"   client_id: {config['client_id']}")
    logger.info(f"   response_type: code")
    logger.info(f"   redirect_uri: {redirect_uri}")
    logger.info(f"   scope: {EBAY_SCOPES}")
    logger.info(f"   state: {state[:20]}...")
    logger.info("")
    logger.info(f"🔗 FULL AUTHORIZE URL:")
    logger.info(f"   {auth_url}")
    logger.info("=" * 60)
    
    return {
        "auth_url": auth_url, 
        "environment": environment,
        "debug": {
            "auth_base_url": auth_base_url,
            "client_id": config["client_id"],
            "redirect_uri": redirect_uri,
            "scopes": EBAY_SCOPES.split(" ")
        }
    }

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


async def get_ebay_app_token() -> str:
    """Get an Application Access Token for APIs that don't require user context (e.g., Taxonomy)"""
    environment = await get_ebay_environment()
    app_token_id = f"ebay_app_token_{environment}"
    
    # Check if we have a valid cached app token
    cached = await db.ebay_tokens.find_one({"_id": app_token_id})
    if cached:
        expiry = datetime.fromisoformat(cached.get("token_expiry", "2000-01-01T00:00:00+00:00").replace("Z", "+00:00"))
        if expiry > datetime.now(timezone.utc):
            return cached["access_token"]
    
    # Get new app token using client credentials
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
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope"
            }
        )
    
    if response.status_code != 200:
        logger.error(f"Failed to get app token: {response.status_code} - {response.text}")
        raise HTTPException(status_code=500, detail="Failed to get eBay application token")
    
    token_data = response.json()
    
    # Cache the app token
    await db.ebay_tokens.update_one(
        {"_id": app_token_id},
        {
            "$set": {
                "access_token": token_data["access_token"],
                "token_expiry": (datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 7200))).isoformat(),
                "environment": environment,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
    return token_data["access_token"]


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
    """Delete draft and unpublish from eBay if published"""
    
    # Get draft first to check if it has a listing
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    sku = draft.get("sku")
    listing_id = draft.get("listing_id")
    offer_id = draft.get("offer_id")
    multi_results = draft.get("multi_marketplace_results", {})
    marketplace_listings = draft.get("marketplace_listings", {})
    
    ebay_errors = []
    
    # If published on eBay, try to end the listing
    if listing_id or multi_results or marketplace_listings:
        logger.info(f"🗑️ Deleting eBay listing for draft {draft_id}, SKU: {sku}")
        
        try:
            access_token = await get_ebay_access_token()
            environment = await get_ebay_environment()
            config = get_ebay_config(environment)
            api_url = config["api_url"]
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                # Collect all SKUs to delete (base SKU + marketplace-specific SKUs)
                skus_to_delete = set()
                if sku:
                    skus_to_delete.add(sku)
                
                # Add marketplace-specific SKUs
                for mp_id, mp_data in marketplace_listings.items():
                    mp_sku = mp_data.get("sku")
                    if mp_sku:
                        skus_to_delete.add(mp_sku)
                        logger.info(f"  Found marketplace SKU: {mp_sku} ({mp_id})")
                
                logger.info(f"  SKUs to delete: {skus_to_delete}")
                
                # Process each SKU
                for current_sku in skus_to_delete:
                    logger.info(f"  Processing SKU: {current_sku}")
                    
                    # Get all offers for this SKU
                    offers_resp = await http_client.get(
                        f"{api_url}/sell/inventory/v1/offer",
                        headers=headers,
                        params={"sku": current_sku}
                    )
                    
                    if offers_resp.status_code == 200:
                        offers = offers_resp.json().get("offers", [])
                        logger.info(f"    Found {len(offers)} offers for SKU {current_sku}")
                        
                        for offer in offers:
                            offer_id = offer.get("offerId")
                            listing_status = offer.get("status")
                            marketplace = offer.get("marketplaceId", "?")
                            
                            if listing_status == "PUBLISHED":
                                # Withdraw the offer (ends the listing)
                                logger.info(f"    Withdrawing offer {offer_id} ({marketplace})...")
                                withdraw_resp = await http_client.post(
                                    f"{api_url}/sell/inventory/v1/offer/{offer_id}/withdraw",
                                    headers=headers
                                )
                                if withdraw_resp.status_code in [200, 204]:
                                    logger.info(f"    ✅ Offer {offer_id} withdrawn successfully")
                                else:
                                    error_msg = f"Failed to withdraw offer {offer_id}: {withdraw_resp.text[:200]}"
                                    logger.warning(f"    ⚠️ {error_msg}")
                                    ebay_errors.append(error_msg)
                            
                            # Delete the offer
                            logger.info(f"    Deleting offer {offer_id}...")
                            delete_offer_resp = await http_client.delete(
                                f"{api_url}/sell/inventory/v1/offer/{offer_id}",
                                headers=headers
                            )
                            if delete_offer_resp.status_code in [200, 204]:
                                logger.info(f"    ✅ Offer {offer_id} deleted")
                            else:
                                logger.warning(f"    ⚠️ Could not delete offer: {delete_offer_resp.status_code}")
                    
                    # Delete the inventory item for this SKU
                    logger.info(f"  Deleting inventory item {current_sku}...")
                    delete_inv_resp = await http_client.delete(
                        f"{api_url}/sell/inventory/v1/inventory_item/{current_sku}",
                        headers=headers
                    )
                    if delete_inv_resp.status_code in [200, 204]:
                        logger.info(f"  ✅ Inventory item {current_sku} deleted")
                    else:
                        logger.warning(f"  ⚠️ Could not delete inventory item: {delete_inv_resp.status_code}")
                    
        except HTTPException as e:
            logger.warning(f"  ⚠️ eBay not connected, skipping eBay deletion: {e.detail}")
            ebay_errors.append(f"eBay not connected: {e.detail}")
        except Exception as e:
            logger.error(f"  ❌ Error deleting from eBay: {str(e)}")
            ebay_errors.append(str(e))
    
    # Delete from local database
    result = await db.drafts.delete_one({"id": draft_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    response = {"message": "Draft deleted"}
    if listing_id or multi_results:
        response["ebay_deleted"] = len(ebay_errors) == 0
        if ebay_errors:
            response["ebay_errors"] = ebay_errors
            response["message"] = "Draft deleted locally. Some eBay listings may need manual removal."
        else:
            response["message"] = "Draft and eBay listing deleted successfully"
    
    logger.info(f"✅ Draft {draft_id} deleted. eBay errors: {ebay_errors}")
    return response


@api_router.delete("/drafts/{draft_id}/marketplace/{marketplace_id}")
async def delete_draft_marketplace(draft_id: str, marketplace_id: str, user = Depends(get_current_user)):
    """Delete a single marketplace listing from eBay without deleting the draft"""
    
    # Get draft first
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    marketplace_listings = draft.get("marketplace_listings", {})
    multi_results = draft.get("multi_marketplace_results", {})
    
    if marketplace_id not in marketplace_listings:
        raise HTTPException(status_code=404, detail=f"Marketplace {marketplace_id} not found in this draft")
    
    mp_data = marketplace_listings[marketplace_id]
    mp_sku = mp_data.get("sku")
    mp_offer_id = mp_data.get("offer_id")
    
    logger.info(f"🗑️ Deleting single marketplace listing: {marketplace_id} for draft {draft_id}, SKU: {mp_sku}")
    
    ebay_errors = []
    
    try:
        access_token = await get_ebay_access_token()
        environment = await get_ebay_environment()
        config = get_ebay_config(environment)
        api_url = config["api_url"]
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # Get all offers for this SKU
            offers_resp = await http_client.get(
                f"{api_url}/sell/inventory/v1/offer",
                headers=headers,
                params={"sku": mp_sku}
            )
            
            if offers_resp.status_code == 200:
                offers = offers_resp.json().get("offers", [])
                logger.info(f"  Found {len(offers)} offers for SKU {mp_sku}")
                
                for offer in offers:
                    offer_id = offer.get("offerId")
                    listing_status = offer.get("status")
                    
                    if listing_status == "PUBLISHED":
                        # Withdraw the offer
                        logger.info(f"  Withdrawing offer {offer_id}...")
                        withdraw_resp = await http_client.post(
                            f"{api_url}/sell/inventory/v1/offer/{offer_id}/withdraw",
                            headers=headers
                        )
                        if withdraw_resp.status_code in [200, 204]:
                            logger.info(f"  ✅ Offer {offer_id} withdrawn successfully")
                        else:
                            error_msg = f"Failed to withdraw offer {offer_id}: {withdraw_resp.text[:200]}"
                            logger.warning(f"  ⚠️ {error_msg}")
                            ebay_errors.append(error_msg)
                    
                    # Delete the offer
                    logger.info(f"  Deleting offer {offer_id}...")
                    delete_offer_resp = await http_client.delete(
                        f"{api_url}/sell/inventory/v1/offer/{offer_id}",
                        headers=headers
                    )
                    if delete_offer_resp.status_code in [200, 204]:
                        logger.info(f"  ✅ Offer {offer_id} deleted")
                    else:
                        logger.warning(f"  ⚠️ Could not delete offer: {delete_offer_resp.status_code}")
            
            # Delete the inventory item for this marketplace SKU
            logger.info(f"  Deleting inventory item {mp_sku}...")
            delete_inv_resp = await http_client.delete(
                f"{api_url}/sell/inventory/v1/inventory_item/{mp_sku}",
                headers=headers
            )
            if delete_inv_resp.status_code in [200, 204]:
                logger.info(f"  ✅ Inventory item {mp_sku} deleted")
            else:
                logger.warning(f"  ⚠️ Could not delete inventory item: {delete_inv_resp.status_code}")
                
    except HTTPException as e:
        logger.warning(f"  ⚠️ eBay not connected: {e.detail}")
        ebay_errors.append(f"eBay not connected: {e.detail}")
    except Exception as e:
        logger.error(f"  ❌ Error deleting from eBay: {str(e)}")
        ebay_errors.append(str(e))
    
    # Update draft to remove this marketplace from listings
    del marketplace_listings[marketplace_id]
    if marketplace_id in multi_results:
        del multi_results[marketplace_id]
    
    # Update draft status if no more listings
    update_data = {
        "marketplace_listings": marketplace_listings,
        "multi_marketplace_results": multi_results,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if not marketplace_listings:
        # No more marketplaces - set status back to DRAFT
        update_data["status"] = "DRAFT"
        update_data["listing_id"] = None
        update_data["offer_id"] = None
    
    await db.drafts.update_one({"id": draft_id}, {"$set": update_data})
    
    response = {
        "message": f"Listing removed from {marketplace_id}",
        "remaining_marketplaces": list(marketplace_listings.keys()),
        "ebay_deleted": len(ebay_errors) == 0
    }
    if ebay_errors:
        response["ebay_errors"] = ebay_errors
    
    logger.info(f"✅ Marketplace {marketplace_id} deleted from draft {draft_id}. Remaining: {list(marketplace_listings.keys())}")
    return response


@api_router.post("/drafts/{draft_id}/sync-marketplaces")
async def sync_draft_marketplaces(draft_id: str, user = Depends(get_current_user)):
    """Sync marketplace listings from eBay for drafts that were published before the multi-marketplace feature"""
    
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft.get("status") != "PUBLISHED":
        raise HTTPException(status_code=400, detail="Draft is not published")
    
    sku = draft.get("sku")
    if not sku:
        raise HTTPException(status_code=400, detail="Draft has no SKU")
    
    logger.info(f"🔄 Syncing marketplace listings for draft {draft_id}, SKU: {sku}")
    
    try:
        access_token = await get_ebay_access_token()
        environment = await get_ebay_environment()
        config = get_ebay_config(environment)
        api_url = config["api_url"]
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        marketplace_listings = {}
        
        # Check for marketplace-specific SKUs
        marketplace_suffixes = {
            "EBAY_US": "us",
            "EBAY_DE": "de", 
            "EBAY_ES": "es",
            "EBAY_AU": "au"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            for mp_id, suffix in marketplace_suffixes.items():
                mp_sku = f"{sku}-{suffix}"
                
                # Try to get offers for this SKU
                offers_resp = await http_client.get(
                    f"{api_url}/sell/inventory/v1/offer",
                    headers=headers,
                    params={"sku": mp_sku}
                )
                
                if offers_resp.status_code == 200:
                    offers = offers_resp.json().get("offers", [])
                    for offer in offers:
                        if offer.get("status") == "PUBLISHED":
                            listing_id = offer.get("listing", {}).get("listingId")
                            offer_id = offer.get("offerId")
                            mp_config = MARKETPLACE_CONFIG.get(mp_id, {})
                            domain = mp_config.get("domain", "ebay.com")
                            
                            marketplace_listings[mp_id] = {
                                "sku": mp_sku,
                                "offer_id": offer_id,
                                "listing_id": listing_id,
                                "listing_url": f"https://www.{domain}/itm/{listing_id}" if listing_id else None
                            }
                            logger.info(f"  Found {mp_id}: SKU={mp_sku}, listing={listing_id}")
        
        if marketplace_listings:
            # Update draft with synced marketplace listings
            await db.drafts.update_one(
                {"id": draft_id},
                {"$set": {
                    "marketplace_listings": marketplace_listings,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            logger.info(f"✅ Synced {len(marketplace_listings)} marketplaces for draft {draft_id}")
            return {
                "message": f"Synced {len(marketplace_listings)} marketplaces",
                "marketplace_listings": marketplace_listings
            }
        else:
            return {
                "message": "No marketplace listings found on eBay",
                "marketplace_listings": {}
            }
            
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error syncing marketplaces: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/drafts/{draft_id}/republish")
async def republish_draft(draft_id: str, user = Depends(get_current_user)):
    """Republish a published draft after modifications (updates existing listings on all marketplaces)"""
    
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft.get("status") != "PUBLISHED":
        raise HTTPException(status_code=400, detail="Draft is not published. Use publish-multi instead.")
    
    marketplace_listings = draft.get("marketplace_listings", {})
    if not marketplace_listings:
        raise HTTPException(status_code=400, detail="No marketplace listings found. Use sync-marketplaces first.")
    
    sku = draft.get("sku")
    logger.info(f"🔄 Republishing draft {draft_id}, SKU: {sku}")
    logger.info(f"  Marketplaces to update: {list(marketplace_listings.keys())}")
    
    try:
        access_token = await get_ebay_access_token()
        environment = await get_ebay_environment()
        config = get_ebay_config(environment)
        api_url = config["api_url"]
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Content-Language": "en-US"
        }
        
        results = {}
        
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            for mp_id, mp_data in marketplace_listings.items():
                mp_sku = mp_data.get("sku")
                mp_offer_id = mp_data.get("offer_id")
                
                logger.info(f"  Updating {mp_id}: SKU={mp_sku}, offer_id={mp_offer_id}")
                
                mp_config = MARKETPLACE_CONFIG.get(mp_id, {})
                content_lang = mp_config.get("content_language", "en-US")
                
                try:
                    # Step 1: Update inventory item with new title/description
                    inventory_payload = {
                        "product": {
                            "title": draft.get("title", ""),
                            "description": draft.get("description", ""),
                            "aspects": draft.get("aspects", {}),
                            "imageUrls": draft.get("image_urls", [])
                        },
                        "condition": draft.get("condition", "USED_EXCELLENT"),
                        "availability": {
                            "shipToLocationAvailability": {
                                "quantity": 1
                            }
                        }
                    }
                    
                    inv_headers = {**headers, "Content-Language": content_lang}
                    inv_resp = await http_client.put(
                        f"{api_url}/sell/inventory/v1/inventory_item/{mp_sku}",
                        headers=inv_headers,
                        json=inventory_payload
                    )
                    
                    if inv_resp.status_code in [200, 201, 204]:
                        logger.info(f"    ✅ Inventory updated for {mp_id}")
                        results[mp_id] = {"success": True, "message": "Updated"}
                    else:
                        error_text = inv_resp.text[:300]
                        logger.warning(f"    ⚠️ Inventory update failed for {mp_id}: {error_text}")
                        results[mp_id] = {"success": False, "error": error_text}
                        
                except Exception as e:
                    logger.error(f"    ❌ Error updating {mp_id}: {str(e)}")
                    results[mp_id] = {"success": False, "error": str(e)}
        
        # Update draft timestamp
        await db.drafts.update_one(
            {"id": draft_id},
            {"$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        successful = sum(1 for r in results.values() if r.get("success"))
        logger.info(f"✅ Republish complete: {successful}/{len(results)} marketplaces updated")
        
        return {
            "message": f"Republished to {successful}/{len(results)} marketplaces",
            "results": results
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error republishing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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


# ============ TAXONOMY API - Category Management per Marketplace ============

@api_router.get("/taxonomy/categories/{marketplace_id}")
async def get_category_suggestions(
    marketplace_id: str,
    q: str = Query(..., description="Search query for category suggestions"),
    user = Depends(get_current_user)
):
    """
    Get category suggestions for a specific marketplace using eBay Taxonomy API.
    Returns list of suggested categories with IDs and names.
    """
    # Get Application Access Token for Taxonomy API (uses client_credentials)
    try:
        access_token = await get_ebay_app_token()
    except HTTPException as e:
        raise HTTPException(status_code=400, detail=f"eBay authentication error: {e.detail}")
    
    environment = await get_ebay_environment()
    config = get_ebay_config(environment)
    
    if not access_token:
        raise HTTPException(status_code=400, detail="No eBay access token")
    
    api_url = config["api_url"]
    category_tree_id = MARKETPLACE_CATEGORY_TREE.get(marketplace_id)
    
    if not category_tree_id:
        raise HTTPException(status_code=400, detail=f"Unknown marketplace: {marketplace_id}")
    
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        taxonomy_url = f"{api_url}/commerce/taxonomy/v1/category_tree/{category_tree_id}/get_category_suggestions"
        
        try:
            resp = await http_client.get(
                taxonomy_url,
                headers=headers,
                params={"q": q}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                suggestions = []
                for item in data.get("categorySuggestions", []):
                    cat = item.get("category", {})
                    suggestions.append({
                        "categoryId": cat.get("categoryId"),
                        "categoryName": cat.get("categoryName"),
                        "categoryTreeNodeLevel": item.get("categoryTreeNodeLevel", 0)
                    })
                return {"marketplace": marketplace_id, "suggestions": suggestions}
            else:
                logger.warning(f"Taxonomy API error: {resp.status_code} - {resp.text[:300]}")
                return {"marketplace": marketplace_id, "suggestions": [], "error": f"API error: {resp.status_code}"}
        except Exception as e:
            logger.error(f"Taxonomy API exception: {e}")
            return {"marketplace": marketplace_id, "suggestions": [], "error": str(e)}


@api_router.get("/taxonomy/aspects/{marketplace_id}/{category_id}")
async def get_category_aspects(
    marketplace_id: str,
    category_id: str,
    user = Depends(get_current_user)
):
    """
    Get required and recommended item aspects for a category on a specific marketplace.
    """
    # Get Application Access Token for Taxonomy API (uses client_credentials)
    try:
        access_token = await get_ebay_app_token()
    except HTTPException as e:
        raise HTTPException(status_code=400, detail=f"eBay authentication error: {e.detail}")
    
    environment = await get_ebay_environment()
    config = get_ebay_config(environment)
    
    api_url = config["api_url"]
    category_tree_id = MARKETPLACE_CATEGORY_TREE.get(marketplace_id)
    
    if not category_tree_id:
        raise HTTPException(status_code=400, detail=f"Unknown marketplace: {marketplace_id}")
    
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        aspects_url = f"{api_url}/commerce/taxonomy/v1/category_tree/{category_tree_id}/get_item_aspects_for_category"
        
        try:
            resp = await http_client.get(
                aspects_url,
                headers=headers,
                params={"category_id": category_id}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                aspects = []
                for aspect in data.get("aspects", []):
                    aspects.append({
                        "localizedAspectName": aspect.get("localizedAspectName"),
                        "aspectConstraint": aspect.get("aspectConstraint", {}),
                        "aspectValues": [v.get("localizedValue") for v in aspect.get("aspectValues", [])[:20]]
                    })
                return {
                    "marketplace": marketplace_id,
                    "categoryId": category_id,
                    "aspects": aspects
                }
            else:
                return {"marketplace": marketplace_id, "categoryId": category_id, "aspects": [], "error": f"API error: {resp.status_code}"}
        except Exception as e:
            logger.error(f"Aspects API exception: {e}")
            return {"marketplace": marketplace_id, "categoryId": category_id, "aspects": [], "error": str(e)}


@api_router.post("/drafts/{draft_id}/auto-categories")
async def auto_suggest_categories(draft_id: str, user = Depends(get_current_user)):
    """
    Auto-suggest categories for all target marketplaces based on draft item_type and title.
    Returns suggested categoryId for each marketplace.
    """
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # Get Application Access Token for Taxonomy API
    try:
        access_token = await get_ebay_app_token()
    except HTTPException as e:
        raise HTTPException(status_code=400, detail=f"eBay authentication error: {e.detail}")
    
    environment = await get_ebay_environment()
    config = get_ebay_config(environment)
    api_url = config["api_url"]
    
    item_type = draft.get("item_type", "MISC")
    title = draft.get("title", "skateboard")
    
    # Build search query based on item type
    type_queries = {
        "WHL": "skateboard wheels",
        "TRK": "skateboard trucks",
        "DCK": "skateboard deck",
        "APP": "skateboard clothing apparel",
        "MISC": "skateboard accessories parts"
    }
    query = type_queries.get(item_type, "skateboard")
    
    # Get enabled marketplaces from settings
    settings = await db.settings.find_one({"_id": "app_settings"}, {"_id": 0})
    enabled_marketplaces = []
    if settings:
        mp_settings = settings.get("marketplaces", {})
        for mp_id, mp_data in mp_settings.items():
            if mp_data.get("fulfillment_policy_id"):  # Has policy = enabled
                enabled_marketplaces.append(mp_id)
    
    if not enabled_marketplaces:
        enabled_marketplaces = ["EBAY_US", "EBAY_DE", "EBAY_ES", "EBAY_AU"]
    
    results = {}
    
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        for marketplace_id in enabled_marketplaces:
            category_id = await get_category_suggestion_for_marketplace(
                http_client, api_url, access_token, marketplace_id, query
            )
            if category_id:
                results[marketplace_id] = category_id
            else:
                # Use fallback
                results[marketplace_id] = get_category_for_item(item_type, marketplace_id)
    
    # Save to draft
    await db.drafts.update_one(
        {"id": draft_id},
        {"$set": {"category_by_marketplace": results, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"draft_id": draft_id, "category_by_marketplace": results}




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
    
    # Get eBay environment config
    environment = await get_ebay_environment()
    config = get_ebay_config(environment)
    api_url = config["api_url"]
    marketplace_id = config["marketplace_id"]
    country_code = config["country_code"]
    currency = config["currency"]
    
    logger.info(f"Publishing to {environment.upper()}: marketplace={marketplace_id}, country={country_code}, currency={currency}")
    
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
                    f"{api_url}/sell/inventory/v1/location/{location_key}",
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
                f"{api_url}/sell/inventory/v1/inventory_item/{draft['sku']}",
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
                    f"{api_url}/sell/inventory/v1/offer",
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
                    f"{api_url}/sell/inventory/v1/offer/{offer_id}",
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
                    f"{api_url}/sell/inventory/v1/offer",
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
                f"{api_url}/sell/inventory/v1/offer/{offer_id}/publish",
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
        settings = {"ebay_environment": "sandbox"}
    
    # Get environment and check eBay connection for that environment
    environment = settings.get("ebay_environment", "sandbox")
    token_collection_id = f"ebay_tokens_{environment}"
    tokens = await db.ebay_tokens.find_one({"_id": token_collection_id})
    settings["ebay_connected"] = bool(tokens and tokens.get("access_token"))
    settings["ebay_environment"] = environment
    
    return SettingsResponse(**settings)

@api_router.patch("/settings", response_model=SettingsResponse)
async def update_settings(update: SettingsUpdate, user = Depends(get_current_user)):
    """Update app settings"""
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    
    # If environment is changing, clear policy IDs (they're environment-specific)
    if "ebay_environment" in update_data:
        old_settings = await db.settings.find_one({"_id": "app_settings"})
        old_env = old_settings.get("ebay_environment", "sandbox") if old_settings else "sandbox"
        if update_data["ebay_environment"] != old_env:
            update_data["fulfillment_policy_id"] = None
            update_data["return_policy_id"] = None
            update_data["payment_policy_id"] = None
            update_data["merchant_location_key"] = None
            logger.info(f"Environment changed from {old_env} to {update_data['ebay_environment']}, cleared policy IDs")
    
    await db.settings.update_one(
        {"_id": "app_settings"},
        {"$set": update_data},
        upsert=True
    )
    
    settings = await db.settings.find_one({"_id": "app_settings"}, {"_id": 0})
    environment = settings.get("ebay_environment", "sandbox")
    token_collection_id = f"ebay_tokens_{environment}"
    tokens = await db.ebay_tokens.find_one({"_id": token_collection_id})
    settings["ebay_connected"] = bool(tokens and tokens.get("access_token"))
    
    return SettingsResponse(**settings)


# ============ BOOTSTRAP MULTI-MARKETPLACE ============

class BootstrapResult(BaseModel):
    marketplace_id: str
    success: bool
    location_key: Optional[str] = None
    fulfillment_policy_id: Optional[str] = None
    payment_policy_id: Optional[str] = None
    return_policy_id: Optional[str] = None
    shipping_service_code: Optional[str] = None
    error: Optional[str] = None
    errors: List[str] = []


@api_router.post("/settings/ebay/bootstrap-marketplaces")
async def bootstrap_marketplaces(
    marketplaces: List[str] = None,
    force_recreate: bool = False,
    user = Depends(get_current_user)
):
    """
    Bootstrap eBay configuration for multiple marketplaces.
    For each marketplace:
    1. Creates inventory location
    2. Fetches valid shipping service codes via Metadata API
    3. Creates fulfillment policy (with dynamic shipping service)
    4. Creates payment policy
    5. Creates return policy (30 days, seller pays, domestic only)
    6. Saves all IDs to database
    
    Set force_recreate=True to create new policies even if existing ones are found.
    """
    logger.info("=" * 60)
    logger.info(f"BOOTSTRAP MULTI-MARKETPLACE STARTED (force_recreate={force_recreate})")
    logger.info("=" * 60)
    
    # Default to all supported marketplaces if none specified
    if not marketplaces:
        marketplaces = get_all_marketplaces()
    
    logger.info(f"Marketplaces to bootstrap: {marketplaces}")
    
    # Get eBay access token
    try:
        access_token = await get_ebay_access_token()
    except HTTPException as e:
        raise HTTPException(status_code=401, detail=f"eBay not connected: {e.detail}")
    
    environment = await get_ebay_environment()
    use_sandbox = environment == "sandbox"
    api_url = "https://api.sandbox.ebay.com" if use_sandbox else "https://api.ebay.com"
    
    logger.info(f"Environment: {environment}, API URL: {api_url}")
    
    results = []
    settings_update = {"marketplaces": {}}
    
    # Load existing settings
    existing_settings = await db.settings.find_one({"_id": "app_settings"}) or {}
    existing_marketplaces = existing_settings.get("marketplaces", {})
    
    async with httpx.AsyncClient(timeout=60.0) as http_client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # First, opt-in to Business Policies
        logger.info("Step 0: Opting in to Business Policies...")
        opt_in_resp = await http_client.post(
            f"{api_url}/sell/account/v1/program/opt_in",
            headers=headers,
            json={"programType": "SELLING_POLICY_MANAGEMENT"}
        )
        logger.info(f"Opt-in response: {opt_in_resp.status_code}")
        await asyncio.sleep(1)
        
        for marketplace_id in marketplaces:
            logger.info(f"\n{'='*40}")
            logger.info(f"Processing {marketplace_id}")
            logger.info(f"{'='*40}")
            
            result = BootstrapResult(marketplace_id=marketplace_id, success=False)
            mp_settings = {}
            
            # Get marketplace defaults
            mp_config = get_default_marketplace_config(marketplace_id)
            if not mp_config:
                result.error = f"Unknown marketplace: {marketplace_id}"
                results.append(result)
                continue
            
            country_code = mp_config["country_code"]
            currency = mp_config["currency"]
            site_id = mp_config["site_id"]
            
            try:
                # ========== STEP 1: Create Inventory Location ==========
                location_key = f"warehouse_{country_code.lower()}"
                logger.info(f"Step 1: Creating location '{location_key}'...")
                
                # Check if exists first
                loc_check = await http_client.get(
                    f"{api_url}/sell/inventory/v1/location/{location_key}",
                    headers=headers
                )
                
                if loc_check.status_code == 200:
                    logger.info(f"  Location '{location_key}' already exists")
                else:
                    # Create location (ship from Italy for all)
                    loc_payload = {
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
                        "name": f"Warehouse {country_code}",
                        "merchantLocationStatus": "ENABLED"
                    }
                    loc_create = await http_client.post(
                        f"{api_url}/sell/inventory/v1/location/{location_key}",
                        headers=headers,
                        json=loc_payload
                    )
                    logger.info(f"  Create location: status={loc_create.status_code}")
                    if loc_create.status_code not in [200, 201, 204, 409]:
                        logger.warning(f"  Location creation issue: {loc_create.text[:200]}")
                
                result.location_key = location_key
                mp_settings["merchant_location_key"] = location_key
                
                # ========== STEP 2: Get Shipping Services via Metadata API ==========
                logger.info(f"Step 2: Fetching shipping services for {marketplace_id}...")
                
                shipping_service_code = None
                
                # Call Metadata API getShippingServices
                meta_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-EBAY-C-MARKETPLACE-ID": marketplace_id
                }
                
                shipping_resp = await http_client.get(
                    f"{api_url}/sell/metadata/v1/marketplace/{marketplace_id}/get_shipping_services",
                    headers=meta_headers
                )
                
                if shipping_resp.status_code == 200:
                    shipping_data = shipping_resp.json()
                    services = shipping_data.get("shippingServices", [])
                    logger.info(f"  Found {len(services)} shipping services")
                    
                    # Find international shipping service that supports Italy -> target country
                    # Look for:
                    # 1. International services from Italy
                    # 2. Standard/Economy services (not Express)
                    for svc in services:
                        svc_code = svc.get("shippingServiceCode", "")
                        carrier = svc.get("shippingCarrierCode", "")
                        intl = svc.get("internationalShipping", False)
                        
                        # For sandbox, just pick first available
                        if use_sandbox:
                            shipping_service_code = svc_code
                            logger.info(f"  Selected (sandbox): {svc_code}")
                            break
                        
                        # For production, prefer international services
                        if intl and "standard" in svc_code.lower():
                            shipping_service_code = svc_code
                            logger.info(f"  Selected international: {svc_code}")
                            break
                    
                    # Fallback to first service if none matched
                    if not shipping_service_code and services:
                        shipping_service_code = services[0].get("shippingServiceCode")
                        logger.info(f"  Fallback to first: {shipping_service_code}")
                else:
                    logger.warning(f"  Metadata API failed: {shipping_resp.status_code}")
                    logger.warning(f"  Response: {shipping_resp.text[:300]}")
                
                # Use fallback if API didn't return anything
                if not shipping_service_code:
                    shipping_service_code = FALLBACK_SHIPPING_SERVICES.get(marketplace_id, "OtherInternational")
                    logger.info(f"  Using fallback: {shipping_service_code}")
                
                result.shipping_service_code = shipping_service_code
                
                # ========== STEP 3: Clone & Update Fulfillment Policy ==========
                # Strategy: Find existing policy (by name AUTO_INTL_V2 or first available),
                # clone it, update shippingOptions with new rates, and save via updateFulfillmentPolicy.
                # IMPORTANT: Keep original shipping services, only change costs!
                logger.info(f"Step 3: Clone & Update Fulfillment Policy for {marketplace_id}...")
                
                # Get shipping rates converted to marketplace currency
                shipping_rates = await get_shipping_rates_for_marketplace(marketplace_id)
                mp_currency = shipping_rates["currency"]
                
                logger.info(f"  Shipping rates for {marketplace_id} ({mp_currency}):")
                logger.info(f"    Europe: {shipping_rates['europe']['value']} {mp_currency}")
                logger.info(f"    Americas: {shipping_rates['americas']['value']} {mp_currency}")
                logger.info(f"    Rest of World: {shipping_rates['rest_of_world']['value']} {mp_currency}")
                
                # Policy name to search for - user-created with worldwide shipping
                OUR_POLICY_NAME = "WORLDWIDE_SHIPPING_10"
                template_policy_id = None
                our_policy_id = None
                
                # Step 3a: Try to get our policy by name first
                logger.info(f"  3a. Trying to get policy by name: {OUR_POLICY_NAME}")
                get_by_name_resp = await http_client.get(
                    f"{api_url}/sell/account/v1/fulfillment_policy/get_by_policy_name",
                    headers={**headers, "X-EBAY-C-MARKETPLACE-ID": marketplace_id},
                    params={"marketplace_id": marketplace_id, "name": OUR_POLICY_NAME}
                )
                logger.info(f"    get_by_policy_name: status={get_by_name_resp.status_code}")
                
                if get_by_name_resp.status_code == 200:
                    our_policy = get_by_name_resp.json()
                    our_policy_id = our_policy.get("fulfillmentPolicyId")
                    logger.info(f"    ✅ Found policy '{OUR_POLICY_NAME}': {our_policy_id}")
                else:
                    logger.warning(f"    ⚠️ Policy '{OUR_POLICY_NAME}' not found for {marketplace_id}")
                    logger.warning(f"    Will try to use an existing policy with INTERNATIONAL shipping")
                
                # Step 3b: Get all existing fulfillment policies to find a fallback
                logger.info(f"  3b. Getting all fulfillment policies for {marketplace_id}...")
                existing_resp = await http_client.get(
                    f"{api_url}/sell/account/v1/fulfillment_policy",
                    headers={**headers, "X-EBAY-C-MARKETPLACE-ID": marketplace_id},
                    params={"marketplace_id": marketplace_id}
                )
                logger.info(f"    getFulfillmentPolicies: status={existing_resp.status_code}")
                
                if existing_resp.status_code != 200:
                    error_text = existing_resp.text[:500]
                    logger.error(f"    Failed to get fulfillment policies: {error_text}")
                    result.errors.append(f"Failed to get fulfillment policies: {existing_resp.status_code} - {error_text}")
                    continue
                
                existing_policies = existing_resp.json().get("fulfillmentPolicies", [])
                logger.info(f"    Found {len(existing_policies)} existing fulfillment policies")
                
                # If we found WORLDWIDE_SHIPPING_10, use it directly WITHOUT modifying rates
                skip_rate_update = False
                if our_policy_id:
                    template_policy_id = our_policy_id
                    logger.info(f"    ✅ Using policy '{OUR_POLICY_NAME}' (ID: {our_policy_id})")
                    # Don't update rates for user's custom policy - use as-is
                    result.fulfillment_policy_id = our_policy_id
                    skip_rate_update = True
                    logger.info(f"    Policy '{OUR_POLICY_NAME}' will be used as-is (rates configured by user)")
                else:
                    # Fallback: look for any policy with INTERNATIONAL shipping
                    intl_policy = None
                    for p in existing_policies:
                        p_name = p.get("name", "Unknown")
                        p_id = p.get("fulfillmentPolicyId", "?")
                        shipping_opts = p.get("shippingOptions", [])
                        has_intl = any(opt.get("optionType") == "INTERNATIONAL" for opt in shipping_opts)
                        intl_marker = " [HAS INTL]" if has_intl else ""
                        logger.info(f"      Policy: {p_name} (ID: {p_id}){intl_marker}")
                        if has_intl and not intl_policy:
                            intl_policy = p
                    
                    if intl_policy:
                        template_policy_id = intl_policy.get("fulfillmentPolicyId")
                        logger.warning(f"    ⚠️ Using fallback policy: {intl_policy.get('name')} (ID: {template_policy_id})")
                        result.errors.append(f"⚠️ {marketplace_id}: Using fallback policy '{intl_policy.get('name')}'. Create '{OUR_POLICY_NAME}' for better control.")
                    elif existing_policies:
                        template_policy_id = existing_policies[0].get("fulfillmentPolicyId")
                        logger.warning(f"    ⚠️ No INTL policy found, using first: {existing_policies[0].get('name')}")
                        result.errors.append(f"⚠️ {marketplace_id}: No international policy found. Create '{OUR_POLICY_NAME}' with worldwide shipping.")
                    else:
                        logger.error(f"    ❌ No policies found for {marketplace_id}")
                        result.errors.append(f"No fulfillment policy exists for {marketplace_id}. Create '{OUR_POLICY_NAME}' in eBay Seller Hub.")
                        continue
                
                # Skip rate update for user's custom WORLDWIDE_SHIPPING_10 policy
                if skip_rate_update:
                    logger.info(f"    Skipping rate update - using policy as configured by user")
                else:
                    # Step 3c: Get FULL policy object (required for update)
                    logger.info(f"  3c. Getting full policy object: {template_policy_id}")
                    full_policy_resp = await http_client.get(
                        f"{api_url}/sell/account/v1/fulfillment_policy/{template_policy_id}",
                        headers={**headers, "X-EBAY-C-MARKETPLACE-ID": marketplace_id}
                    )
                    logger.info(f"    getFulfillmentPolicy: status={full_policy_resp.status_code}")
                    
                    if full_policy_resp.status_code != 200:
                        error_text = full_policy_resp.text[:500]
                        logger.error(f"    Failed to get full policy: {error_text}")
                        result.errors.append(f"Failed to get full policy {template_policy_id}: {error_text}")
                        continue
                    
                    full_policy = full_policy_resp.json()
                    logger.info(f"    Full policy loaded: {full_policy.get('name')}")
                    
                    # Log the full policy structure for debugging
                    shipping_opts_debug = full_policy.get("shippingOptions", [])
                    logger.info(f"    Policy has {len(shipping_opts_debug)} shippingOptions:")
                    for i, opt in enumerate(shipping_opts_debug):
                        opt_type = opt.get("optionType", "?")
                        services = opt.get("shippingServices", [])
                        ship_to = opt.get("shipToLocations", {})
                        region_included = ship_to.get("regionIncluded", [])
                        region_excluded = ship_to.get("regionExcluded", [])
                        logger.info(f"      [{i}] {opt_type}: {len(services)} services")
                        logger.info(f"          shipToLocations.regionIncluded: {[r.get('regionName', r) for r in region_included]}")
                        if region_excluded:
                            logger.info(f"          shipToLocations.regionExcluded: {[r.get('regionName', r) for r in region_excluded]}")
                        for svc in services:
                            svc_code = svc.get("shippingServiceCode", "?")
                            cost = svc.get("shippingCost", {})
                            logger.info(f"          - {svc_code}: {cost.get('value', '?')} {cost.get('currency', '?')}")
                    
                    # Step 3d: Clone and modify the policy
                    logger.info(f"  3d. Modifying policy with new shipping rates...")
                    
                    # Clone the policy object for modification
                    updated_policy = dict(full_policy)
                    
                    # Don't rename the user's policy - keep original name
                    # We just update the shipping costs
                    
                    # Get the shippingOptions and update costs based on destination regions
                    # Target rates: €10 Europe, $25 Americas, $45 Rest of World (converted to marketplace currency)
                    shipping_options = updated_policy.get("shippingOptions", [])
                    
                    if shipping_options:
                        for opt in shipping_options:
                            opt_type = opt.get("optionType", "UNKNOWN")
                            services = opt.get("shippingServices", [])
                            ship_to = opt.get("shipToLocations", {})
                            region_included = ship_to.get("regionIncluded", [])
                            
                            # Determine which rate to use based on option type and destination
                            # DOMESTIC = seller's home region (use Europe rate €10)
                            # INTERNATIONAL = check shipToLocations to determine rate
                            if opt_type == "DOMESTIC":
                                # Domestic shipping - use Europe rate (€10 converted)
                                new_cost = shipping_rates['europe']['value']
                                rate_name = "Europe (domestic)"
                            elif opt_type == "INTERNATIONAL":
                                # Check what regions are included
                                region_names = [r.get("regionName", "") for r in region_included]
                                region_str = ", ".join(region_names) if region_names else "Worldwide"
                                
                                # If Americas (North/South America), use Americas rate ($25)
                                # If Europe, use Europe rate (€10)
                                # Otherwise, use Rest of World rate ($45)
                                is_americas = any(r in ["North_America", "South_America", "Americas", "NORTH_AMERICA", "SOUTH_AMERICA"] for r in region_names)
                                is_europe = any(r in ["Europe", "EUROPE", "European_Union"] for r in region_names)
                                
                                if is_americas:
                                    new_cost = shipping_rates['americas']['value']
                                    rate_name = f"Americas ({region_str})"
                                elif is_europe:
                                    new_cost = shipping_rates['europe']['value']
                                    rate_name = f"Europe ({region_str})"
                                else:
                                    # Rest of World or Worldwide
                                    new_cost = shipping_rates['rest_of_world']['value']
                                    rate_name = f"Rest of World ({region_str})"
                            else:
                                new_cost = shipping_rates['rest_of_world']['value']
                                rate_name = "Unknown type"
                            
                            logger.info(f"      {opt_type} -> {rate_name}: {len(services)} service(s) to {new_cost} {mp_currency}")
                            
                            # Update cost for each service, keeping the original service codes!
                            for svc in services:
                                original_code = svc.get("shippingServiceCode", "?")
                                svc["shippingCost"] = {
                                    "value": str(new_cost),
                                    "currency": mp_currency
                                }
                                # Also update additionalShippingCost if present
                                if "additionalShippingCost" in svc:
                                    svc["additionalShippingCost"] = {
                                        "value": "0.00",
                                        "currency": mp_currency
                                    }
                                logger.info(f"        Service: {original_code} -> {new_cost} {mp_currency}")
                        
                        updated_policy["shippingOptions"] = shipping_options
                    else:
                        logger.warning(f"    ⚠️ No shippingOptions in template policy!")
                    
                    # Remove read-only fields that can't be sent in update
                    fields_to_remove = ["fulfillmentPolicyId", "warnings", "errors"]
                    for field in fields_to_remove:
                        updated_policy.pop(field, None)
                    
                    # Step 3e: Update the fallback policy with new rates
                    logger.info(f"  3e. Updating fallback policy with new shipping rates: {template_policy_id}")
                    
                    # Keep original name for the update (don't try to rename)
                    updated_policy["name"] = full_policy.get("name")
                    updated_policy.pop("description", None)  # Keep original description
                    
                    update_resp = await http_client.put(
                        f"{api_url}/sell/account/v1/fulfillment_policy/{template_policy_id}",
                        headers={**headers, "X-EBAY-C-MARKETPLACE-ID": marketplace_id, "Content-Type": "application/json"},
                        json=updated_policy
                    )
                    logger.info(f"    updateFulfillmentPolicy: status={update_resp.status_code}")
                    
                    if update_resp.status_code == 200:
                        result.fulfillment_policy_id = template_policy_id
                        logger.info(f"    ✅ Policy updated with new rates: {template_policy_id}")
                    else:
                        error_data = {}
                        try:
                            error_data = update_resp.json()
                        except:
                            error_data = {"message": update_resp.text[:500]}
                        logger.error(f"    ❌ Failed to update policy: {json.dumps(error_data, indent=2)}")
                        # Show detailed errors
                        errors_list = error_data.get("errors", [])
                        for err in errors_list:
                            err_msg = f"{err.get('errorId', '?')}: {err.get('longMessage', err.get('message', 'Unknown error'))}"
                            logger.error(f"      Error: {err_msg}")
                            result.errors.append(err_msg)
                        if not errors_list:
                            result.errors.append(f"Update failed: {update_resp.status_code} - {error_data}")
                        # Use the fallback policy anyway (it still exists and is valid)
                        result.fulfillment_policy_id = template_policy_id
                        logger.info(f"    Using existing policy without rate update: {template_policy_id}")
                
                # ========== STEP 4: Create Payment Policy ==========
                logger.info(f"Step 4: Creating payment policy for {marketplace_id}...")
                
                payment_payload = {
                    "name": f"PayPal Payment {country_code} - {environment}",
                    "description": f"PayPal payment for {mp_config['name']}",
                    "marketplaceId": marketplace_id,
                    "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                    "paymentMethods": [
                        {
                            "paymentMethodType": "PERSONAL_CHECK",
                            "brands": []
                        }
                    ],
                    "immediatePay": False
                }
                
                # For production, use PAYPAL
                if not use_sandbox:
                    payment_payload["paymentMethods"] = [
                        {"paymentMethodType": "PAYPAL"}
                    ]
                
                # First try to get existing payment policies
                existing_resp = await http_client.get(
                    f"{api_url}/sell/account/v1/payment_policy",
                    headers={**headers, "X-EBAY-C-MARKETPLACE-ID": marketplace_id},
                    params={"marketplace_id": marketplace_id}
                )
                
                if existing_resp.status_code == 200:
                    existing_policies = existing_resp.json().get("paymentPolicies", [])
                    if existing_policies:
                        result.payment_policy_id = existing_policies[0].get("paymentPolicyId")
                        logger.info(f"  Using existing payment: {result.payment_policy_id}")
                
                # Create new if none exists
                if not result.payment_policy_id:
                    payment_resp = await http_client.post(
                        f"{api_url}/sell/account/v1/payment_policy",
                        headers={**headers, "X-EBAY-C-MARKETPLACE-ID": marketplace_id},
                        json=payment_payload
                    )
                    logger.info(f"  Create payment: status={payment_resp.status_code}")
                    logger.info(f"  Response: {payment_resp.text[:300]}")
                    
                    if payment_resp.status_code == 201:
                        payment_data = payment_resp.json()
                        result.payment_policy_id = payment_data.get("paymentPolicyId")
                        logger.info(f"  Payment ID: {result.payment_policy_id}")
                    elif payment_resp.status_code == 400:
                        logger.warning(f"  Payment creation failed: {payment_resp.text[:300]}")
                    else:
                        logger.error(f"  Payment error: {payment_resp.text[:300]}")
                
                # ========== STEP 5: Create Return Policy ==========
                # 30 days, seller pays return shipping, domestic only
                logger.info(f"Step 5: Creating return policy for {marketplace_id}...")
                
                return_payload = {
                    "name": f"30 Day Returns {country_code} - {environment} - {secrets.token_hex(4)}",
                    "description": f"30 day returns, seller pays shipping, domestic only",
                    "marketplaceId": marketplace_id,
                    "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                    "returnsAccepted": True,
                    "returnPeriod": {
                        "value": 30,
                        "unit": "DAY"
                    },
                    "returnShippingCostPayer": "SELLER",
                    "internationalOverride": {
                        "returnsAccepted": False
                    }
                }
                
                # First try to get existing return policies
                existing_resp = await http_client.get(
                    f"{api_url}/sell/account/v1/return_policy",
                    headers={**headers, "X-EBAY-C-MARKETPLACE-ID": marketplace_id},
                    params={"marketplace_id": marketplace_id}
                )
                
                if existing_resp.status_code == 200:
                    existing_policies = existing_resp.json().get("returnPolicies", [])
                    if existing_policies:
                        result.return_policy_id = existing_policies[0].get("returnPolicyId")
                        logger.info(f"  Using existing return: {result.return_policy_id}")
                
                # Create new if none exists
                if not result.return_policy_id:
                    return_resp = await http_client.post(
                        f"{api_url}/sell/account/v1/return_policy",
                        headers={**headers, "X-EBAY-C-MARKETPLACE-ID": marketplace_id},
                        json=return_payload
                    )
                    logger.info(f"  Create return: status={return_resp.status_code}")
                    logger.info(f"  Response: {return_resp.text[:300]}")
                    
                    if return_resp.status_code == 201:
                        return_data = return_resp.json()
                        result.return_policy_id = return_data.get("returnPolicyId")
                        logger.info(f"  Return ID: {result.return_policy_id}")
                    elif return_resp.status_code == 400:
                        logger.warning(f"  Return creation failed: {return_resp.text[:300]}")
                    else:
                        logger.error(f"  Return error: {return_resp.text[:300]}")
                
                # ========== STEP 6: Save to settings ==========
                mp_settings["policies"] = {
                    "fulfillment_policy_id": result.fulfillment_policy_id,
                    "payment_policy_id": result.payment_policy_id,
                    "return_policy_id": result.return_policy_id
                }
                mp_settings["shipping_service_code"] = shipping_service_code
                
                # Check if all required fields are present
                if all([result.location_key, result.fulfillment_policy_id, result.payment_policy_id, result.return_policy_id]):
                    result.success = True
                    logger.info(f"SUCCESS: {marketplace_id} fully configured!")
                else:
                    missing = []
                    if not result.location_key:
                        missing.append("location")
                    if not result.fulfillment_policy_id:
                        missing.append("fulfillment_policy")
                    if not result.payment_policy_id:
                        missing.append("payment_policy")
                    if not result.return_policy_id:
                        missing.append("return_policy")
                    result.error = f"Missing: {', '.join(missing)}"
                    logger.warning(f"PARTIAL: {marketplace_id} - {result.error}")
                
                settings_update["marketplaces"][marketplace_id] = mp_settings
                
            except Exception as e:
                logger.error(f"Error processing {marketplace_id}: {str(e)}")
                result.error = str(e)
            
            results.append(result)
    
    # Save all settings to database
    logger.info("\nSaving settings to database...")
    
    # Merge with existing marketplaces settings
    merged_marketplaces = {**existing_marketplaces, **settings_update["marketplaces"]}
    
    await db.settings.update_one(
        {"_id": "app_settings"},
        {"$set": {"marketplaces": merged_marketplaces}},
        upsert=True
    )
    
    # Calculate summary
    success_count = sum(1 for r in results if r.success)
    partial_count = sum(1 for r in results if not r.success and r.location_key)
    failed_count = sum(1 for r in results if not r.success and not r.location_key)
    
    logger.info("=" * 60)
    logger.info(f"BOOTSTRAP COMPLETE: {success_count} success, {partial_count} partial, {failed_count} failed")
    logger.info("=" * 60)
    
    return {
        "message": f"Bootstrap complete: {success_count}/{len(results)} marketplaces configured",
        "results": [r.model_dump() for r in results],
        "summary": {
            "total": len(results),
            "success": success_count,
            "partial": partial_count,
            "failed": failed_count
        }
    }


@api_router.get("/marketplaces")
async def get_marketplaces(user = Depends(get_current_user)):
    """
    Get list of supported marketplaces with their current configuration status.
    Shows which marketplaces have policies configured.
    """
    # Get saved settings
    settings = await db.settings.find_one({"_id": "app_settings"}) or {}
    saved_marketplaces = settings.get("marketplaces", {})
    
    # Get all supported marketplaces
    all_mp_ids = get_all_marketplaces()
    
    result = []
    for mp_id in all_mp_ids:
        mp_config = get_marketplace_config(mp_id, settings)
        if not mp_config:
            continue
        
        # Check if fully configured
        saved = saved_marketplaces.get(mp_id, {})
        policies = saved.get("policies", {})
        
        is_configured = all([
            saved.get("merchant_location_key"),
            policies.get("fulfillment_policy_id"),
            policies.get("payment_policy_id"),
            policies.get("return_policy_id")
        ])
        
        result.append({
            "id": mp_id,
            "name": mp_config["name"],
            "currency": mp_config["currency"],
            "country_code": mp_config["country_code"],
            "is_configured": is_configured,
            "merchant_location_key": saved.get("merchant_location_key"),
            "policies": policies,
            "default_price": mp_config["price"]["value"],
            "default_shipping": mp_config["shipping_standard"]["cost"]["value"]
        })
    
    return {"marketplaces": result}


@api_router.get("/ebay/policies")
async def get_ebay_policies(user = Depends(get_current_user)):
    """Fetch business policies from eBay, create defaults if none exist"""
    try:
        access_token = await get_ebay_access_token()
        environment = await get_ebay_environment()
        config = get_ebay_config(environment)
        marketplace_id = config["marketplace_id"]
        api_url = config["api_url"]
        
        logger.info("=" * 60)
        logger.info(f"FETCHING EBAY POLICIES ({environment.upper()}) for marketplace: {marketplace_id}")
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Content-Language": "en-US" if environment == "sandbox" else "it-IT"
            }
            
            # 0. First, opt-in to Business Policies (SELLING_POLICY_MANAGEMENT)
            logger.info("Step 0: Opting in to Business Policies...")
            opt_in_resp = await http_client.post(
                f"{api_url}/sell/account/v1/program/opt_in",
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
                f"{api_url}/sell/account/v1/fulfillment_policy",
                headers=headers,
                params={"marketplace_id": marketplace_id}
            )
            logger.info(f"GET fulfillment_policy: status={fulfillment_resp.status_code}")
            logger.info(f"  Response body: {fulfillment_resp.text[:500]}")
            
            # 2. Fetch Payment Policies
            payment_resp = await http_client.get(
                f"{api_url}/sell/account/v1/payment_policy",
                headers=headers,
                params={"marketplace_id": marketplace_id}
            )
            logger.info(f"GET payment_policy: status={payment_resp.status_code}")
            logger.info(f"  Response body: {payment_resp.text[:500]}")
            
            # 3. Fetch Return Policies
            return_resp = await http_client.get(
                f"{api_url}/sell/account/v1/return_policy",
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
                    f"{api_url}/sell/account/v1/fulfillment_policy",
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
                    f"{api_url}/sell/account/v1/payment_policy",
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
                    f"{api_url}/sell/account/v1/return_policy",
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
        environment = await get_ebay_environment()
        config = get_ebay_config(environment)
        api_url = config["api_url"]
        location_key = "default_location"
        
        logger.info(f"Creating merchant location ({environment})...")
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # First check if location exists
            check_resp = await http_client.get(
                f"{api_url}/sell/inventory/v1/location/{location_key}",
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
                return {"message": "Location already exists", "location_key": location_key, "environment": environment}
            
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
                f"{api_url}/sell/inventory/v1/location/{location_key}",
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
                return {"message": "Location created", "location_key": location_key, "environment": environment}
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


# ============ MULTI-MARKETPLACE PUBLISH ============

class MultiMarketplacePublishRequest(BaseModel):
    marketplaces: List[str] = ["EBAY_US"]  # List of marketplace IDs to publish to
    custom_prices: Optional[Dict[str, float]] = None  # Override prices per marketplace

@api_router.post("/drafts/{draft_id}/publish-multi")
async def publish_draft_multi_marketplace(
    draft_id: str, 
    request: MultiMarketplacePublishRequest,
    user = Depends(get_current_user)
):
    """Publish draft to multiple eBay marketplaces"""
    logger.info("=" * 60)
    logger.info(f"MULTI-MARKETPLACE PUBLISH: {draft_id}")
    logger.info(f"Marketplaces: {request.marketplaces}")
    logger.info("=" * 60)
    
    draft = await db.drafts.find_one({"id": draft_id}, {"_id": 0})
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # Basic validation
    errors = []
    if not draft.get("title"):
        errors.append("Title is required")
    if not draft.get("image_urls") or len(draft["image_urls"]) == 0:
        errors.append("At least one image is required")
    
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    
    # Get environment and settings
    environment = await get_ebay_environment()
    use_sandbox = environment == "sandbox"
    settings = await db.settings.find_one({"_id": "app_settings"}, {"_id": 0}) or {}
    
    # Validate marketplace configurations BEFORE proceeding
    missing_configs = []
    for marketplace_id in request.marketplaces:
        mp_config = get_marketplace_config(marketplace_id, settings)
        if not mp_config:
            missing_configs.append(f"Unknown marketplace: {marketplace_id}")
            continue
        
        validation_errors = validate_marketplace_config(marketplace_id, mp_config)
        if validation_errors:
            missing_configs.extend(validation_errors)
    
    if missing_configs:
        raise HTTPException(
            status_code=400, 
            detail={
                "errors": missing_configs,
                "message": "Missing policy/location configuration. Go to Settings and configure policies for each marketplace."
            }
        )
    
    try:
        access_token = await get_ebay_access_token()
    except HTTPException as e:
        raise HTTPException(status_code=401, detail=f"eBay not connected: {e.detail}")
    
    # Get base API URL based on environment
    if use_sandbox:
        api_url = "https://api.sandbox.ebay.com"
    else:
        api_url = "https://api.ebay.com"
    
    # Convert image URLs to absolute
    image_urls = []
    for url in draft.get("image_urls", []):
        if url.startswith("/api/"):
            image_urls.append(f"{FRONTEND_URL}{url}")
        elif url.startswith("http"):
            image_urls.append(url)
        else:
            image_urls.append(f"{FRONTEND_URL}/api/uploads/{url}")
    
    # Build aspects - ensure required fields are always present
    aspects = {}
    for k, v in (draft.get("aspects") or {}).items():
        if v and str(v).strip():
            aspects[k] = [str(v)]
    
    # Ensure Brand is present (required by most eBay categories)
    if "Brand" not in aspects:
        brand_value = draft.get("brand") or "Unbranded"
        aspects["Brand"] = [brand_value]
        logger.info(f"Added missing Brand aspect: {brand_value}")
    
    # Ensure MPN is present (required by some marketplaces like AU)
    if "MPN" not in aspects:
        mpn_value = draft.get("mpn") or "Does not apply"
        aspects["MPN"] = [mpn_value]
        logger.info(f"Added missing MPN aspect: {mpn_value}")
    
    # Ensure UPC is present (required by AU marketplace)
    if "UPC" not in aspects:
        upc_value = draft.get("upc") or "Does not apply"
        aspects["UPC"] = [upc_value]
        logger.info(f"Added missing UPC aspect: {upc_value}")
    
    # Ensure EAN is present (required by ES marketplace)
    if "EAN" not in aspects:
        ean_value = draft.get("ean") or "Does not apply"
        aspects["EAN"] = [ean_value]
        logger.info(f"Added missing EAN aspect: {ean_value}")
    
    # Ensure Type is present for skateboard items
    if "Type" not in aspects:
        item_type = draft.get("item_type", "MISC")
        type_mapping = {
            "WHL": "Skateboard Wheels",
            "TRK": "Skateboard Trucks", 
            "DCK": "Skateboard Deck",
            "APP": "Skateboard Apparel",
            "MISC": "Skateboard Accessory"
        }
        aspects["Type"] = [type_mapping.get(item_type, "Skateboard Accessory")]
    
    logger.info(f"Final aspects: {aspects}")
    
    sku = draft["sku"]
    results = {"sku": sku, "marketplaces": {}}
    
    async with httpx.AsyncClient(timeout=60.0) as http_client:
        # Base headers - Content-Language will be set per marketplace
        base_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Step 1: Create/Update Inventory Item for EACH marketplace with UNIQUE SKU
        # eBay requires separate inventory items per marketplace
        # Using unique SKU per marketplace: {base_sku}-{marketplace_suffix}
        logger.info(f"Step 1: Creating inventory items for base SKU {sku} on EACH marketplace")
        
        marketplace_skus = {}  # Map marketplace -> unique SKU
        
        # Aspect name localization mapping
        ASPECT_LOCALIZATION = {
            "EBAY_DE": {"Brand": "Marke", "Type": "Typ"},
            "EBAY_ES": {"Brand": "Marca", "Type": "Tipo"},
        }
        
        def localize_aspects(base_aspects: dict, marketplace_id: str) -> dict:
            """Localize aspect names for a specific marketplace"""
            localization = ASPECT_LOCALIZATION.get(marketplace_id, {})
            localized = {}
            for key, value in base_aspects.items():
                localized_key = localization.get(key, key)
                localized[localized_key] = value
            return localized
        
        for marketplace_id in request.marketplaces:
            mp_config_for_inv = get_marketplace_config(marketplace_id, settings)
            mp_language = mp_config_for_inv.get("language", "en-US") if mp_config_for_inv else "en-US"
            
            # Create unique SKU for this marketplace
            mp_suffix = marketplace_id.replace("EBAY_", "").lower()
            unique_sku = f"{sku}-{mp_suffix}"
            marketplace_skus[marketplace_id] = unique_sku
            
            # Localize aspects for this marketplace
            localized_aspects = localize_aspects(aspects, marketplace_id)
            logger.info(f"  SKU for {marketplace_id}: {unique_sku}")
            logger.info(f"  Aspects: {localized_aspects}")
            
            # Build product payload with UPC/EAN as product identifiers
            product_payload = {
                "title": draft["title"],
                "description": draft.get("description", ""),
                "aspects": localized_aspects,
                "imageUrls": image_urls
            }
            
            # Add product identifiers (ALWAYS include them - eBay requires presence even if "Does not apply")
            upc_value = draft.get("upc") or aspects.get("UPC", ["Does not apply"])[0]
            ean_value = draft.get("ean") or aspects.get("EAN", ["Does not apply"])[0]
            
            # Add as arrays (eBay API format)
            product_payload["upc"] = [upc_value]
            product_payload["ean"] = [ean_value]
            
            logger.info(f"  Product identifiers: UPC={upc_value}, EAN={ean_value}")
            
            inventory_payload = {
                "product": product_payload,
                "condition": draft.get("condition", "USED_GOOD"),
                "availability": {
                    "shipToLocationAvailability": {
                        "quantity": 1
                    }
                }
            }
            
            inv_headers = {
                **base_headers,
                "X-EBAY-C-MARKETPLACE-ID": marketplace_id,
                "Content-Language": mp_language
            }
            
            logger.info(f"  Creating inventory item for {marketplace_id} (SKU: {unique_sku}, Content-Language: {mp_language})...")
            inv_response = await http_client.put(
                f"{api_url}/sell/inventory/v1/inventory_item/{unique_sku}",
                headers=inv_headers,
                json=inventory_payload
            )
            
            logger.info(f"  createOrReplaceInventoryItem ({marketplace_id}): status={inv_response.status_code}")
            if inv_response.status_code not in [200, 204]:
                logger.warning(f"  Inventory creation for {marketplace_id} failed: {inv_response.text[:300]}")
        
        logger.info(f"Inventory item {sku} created/updated for all marketplaces")
        
        # Default headers for location API (en-US is fine for locations)
        location_headers = {
            **base_headers,
            "Content-Language": "en-US"
        }
        
        # Step 2: Create locations for each marketplace if needed
        created_locations = set()
        for marketplace_id in request.marketplaces:
            mp_config = get_marketplace_config(marketplace_id, settings)
            location_key = mp_config.get("merchant_location_key", f"location_{mp_config['country_code'].lower()}")
            
            if location_key in created_locations:
                continue
            
            logger.info(f"Step 2: Checking/creating merchant location: {location_key} for {marketplace_id}")
            
            loc_check = await http_client.get(
                f"{api_url}/sell/inventory/v1/location/{location_key}",
                headers=location_headers
            )
            
            if loc_check.status_code != 200:
                logger.info(f"Creating merchant location {location_key}...")
                loc_payload = {
                    "location": {
                        "address": {
                            "addressLine1": "Via Roma 1",
                            "city": "Milan",
                            "stateOrProvince": "MI",
                            "postalCode": "20100",
                            "country": "IT"  # Ship from Italy for all
                        }
                    },
                    "locationTypes": ["WAREHOUSE"],
                    "name": f"Warehouse {mp_config['country_code']}",
                    "merchantLocationStatus": "ENABLED"
                }
                loc_create = await http_client.post(
                    f"{api_url}/sell/inventory/v1/location/{location_key}",
                    headers=location_headers,
                    json=loc_payload
                )
                logger.info(f"Create location {location_key}: status={loc_create.status_code}")
            
            created_locations.add(location_key)
        
        # Step 3: Create/Update and Publish offer for each marketplace
        for marketplace_id in request.marketplaces:
            logger.info(f"\n--- Processing {marketplace_id} ---")
            
            # Get marketplace config with DB settings merged
            mp_config = get_marketplace_config(marketplace_id, settings)
            if not mp_config:
                results["marketplaces"][marketplace_id] = {"error": "Unknown marketplace"}
                continue
            
            # Get price (custom or default from config)
            if request.custom_prices and marketplace_id in request.custom_prices:
                price = request.custom_prices[marketplace_id]
            else:
                price = draft.get("price") or mp_config.get("default_price", 25.00)
            
            currency = mp_config["currency"]
            country_code = mp_config["country_code"]
            
            # Get category - PRIORITY:
            # 1. category_by_marketplace (user-defined per marketplace)
            # 2. Taxonomy API suggestion
            # 3. Fallback to item_type mapping
            item_type = draft.get("item_type", "MISC")
            category_by_mp = draft.get("category_by_marketplace", {})
            
            category_id = category_by_mp.get(marketplace_id)
            
            if not category_id:
                # Try Taxonomy API
                title = draft.get("title", "skateboard")
                category_id = await get_valid_category_for_marketplace(
                    http_client, api_url, access_token, marketplace_id, item_type, title
                )
            
            # Validate category exists
            if not category_id:
                results["marketplaces"][marketplace_id] = {
                    "success": False,
                    "error": f"Categoria mancante per {marketplace_id}. Vai in 'Auto-Categories' per suggerire categorie automaticamente."
                }
                logger.warning(f"Missing category for {marketplace_id}, skipping")
                continue
            
            # Sanitize category_id - extract only numeric part
            import re
            match = re.match(r'^(\d+)', str(category_id))
            if match:
                category_id = match.group(1)
            else:
                results["marketplaces"][marketplace_id] = {
                    "success": False,
                    "error": f"Formato categoria non valido per {marketplace_id}: {category_id}"
                }
                continue
            
            logger.info(f"Using category {category_id} for {marketplace_id} (item_type: {item_type})")
            
            # Get policy IDs from marketplace config (nested in 'policies' dict)
            policies = mp_config.get("policies", {})
            fulfillment_policy_id = policies.get("fulfillment_policy_id")
            payment_policy_id = policies.get("payment_policy_id")
            return_policy_id = policies.get("return_policy_id")
            merchant_location_key = mp_config.get("merchant_location_key", f"location_{country_code.lower()}")
            
            # This check is redundant now (we validate upfront) but keep as safety
            if not all([fulfillment_policy_id, payment_policy_id, return_policy_id]):
                results["marketplaces"][marketplace_id] = {
                    "error": f"Missing policy IDs for {marketplace_id}. Configure in Settings."
                }
                continue
            
            logger.info(f"Using policies for {marketplace_id}: fulfillment={fulfillment_policy_id}, payment={payment_policy_id}, return={return_policy_id}")
            logger.info(f"Using location: {merchant_location_key}")
            
            # Get the unique SKU for this marketplace
            mp_sku = marketplace_skus[marketplace_id]
            
            # Build offer payload with marketplace-specific policies
            offer_payload = {
                "sku": mp_sku,
                "marketplaceId": marketplace_id,
                "format": "FIXED_PRICE",
                "pricingSummary": {
                    "price": {
                        "value": str(price),
                        "currency": currency
                    }
                },
                "availableQuantity": 1,
                "categoryId": category_id,
                "countryCode": country_code,
                "merchantLocationKey": merchant_location_key,
                "listingPolicies": {
                    "fulfillmentPolicyId": fulfillment_policy_id,
                    "paymentPolicyId": payment_policy_id,
                    "returnPolicyId": return_policy_id
                },
                "listingDescription": draft.get("description", "")
            }
            
            # === CLEAR LOGGING: OFFER PAYLOAD ===
            logger.info("=" * 60)
            logger.info(f"📦 OFFER PAYLOAD FOR {marketplace_id}")
            logger.info("=" * 60)
            logger.info(json.dumps({
                "sku": offer_payload["sku"],
                "marketplaceId": offer_payload["marketplaceId"],
                "format": offer_payload["format"],
                "price": offer_payload["pricingSummary"]["price"],
                "categoryId": offer_payload["categoryId"],
                "countryCode": offer_payload["countryCode"],
                "merchantLocationKey": offer_payload["merchantLocationKey"],
                "listingPolicies": offer_payload["listingPolicies"]
            }, indent=2))
            logger.info("=" * 60)
            
            # Get the correct Content-Language for this marketplace
            mp_language = mp_config.get("language", "en-US")
            
            # Get the unique SKU for this marketplace
            mp_sku = marketplace_skus[marketplace_id]
            
            # Headers with marketplace ID and correct language for all offer-related calls
            mp_offer_headers = {
                **base_headers,
                "X-EBAY-C-MARKETPLACE-ID": marketplace_id,
                "Content-Language": mp_language
            }
            
            logger.info(f"Using Content-Language: {mp_language} for {marketplace_id}")
            logger.info(f"Using SKU: {mp_sku} for {marketplace_id}")
            
            # Check if offer already exists for this SKU+marketplace
            existing_offer_id = None
            get_offers_resp = await http_client.get(
                f"{api_url}/sell/inventory/v1/offer",
                headers=mp_offer_headers,
                params={"sku": mp_sku, "marketplace_id": marketplace_id}
            )
            
            if get_offers_resp.status_code == 200:
                offers_data = get_offers_resp.json()
                for offer in offers_data.get("offers", []):
                    if offer.get("marketplaceId") == marketplace_id:
                        existing_offer_id = offer.get("offerId")
                        # Check if this offer is already published (has listingId)
                        existing_listing_id = offer.get("listing", {}).get("listingId")
                        if existing_listing_id:
                            # Already published! Skip and return existing result
                            logger.info(f"⏭️ SKIPPING {marketplace_id} - Already published with listing ID: {existing_listing_id}")
                            mp_domain = get_marketplace_domain(marketplace_id)
                            sandbox_prefix = "sandbox." if use_sandbox else ""
                            results["marketplaces"][marketplace_id] = {
                                "success": True,
                                "offer_id": existing_offer_id,
                                "listing_id": existing_listing_id,
                                "price": f"{price} {currency}",
                                "listing_url": f"https://www.{sandbox_prefix}{mp_domain}/itm/{existing_listing_id}",
                                "note": "Already published (skipped)"
                            }
                            break
                        else:
                            logger.info(f"Found existing unpublished offer: {existing_offer_id}")
                        break
            
            # Skip to next marketplace if already published
            if results["marketplaces"].get(marketplace_id, {}).get("success"):
                continue
            
            # Also check draft's multi_marketplace_results for existing listing
            existing_results = draft.get("multi_marketplace_results", {})
            if existing_results.get(marketplace_id, {}).get("listing_id"):
                existing_listing_id = existing_results[marketplace_id]["listing_id"]
                logger.info(f"⏭️ SKIPPING {marketplace_id} - Found existing listing in draft: {existing_listing_id}")
                mp_domain = get_marketplace_domain(marketplace_id)
                sandbox_prefix = "sandbox." if use_sandbox else ""
                results["marketplaces"][marketplace_id] = {
                    "success": True,
                    "offer_id": existing_results[marketplace_id].get("offer_id"),
                    "listing_id": existing_listing_id,
                    "price": f"{price} {currency}",
                    "listing_url": f"https://www.{sandbox_prefix}{mp_domain}/itm/{existing_listing_id}",
                    "note": "Already published (from draft history)"
                }
                continue
            
            offer_id = None
            
            # Create or Update offer
            if existing_offer_id:
                # Delete existing unpublished offer to ensure clean state
                logger.info(f"Deleting existing unpublished offer {existing_offer_id}...")
                delete_resp = await http_client.delete(
                    f"{api_url}/sell/inventory/v1/offer/{existing_offer_id}",
                    headers=mp_offer_headers
                )
                logger.info(f"Delete offer response: {delete_resp.status_code}")
                if delete_resp.status_code in [200, 204]:
                    logger.info("Offer deleted successfully, will create new")
                    existing_offer_id = None  # Force create new offer
                else:
                    # Delete failed, try update with FULL payload
                    logger.info(f"Delete failed ({delete_resp.status_code}), trying full update...")
                    # updateOffer is "replace" - must include ALL required fields
                    offer_response = await http_client.put(
                        f"{api_url}/sell/inventory/v1/offer/{existing_offer_id}",
                        headers=mp_offer_headers,
                        json=offer_payload
                    )
                    logger.info(f"updateOffer: status={offer_response.status_code}")
                    if offer_response.status_code in [200, 204]:
                        offer_id = existing_offer_id
                    else:
                        logger.warning(f"updateOffer failed: {offer_response.text[:200]}")
            
            if not offer_id and not existing_offer_id:
                # Create new offer
                offer_response = await http_client.post(
                    f"{api_url}/sell/inventory/v1/offer",
                    headers=mp_offer_headers,
                    json=offer_payload
                )
                logger.info(f"createOffer ({marketplace_id}): status={offer_response.status_code}")
                
                if offer_response.status_code == 201:
                    offer_data = offer_response.json()
                    offer_id = offer_data.get("offerId")
                elif offer_response.status_code == 400:
                    # Check for "already exists" error
                    try:
                        err_data = offer_response.json()
                        for err in err_data.get("errors", []):
                            if "already exists" in err.get("message", "").lower():
                                for param in err.get("parameters", []):
                                    if param.get("name") == "offerId":
                                        offer_id = param.get("value")
                                        break
                    except:
                        pass
                    
                    if not offer_id:
                        results["marketplaces"][marketplace_id] = {
                            "success": False,
                            "error": f"Create offer failed: {offer_response.text[:200]}"
                        }
                        continue
                else:
                    results["marketplaces"][marketplace_id] = {
                        "success": False,
                        "error": f"Create offer failed: {offer_response.text[:200]}"
                    }
                    continue
            
            if not offer_id:
                results["marketplaces"][marketplace_id] = {
                    "success": False,
                    "error": "Failed to create or retrieve offer ID"
                }
                continue
            
            logger.info(f"Offer ID: {offer_id}")
            
            # ========== PUBLISH OFFER WITH RETRY ==========
            logger.info("=" * 60)
            logger.info(f"🚀 PUBLISHING OFFER {offer_id} to {marketplace_id}")
            logger.info("=" * 60)
            
            # Use retry with backoff for publish (429 and 5xx only)
            # Pass marketplace-specific headers
            publish_response, attempt_num = await retry_with_backoff(
                http_client=http_client,
                method="POST",
                url=f"{api_url}/sell/inventory/v1/offer/{offer_id}/publish",
                headers=mp_offer_headers,
                json_body=None,
                max_retries=3,
                base_delay=2.0,
                context=f"publishOffer {marketplace_id}"
            )
            
            # === CLEAR LOGGING: PUBLISH RESPONSE ===
            logger.info("=" * 60)
            logger.info(f"📬 PUBLISH RESPONSE FOR {marketplace_id} (attempt {attempt_num}/3)")
            logger.info(f"Status Code: {publish_response.status_code}")
            if publish_response.text:
                try:
                    response_json = publish_response.json()
                    logger.info(f"Response JSON: {json.dumps(response_json, indent=2)}")
                except:
                    logger.info(f"Response Text: {publish_response.text[:500]}")
            else:
                logger.info("Response: empty")
            logger.info("=" * 60)
            
            if publish_response.status_code in [200, 204]:
                publish_data = publish_response.json() if publish_response.text else {}
                listing_id = publish_data.get("listingId")
                
                # Get correct domain for this marketplace
                mp_domain = get_marketplace_domain(marketplace_id)
                sandbox_prefix = "sandbox." if use_sandbox else ""
                
                result_data = {
                    "success": True,
                    "offer_id": offer_id,
                    "listing_id": listing_id,
                    "price": f"{price} {currency}",
                    "listing_url": f"https://www.{sandbox_prefix}{mp_domain}/itm/{listing_id}" if listing_id else None
                }
                
                # Add retry info if there were retries
                if attempt_num > 1:
                    result_data["retries"] = attempt_num - 1
                    logger.info(f"SUCCESS after {attempt_num - 1} retry(s)! Listing ID: {listing_id}")
                else:
                    logger.info(f"SUCCESS! Listing ID: {listing_id}")
                
                results["marketplaces"][marketplace_id] = result_data
            else:
                error_text = publish_response.text[:300] if publish_response.text else "Unknown error"
                result_data = {
                    "success": False,
                    "offer_id": offer_id,
                    "error": error_text
                }
                
                # Add retry info
                if attempt_num > 1:
                    result_data["retries"] = attempt_num - 1
                    logger.error(f"Publish failed after {attempt_num} attempts: {error_text}")
                else:
                    logger.error(f"Publish failed: {error_text}")
                
                results["marketplaces"][marketplace_id] = result_data
    
    # Update draft with results
    successful_marketplaces = [
        mp for mp, data in results["marketplaces"].items() 
        if data.get("success")
    ]
    
    update_data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "multi_marketplace_results": results["marketplaces"]
    }
    
    if successful_marketplaces:
        update_data["status"] = "PUBLISHED"
        # Store first successful listing_id
        first_success = results["marketplaces"][successful_marketplaces[0]]
        update_data["listing_id"] = first_success.get("listing_id")
        update_data["offer_id"] = first_success.get("offer_id")
    
    # Save detailed mapping: marketplace → {sku, offerId, listingId}
    marketplace_listings = {}
    for mp_id, mp_result in results["marketplaces"].items():
        if mp_result.get("success"):
            mp_suffix = mp_id.replace("EBAY_", "").lower()
            marketplace_listings[mp_id] = {
                "sku": f"{sku}-{mp_suffix}",
                "offer_id": mp_result.get("offer_id"),
                "listing_id": mp_result.get("listing_id"),
                "listing_url": mp_result.get("listing_url")
            }
    
    update_data["marketplace_listings"] = marketplace_listings
    logger.info(f"Saving marketplace_listings: {marketplace_listings}")
    
    await db.drafts.update_one({"id": draft_id}, {"$set": update_data})
    
    logger.info("=" * 60)
    logger.info(f"MULTI-MARKETPLACE PUBLISH COMPLETE")
    logger.info(f"Results: {results}")
    logger.info("=" * 60)
    
    return results


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
