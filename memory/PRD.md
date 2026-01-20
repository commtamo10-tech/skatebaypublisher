# SkateBay - eBay Listing Manager for Vintage Skateboard Shop

## Original Problem Statement
Full-stack web app (React frontend + FastAPI backend + MongoDB) per creare inserzioni eBay in modo semi-automatico per un negozio di skateboard vintage.
L'obiettivo si è evoluto in un'applicazione multi-marketplace (US, DE, ES, AU), con la capacità di pubblicare lo stesso prodotto su più siti eBay contemporaneamente.

---

## What's Been Implemented (January 2025)

### ✅ LATEST - Fulfillment Policy Clone & Update Strategy (Jan 20, 2025)

#### Problema Risolto
Il bootstrap delle fulfillment policy falliva con errori come "DOMESTIC_SHIPPING_REQUIRED" e "Please select a valid postage service" perché la creazione di policy da zero era troppo complessa.

#### Soluzione Implementata
Nuova strategia "Clone & Update":
1. Cerca policy esistente per nome `AUTO_INTL_V2` (se già creata)
2. Se non esiste, usa la prima policy esistente come template
3. Carica oggetto completo con `getFulfillmentPolicy(id)`
4. Aggiorna SOLO `shippingCost` mantenendo i `shippingServiceCode` originali
5. Salva con `updateFulfillmentPolicy(id, fullObject)`

#### Conversione Valute Automatica
Tariffe di spedizione convertite usando tassi BCE (Banca Centrale Europea):
- €10 Europa → $11.63 USD (US), 17.34 AUD (AU)
- Tassi scaricati dal feed XML BCE e messi in cache per 12h

#### File Modificati
- `/app/backend/server.py` - Logica Clone & Update nello Step 3 di bootstrap
- `/app/backend/exchange_rates.py` - Modulo tassi di cambio BCE

---

### ✅ Multi-Marketplace Publishing (Jan 19, 2025)
- [x] Pubblicazione corretta su US, DE, ES, AU
- [x] SKU unici per marketplace
- [x] categoryId specifico per sito
- [x] Content-Language header corretto
- [x] Product identifiers (Brand, MPN, UPC, EAN)

### ✅ Taxonomy API Integration (Jan 19, 2025)
- [x] Auto-suggest categorie via API Taxonomy eBay
- [x] Endpoint `/api/drafts/{id}/auto-suggest-categories`
- [x] Bottone "Auto-Suggest Categories" in UI

### ✅ OAuth Fix & Enhanced Logging (Jan 19, 2025)
- [x] URL OAuth corretti per sandbox e production
- [x] Logging dettagliato flusso OAuth
- [x] Debug endpoint `/api/ebay/oauth/config`

---

## Environment Variables (.env)

```bash
# eBay Environment
EBAY_ENV=production  # or sandbox

# Production credentials
EBAY_PROD_CLIENT_ID=...
EBAY_PROD_CLIENT_SECRET=...
EBAY_PROD_REDIRECT_URI=...
EBAY_PROD_RUNAME=...

EBAY_SCOPES=https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.account
```

---

## Key API Endpoints

### Multi-Marketplace
- `POST /api/settings/ebay/bootstrap-marketplaces` - Bootstrap policy per tutti i marketplace
- `POST /api/drafts/{id}/publish-multi` - Pubblica su marketplace selezionati
- `POST /api/drafts/{id}/auto-suggest-categories` - Auto-suggest categorie via Taxonomy API

### OAuth
- `GET /api/ebay/oauth/config` - Debug OAuth configuration
- `GET /api/ebay/auth/start` - Start OAuth flow
- `GET /api/ebay/auth/callback` - OAuth callback handler

---

## Prioritized Backlog

### P0 (Completed ✅)
- [x] OAuth fix con URL corretti
- [x] Multi-marketplace publishing (US, DE, ES, AU)
- [x] Taxonomy API integration
- [x] **Fulfillment Policy Clone & Update con tariffe BCE**

### P1 (Next)
- [ ] Test cancellazione sincronizzata listing su più marketplace
- [ ] UI per Item Specifics (attributi richiesti per categoria)

### P2 
- [ ] **Refactoring server.py** (>4500 righe - CRITICO)
- [ ] Migrazione Supabase/Postgres

### P3
- [ ] Dashboard analisi performance

---

## Credentials for Testing
- **Password**: admin123
- **eBay**: Production (ebay.it) connected

---

## Files of Reference
- `/app/backend/server.py` (monolite da refactorizzare)
- `/app/backend/exchange_rates.py` (modulo tassi BCE)
- `/app/backend/ebay_config.py`
- `/app/frontend/src/pages/Settings.js`
- `/app/frontend/src/pages/DraftEditor.js`
