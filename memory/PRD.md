# SkateBay - eBay Listing Manager for Vintage Skateboard Shop

## Original Problem Statement
Full-stack web app (React frontend + FastAPI backend + MongoDB) per creare inserzioni eBay in modo semi-automatico per un negozio di skateboard vintage. L'utente carica solo le foto; l'app genera titolo/descrizione/item specifics in inglese (eBay-optimized) usando LLM, salva una bozza modificabile nell'app e pubblica su eBay solo dopo approvazione.

## User Personas
- **Admin User**: Shop owner managing vintage skateboard listings (Wheels, Trucks, Decks, Apparel, Misc)
- **Single user authentication** (password-based)

## Core Requirements (Static)
1. Photo upload with local storage and public URL generation
2. LLM-powered content generation (title ≤80 chars, description, aspects)
3. Draft management with statuses: DRAFT, READY, PUBLISHED, ERROR
4. eBay OAuth integration (Sandbox initially, Production-ready)
5. Business policies configuration (fulfillment, return, payment)
6. SKU generation: OSS-<TYPE>-<SEQ> format
7. Validation before publish

## Tech Stack
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + Python
- **Database**: MongoDB
- **LLM**: OpenAI GPT-5.2 via Emergent Universal Key
- **Design**: Swiss Brutalist style (Chivo + JetBrains Mono fonts)

## What's Been Implemented (January 2025)

### LATEST UPDATE - Core Details & Enhanced Auto-populate (Jan 16, 2025)

#### Core Details Section (Always Visible)
- [x] New "CORE DETAILS" section always present in Draft Editor with highlighted border
- [x] Five core fields: Brand, Model, Size, Color, Era/Decade
- [x] Core fields synced bidirectionally with aspects
- [x] Auto-fill button in Core Details section
- [x] Era as dropdown with predefined options (1970s, 1980s, 1990s, 2000s, 1980s-1990s)

#### Enhanced Auto-populate with Metadata
- [x] `aspects_metadata` field tracks source and confidence for each aspect
- [x] Source can be: "photo", "title", or "manual"
- [x] Confidence score (0-1) from LLM analysis
- [x] Title fallback when no images available
- [x] "Force Re-autofill" button to override manual edits
- [x] Low confidence values (< 0.3) automatically filtered out

#### 90s Sticker Label Description (Improved)
- [x] Auto-regenerates when Core Details change
- [x] Description only includes non-empty values
- [x] Template structure:
  - `[ OLD SCHOOL SKATE ]` header with Era tag
  - Collector intro (2-3 sentences)
  - KEY DETAILS bullet list
  - CONDITION section with photo disclaimer
  - INFO section (shipping from Milan, Italy)

#### Auto-sync with Override
- [x] Title auto-updates when core details change (if not manually edited)
- [x] Description auto-updates when core details/condition change
- [x] `titleManuallyEdited` flag preserved
- [x] `descriptionManuallyEdited` flag preserved
- [x] Regenerate buttons reset override flags

### Previous Implementation
- [x] Default Condition = NEW for all drafts
- [x] JWT Authentication (admin login with password)
- [x] Draft CRUD operations with PATCH partial updates
- [x] File upload with local storage
- [x] LLM content generation endpoint
- [x] eBay OAuth flow (start, callback, token refresh)
- [x] Settings management (policy IDs)
- [x] Preview page with sanitized HTML
- [x] Batch Upload with auto-grouping

### Frontend Pages
- [x] Login page with brutalist design
- [x] Dashboard with stats cards and drafts list
- [x] New Draft Wizard (4 steps: type, photos, details, generate)
- [x] **Draft Editor** with:
  - Core Details section (always visible, highlighted)
  - Auto-fill specifics button with source/confidence tracking
  - Title with character counter (70-80 target)
  - 90s sticker label description
  - Additional Item Specifics section
  - Regenerate buttons for title/description
  - Badge "auto" for auto-filled fields
- [x] Draft Preview page with Rendered/HTML toggle
- [x] Settings page with eBay connection
- [x] Batch Upload page (/batch/new)
- [x] Batch Review page (/batch/:id)

### API Endpoints
- POST /api/auth/login
- GET /api/auth/me
- GET /api/drafts, POST /api/drafts
- GET/PATCH/DELETE /api/drafts/{id}
- GET /api/drafts/{id}/preview
- POST /api/drafts/{id}/generate
- **POST /api/drafts/{id}/autofill_aspects** (with ?force=true option)
- POST /api/drafts/{id}/publish
- POST /api/upload
- GET /api/settings, PATCH /api/settings
- GET /api/ebay/auth/start, /callback, /status
- GET /api/ebay/policies
- GET /api/stats
- Batch endpoints: POST /api/batches, etc.

