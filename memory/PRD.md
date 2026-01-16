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

### LATEST UPDATE - 90s Sticker Label & Auto-populate (Jan 16, 2025)
- [x] **Default Condition = NEW**: All new drafts (single and batch) now default to "New" condition
- [x] **90s Sticker Label Description Template**: New minimal HTML template compatible with eBay
  - `[ OLD SCHOOL SKATE ]` header with era tag
  - Collector intro section (2-3 sentences)
  - KEY DETAILS bullet list (auto-generated from aspects)
  - CONDITION section with photo disclaimer
  - INFO section with fixed shipping/contact info
  - All inline styles, no external CSS/JS
- [x] **Auto-populate Item Specifics (Vision LLM)**: New endpoint `/api/drafts/{id}/autofill_aspects`
  - Analyzes images using GPT-5.2 vision
  - Extracts Brand, Model, Size, Color, Era for each item type
  - Never writes "Unknown" - leaves empty if unsure
  - Tracks auto-filled fields with `auto_filled_aspects` array
- [x] **Auto-sync Title/Description**: 
  - Title auto-updates when key aspects change (Brand, Model, Size, Era, Color, etc.)
  - Description auto-regenerates with 90s template when aspects change
  - `titleManuallyEdited` and `descriptionManuallyEdited` flags for override
- [x] **Badge "auto" UI**: Auto-filled fields show cyan "auto" badge until manually edited
- [x] **Regenerate Buttons**: Separate buttons for title, description, and auto-fill specifics
- [x] **Title Character Counter**: Shows 64/80 with target hint (70-80 chars for SEO)
- [x] **Keyword Filler**: Adds "Vintage", "Old School", "OG", "NOS" to reach 70-80 chars

### Previous Implementation
- [x] JWT Authentication (admin login with password)
- [x] Draft CRUD operations (create, read, update, delete)
- [x] File upload with local storage
- [x] LLM content generation endpoint
- [x] eBay OAuth flow (start, callback, token refresh)
- [x] Settings management (policy IDs)
- [x] Stats endpoint for dashboard
- [x] API logging for eBay calls
- [x] SKU generation with counter
- [x] Preview endpoint with HTML sanitization (bleach)
- [x] Draft Preview page with Desktop/Mobile tabs
- [x] Batch Upload with auto-grouping and draft generation

### Frontend Pages
- [x] Login page with brutalist design
- [x] Dashboard with stats cards and drafts list
- [x] New Draft Wizard (4 steps: type, photos, details, generate)
- [x] Draft Editor with:
  - Auto-title generation from Item Specifics
  - Manual override flags
  - Regenerate buttons (title, description, auto-fill)
  - Badge "auto" for auto-filled aspects
  - 90s sticker label description template
  - Character counter for title (70-80 target)
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
- **POST /api/drafts/{id}/autofill_aspects** (NEW - vision LLM auto-populate)
- POST /api/drafts/{id}/publish
- POST /api/upload
- GET /api/settings, PATCH /api/settings
- GET /api/ebay/auth/start, /callback, /status
- GET /api/ebay/policies
- GET /api/stats
- Batch endpoints: POST /api/batches, GET /api/batches, etc.
- Job endpoints: GET /api/jobs/{id}

## Environment Variables Required
```
APP_ADMIN_PASSWORD=admin123
JWT_SECRET=<secret>
EBAY_CLIENT_ID=<from eBay developer portal>
EBAY_CLIENT_SECRET=<from eBay developer portal>
EBAY_REDIRECT_URI=<your callback URL>
EMERGENT_LLM_KEY=sk-emergent-... (provided)
FRONTEND_URL=<frontend URL>
```

## Database Schema (MongoDB)
```
drafts: {
  id, sku, item_type, title, description, aspects,
  auto_filled_aspects: [],  // NEW: tracks auto-filled fields
  condition: "NEW",  // Default changed from USED_GOOD
  title_manually_edited, description_manually_edited,
  category_id, price, image_urls, status, ...
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
Brand, Model, Size (mm), Durometer (A), Color, Era, Core, Material, Quantity, MPN

### TRK (Trucks)
Brand, Model, Size, Era, Color, Material, Quantity, MPN

### DCK (Decks)
Brand, Model, Series, Width (in), Length, Era, Artist, Type (OG/Reissue), Material

### APP (Apparel)
Brand, Item Type, Department, Size, Measurements, Color, Material, Style, Era

### MISC
Brand, Item Type, Era, Color, Material, Notes

## Title Builder Rules
- Max 80 characters (hard limit)
- Target: 70-80 characters for SEO
- Order by type: Brand + Model + Era + OG/NOS + Size + "Skateboard [Type]"
- Keyword fillers: "Vintage", "Old School" (if under 70 chars)
- OG/NOS mutually exclusive
- Never include "Unknown", "N/A", etc.

## 90s Sticker Label Description Template
```html
<div style="font-family: Arial; font-size: 14px; color: #111;">
  <div style="border: 1px solid #111; padding: 6px 10px; font-family: monospace;">
    [ OLD SCHOOL SKATE ] • {Era}
  </div>
  <p>{Collector intro}</p>
  <h2>KEY DETAILS</h2>
  <ul>{Bullet list from aspects}</ul>
  <h2>CONDITION</h2>
  <p>{Condition text + photo disclaimer}</p>
  <h2>INFO</h2>
  <p>Questions? Feel free to message...</p>
  <p>Ships from Milan, Italy...</p>
  <p>International buyers: duties not included...</p>
  <p>Thanks for looking!</p>
</div>
```

## Credentials for Testing
- **Password**: admin123
- **API**: https://vintage-skate-lister.preview.emergentagent.com
