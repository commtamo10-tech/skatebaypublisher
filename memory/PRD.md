# SkateBay - eBay Listing Manager for Vintage Skateboard Shop

## Original Problem Statement
Full-stack web app (React frontend + FastAPI backend + MongoDB) per creare inserzioni eBay in modo semi-automatico per un negozio di skateboard vintage. L'utente carica solo le foto; l'app genera titolo/descrizione/item specifics in inglese (eBay-optimized) usando LLM, salva una bozza modificabile nell'app e pubblica su eBay solo dopo approvazione.

**EVOLUZIONE**: L'applicazione è evoluta in un sistema multi-marketplace (US, DE, ES, AU) con bootstrap automatico delle policy.

## User Personas
- **Admin User**: Shop owner managing vintage skateboard listings (Wheels, Trucks, Decks, Apparel, Misc)
- **Single user authentication** (password-based)

## Tech Stack
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + Python
- **Database**: MongoDB
- **LLM**: OpenAI GPT-5.2 via Emergent Universal Key
- **Design**: Swiss Brutalist style (Chivo + JetBrains Mono fonts)

---

## What's Been Implemented (January 2025)

### 🆕 LATEST - Multi-Marketplace Bootstrap (Jan 19, 2025)

#### Bootstrap Automatico Multi-Marketplace
- [x] Nuovo endpoint `POST /api/settings/ebay/bootstrap-marketplaces`
- [x] Creazione automatica inventory location per ogni marketplace (`warehouse_us`, `warehouse_de`, etc.)
- [x] Recupero dinamico shipping services via eBay Metadata API (con fallback statico)
- [x] Creazione automatica fulfillment policy per marketplace
- [x] Creazione automatica payment policy per marketplace  
- [x] Creazione automatica return policy (30 giorni, seller pays, domestic only)
- [x] Salvataggio policy IDs nel database per-marketplace

#### API Marketplaces
- [x] `GET /api/marketplaces` - Lista marketplace con stato configurazione
- [x] Ogni marketplace mostra: name, currency, country_code, is_configured, policies, location

#### UI Settings - Sezione Multi-Marketplace
- [x] Pulsante "Bootstrap Marketplaces" con loading state
- [x] Griglia 4 marketplace con badge Ready/Not Configured
- [x] Visualizzazione policy IDs e location keys
- [x] Risultati bootstrap con dettaglio successi/errori

#### UI Draft Editor - Selettore Marketplace
- [x] Marketplace configurati sono cliccabili (sfondo blu quando selezionati)
- [x] Marketplace non configurati sono disabilitati (sfondo grigio)
- [x] Badge verde ✓ per configurati, giallo ! per non configurati
- [x] Messaggio "Not configured - run Bootstrap" per marketplace mancanti
- [x] Warning globale se alcuni marketplace non sono configurati

#### Publish Multi-Marketplace Aggiornato
- [x] `POST /api/drafts/{id}/publish-multi` usa policy per-marketplace dal DB
- [x] Validazione pre-pubblicazione: verifica che tutte le policy esistano
- [x] Supporto prezzi custom per marketplace

### Previous Implementation
- [x] Core Details section (Brand, Model, Size, Color, Era)
- [x] Auto-fill aspects with vision LLM + confidence scores
- [x] 90s sticker label description template
- [x] JWT Authentication
- [x] eBay OAuth flow (Sandbox + Production)
- [x] Environment toggle (Sandbox/Production)
- [x] Draft CRUD with PATCH updates
- [x] LLM content generation
- [x] Single-marketplace publish flow
- [x] Batch upload with auto-grouping

---

## Database Schema (MongoDB)

### Settings Collection
```javascript
{
  "_id": "app_settings",
  "ebay_environment": "sandbox",
  "ebay_connected": true,
  
  // Legacy (single marketplace)
  "fulfillment_policy_id": "6214096000",
  "return_policy_id": "6214097000",
  "payment_policy_id": "6214098000",
  "merchant_location_key": "default_location",
  
  // Multi-Marketplace (new)
  "marketplaces": {
    "EBAY_US": {
      "merchant_location_key": "warehouse_us",
      "policies": {
        "fulfillment_policy_id": "6214096000",
        "payment_policy_id": "6214098000",
        "return_policy_id": "6214097000"
      },
      "shipping_service_code": "USPSPriority"
    },
    "EBAY_DE": { ... },
    "EBAY_ES": { ... },
    "EBAY_AU": { ... }
  }
}
```

---

## Key API Endpoints

### Multi-Marketplace
- `POST /api/settings/ebay/bootstrap-marketplaces` - Auto-configure all marketplaces
- `GET /api/marketplaces` - Get marketplace list with config status
- `POST /api/drafts/{id}/publish-multi` - Publish to multiple marketplaces

### eBay Integration
- `GET /api/ebay/auth/start` - Start OAuth flow
- `GET /api/ebay/auth/callback` - OAuth callback
- `GET /api/ebay/status` - Connection status
- `GET /api/ebay/debug` - Debug info
- `GET /api/ebay/policies` - Fetch existing policies

### Settings
- `GET /api/settings` - Get settings
- `PATCH /api/settings` - Update settings

### Drafts
- `GET/POST /api/drafts` - List/Create
- `GET/PATCH/DELETE /api/drafts/{id}` - CRUD
- `POST /api/drafts/{id}/generate` - LLM generation
- `POST /api/drafts/{id}/autofill_aspects` - Vision auto-fill
- `POST /api/drafts/{id}/publish` - Single marketplace publish

---

## Prioritized Backlog

### P0 (Completed ✅)
- [x] Multi-marketplace bootstrap automatico
- [x] UI per gestione marketplace
- [x] Validazione pre-publish per marketplace

### P1 (High Priority - Next)
- [ ] **Fix payment policies per DE/ES/AU** - Il Sandbox eBay non supporta PERSONAL_CHECK per questi marketplace. Richiede test con credenziali Production.
- [ ] **End-to-end test publish su EBAY_US** - Verificare che il flusso completo funzioni con le policy bootstrap

### P2 (Medium Priority)
- [ ] Migrazione a Supabase (Postgres) - In pausa su richiesta utente
- [ ] Refactoring server.py (3000+ righe) in router separati
- [ ] Refactoring DraftEditor.js in componenti

### P3 (Future)
- [ ] Visual clustering per batch auto-grouping (CLIP embeddings)
- [ ] Background job queue (Celery)
- [ ] S3/Supabase storage per immagini

---

## Known Limitations

### eBay Sandbox
- La Metadata API (`getShippingServices`) restituisce 404 per DE, ES, AU
- La creazione di Payment Policy fallisce per DE, ES, AU (PERSONAL_CHECK non supportato)
- La creazione di Fulfillment Policy fallisce per ES (shipping service non valido)
- **Solo EBAY_US è completamente configurabile in Sandbox**

### Workaround
- Il sistema usa fallback hardcoded per shipping services
- Per testing completo di DE/ES/AU, usare credenziali Production

---

## Credentials for Testing
- **Password**: admin123
- **API**: https://vintage-lister.preview.emergentagent.com
- **eBay Environment**: Sandbox (configurabile in Settings)

---

## Files of Reference
- `/app/backend/server.py` - Main backend (3000+ lines)
- `/app/backend/ebay_config.py` - Marketplace configuration
- `/app/frontend/src/pages/Settings.js` - Settings page with Bootstrap
- `/app/frontend/src/pages/DraftEditor.js` - Draft editor with marketplace selector
