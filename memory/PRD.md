# SkateBay - eBay Listing Manager for Vintage Skateboard Shop

## Original Problem Statement
Full-stack web app (React frontend + FastAPI backend + MongoDB) per creare inserzioni eBay in modo semi-automatico per un negozio di skateboard vintage. L'utente carica solo le foto; l'app genera titolo/descrizione/item specifics in inglese (eBay-optimized) usando LLM, salva una bozza modificabile nell'app e pubblica su eBay solo dopo approvazione.

## User Personas
- **Admin User**: Shop owner managing vintage skateboard listings (Wheels, Trucks, Decks)
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

## What's Been Implemented (December 2025)

### Backend (/app/backend/server.py)
- [x] JWT Authentication (admin login with password)
- [x] Draft CRUD operations (create, read, update, delete)
- [x] File upload with local storage
- [x] LLM content generation endpoint
- [x] eBay OAuth flow (start, callback, token refresh)
- [x] Settings management (policy IDs)
- [x] Stats endpoint for dashboard
- [x] API logging for eBay calls
- [x] SKU generation with counter
- [x] **Preview endpoint with HTML sanitization (bleach)**

### Frontend Pages
- [x] Login page with brutalist design
- [x] Dashboard with stats cards and drafts list
- [x] New Draft Wizard (4 steps: type, photos, details, generate)
- [x] Draft Editor with full editing capabilities
- [x] Settings page with eBay connection
- [x] **Draft Preview page with Desktop/Mobile tabs and Rendered/HTML toggle**
- [x] **Auto-title generation from Item Specifics (Brand, Model, Size, Era)**
- [x] **Manual override flag - title stops auto-updating when manually edited**
- [x] **Regenerate title button to rebuild from aspects**
- [x] **Preview auto-saves before opening**
- [x] **NEW: Batch Upload page (/batch/new) with drag&drop for 20-200 images**
- [x] **NEW: Batch Review page (/batch/:id) with group management (split, merge, delete)**

### API Endpoints
- POST /api/auth/login
- GET /api/auth/me
- GET /api/drafts, POST /api/drafts
- GET/PATCH/DELETE /api/drafts/{id}
- **GET /api/drafts/{id}/preview** - returns sanitized HTML preview data
- POST /api/drafts/{id}/generate
- POST /api/drafts/{id}/publish
- POST /api/upload
- GET /api/settings, PATCH /api/settings
- GET /api/ebay/auth/start
- GET /api/ebay/auth/callback
- GET /api/ebay/status
- GET /api/ebay/policies
- GET /api/stats
- **NEW: POST /api/batches** - create batch
- **NEW: GET /api/batches** - list batches
- **NEW: GET /api/batches/{id}** - get batch details
- **NEW: POST /api/batches/{id}/upload** - upload multiple images
- **NEW: GET /api/batches/{id}/images** - get batch images
- **NEW: GET /api/batches/{id}/groups** - get batch groups
- **NEW: POST /api/batches/{id}/auto_group** - start auto-grouping (background)
- **NEW: POST /api/batches/{id}/generate_drafts** - generate drafts (background)
- **NEW: GET /api/jobs/{id}** - get job progress
- **NEW: PATCH /api/batches/{id}/groups/{gid}** - update group
- **NEW: POST /api/batches/{id}/groups/{gid}/split** - split group
- **NEW: POST /api/batches/{id}/merge_groups** - merge groups
- **NEW: POST /api/batches/{id}/move_image** - move image between groups
- **NEW: DELETE /api/batches/{id}/groups/{gid}** - delete group
- **NEW: DELETE /api/batches/{id}** - delete batch

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

## Prioritized Backlog

### P0 (Critical - Required for Production)
- [ ] Configure eBay Sandbox credentials
- [ ] Set up eBay business policies
- [ ] Test full publish flow

### P1 (High Priority)
- [ ] Image analysis with GPT vision for better content generation
- [ ] Bulk draft creation
- [ ] Draft duplication feature

### P2 (Medium Priority)
- [ ] Production eBay environment switch
- [ ] Email notifications on publish
- [ ] Analytics dashboard

## Next Tasks
1. Create eBay Developer account and get Sandbox credentials
2. Configure EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, EBAY_REDIRECT_URI
3. Create test seller account in eBay Sandbox
4. Set up business policies in eBay Sandbox
5. Test complete publish flow