## Database Schema (MongoDB)

### Drafts Collection
```javascript
{
  id: "uuid",
  sku: "OSS-WHL-000001",
  item_type: "WHL",
  
  // Core Details (always present)
  brand: "Powell Peralta",
  model: "G-Bones",
  size: "64mm",
  color: "Yellow",
  era: "1980s",
  
  // Content
  title: "...",
  title_manually_edited: false,
  description: "<div>...</div>",
  description_manually_edited: false,
  
  // Aspects with metadata
  aspects: {
    "Brand": "Powell Peralta",
    "Model": "G-Bones",
    "Size": "64mm",
    ...
  },
  aspects_metadata: {
    "Brand": { source: "photo", confidence: 0.95 },
    "Model": { source: "manual", confidence: 1 },
    ...
  },
  
  // Listing details
  condition: "NEW",
  category_id: "16265",
  price: 50.00,
  image_urls: [],
  status: "DRAFT",
  
  // eBay
  offer_id: null,
  listing_id: null,
  error_message: null,
  
  // Timestamps
  created_at: "2025-01-16T...",
  updated_at: "2025-01-16T..."
}
```

## Prioritized Backlog

### P0 (Critical - Required for Production)
- [ ] Configure eBay Sandbox credentials
- [ ] Set up eBay business policies
- [ ] Test full publish flow

### P1 (High Priority)
- [ ] Visual clustering for batch auto-grouping (CLIP embeddings)
- [ ] Manual grouping tools: Split, Merge, Drag & Drop
- [ ] Background job queue (Celery) for batch operations

### P2 (Medium Priority)
- [ ] Production eBay environment switch
- [ ] S3/Supabase storage for images
- [ ] Refactoring: split server.py into routes/models

## Item Type Specifics

### WHL (Wheels)
**Core:** Brand, Model, Size (mm), Color, Era
**Additional:** Durometer (A), Core, Material, Quantity, MPN

### TRK (Trucks)
**Core:** Brand, Model, Size, Color, Era
**Additional:** Material, Quantity, MPN

### DCK (Decks)
**Core:** Brand, Model, Size (Width in), Color, Era
**Additional:** Series, Length, Artist, Type (OG/Reissue), Material

### APP (Apparel)
**Core:** Brand, Model, Size, Color, Era
**Additional:** Item Type, Department, Measurements, Material, Style, Fit

### MISC
**Core:** Brand, Model, Size, Color, Era
**Additional:** Item Type, Material, Notes

## Title Builder Rules
- Max 80 characters (hard limit)
- Target: 70-80 characters for SEO
- Order: Brand + Model + Era + OG/NOS + Color + Size + "Skateboard [Type]"
- Keyword fillers: "Vintage", "Old School" (if under 70 chars)
- Never include "Unknown", "N/A", empty values

## 90s Sticker Label Description Template
```html
<div style="font-family: Arial; font-size: 14px; line-height: 1.45; color: #111;">
  <div style="display: inline-block; border: 1px solid #111; padding: 6px 10px; font-family: monospace; letter-spacing: 1px;">
    [ OLD SCHOOL SKATE ] • {Era}
  </div>
  <p>{Collector intro - 2-3 sentences}</p>
  <h2>KEY DETAILS</h2>
  <ul>{Only non-empty aspects as bullet list}</ul>
  <h2>CONDITION</h2>
  <p>{Condition label}. Please review all photos carefully...</p>
  <h2>INFO</h2>
  <p>Questions? Feel free to message...</p>
  <p>Ships from Milan, Italy...</p>
  <p>International buyers: duties not included...</p>
  <p>Thanks for looking!</p>
</div>
```

## Auto-populate Logic

### Source Priority
1. **Photo analysis** (GPT-5.2 vision) - Primary source
2. **Title extraction** - Fallback when no images or vision fails
3. **Manual entry** - User edits always override auto-fill

### Anti-hallucination Rules
- Confidence < 0.3: Field not saved
- Invalid values filtered: "unknown", "n/a", "assumed", "estimate", etc.
- Empty values: Never saved to database
- Manual edits: Never overwritten (unless "Force Re-autofill")

## Credentials for Testing
- **Password**: admin123
- **API**: https://vintage-lister.preview.emergentagent.com
