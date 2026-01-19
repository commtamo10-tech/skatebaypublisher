# SkateBay - eBay Listing Manager for Vintage Skateboard Shop

## Original Problem Statement
Full-stack web app (React frontend + FastAPI backend + MongoDB) per creare inserzioni eBay in modo semi-automatico per un negozio di skateboard vintage. L'utente carica solo le foto; l'app genera titolo/descrizione/item specifics in inglese (eBay-optimized) usando LLM, salva una bozza modificabile nell'app e pubblica su eBay solo dopo approvazione.

**EVOLUZIONE**: L'applicazione è evoluta in un sistema multi-marketplace (US, DE, ES, AU) con bootstrap automatico delle policy e retry resiliente.

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

### ✅ LATEST - Retry Automatico Safe (Jan 19, 2025)

#### Retry con Backoff Esponenziale
- [x] Helper function `retry_with_backoff()` per chiamate HTTP
- [x] Retry solo su HTTP 429 (rate limit) e 5xx (server errors)
- [x] Max 3 tentativi con backoff esponenziale (base 2s)
- [x] Jitter ±25% per evitare thundering herd
- [x] Rispetto header `Retry-After` per 429

#### Prevenzione Duplicati
- [x] Check listing esistente prima di publishOffer
- [x] Se SKU+marketplace ha già listingId → skip e ritorna risultato esistente
- [x] Check sia su eBay API che su draft history

#### Logging Migliorato
- [x] `🔄 RETRY {n}/{max}` con status code e error body
- [x] `⏭️ SKIPPING` con listing ID quando già pubblicato
- [x] `(attempt {n}/3)` nel response log
- [x] Campo `retries` nel risultato se ci sono stati retry
- [x] Campo `note` nel risultato per skip ("Already published")

#### updateOffer Safe
- [x] Invio payload completo con TUTTI i campi richiesti
- [x] Nessun rischio di perdere dati durante update

### ✅ END-TO-END TEST PASSED

**Test 1 - Pubblicazione normale:**
```json
{
  "success": true,
  "offer_id": "10596030010",
  "listing_id": "110588679631",
  "price": "49.99 USD",
  "listing_url": "https://www.sandbox.ebay.com/itm/110588679631"
}
```

**Test 2 - Chiamata duplicata (skip):**
```json
{
  "success": true,
  "offer_id": "10596030010",
  "listing_id": "110588679631",
  "note": "Already published (skipped)"
}
```

**Log output:**
```
📦 OFFER PAYLOAD FOR EBAY_US
🚀 PUBLISHING OFFER 10596030010 to EBAY_US
📬 PUBLISH RESPONSE FOR EBAY_US (attempt 1/3)
SUCCESS! Listing ID: 110588679631

// Seconda chiamata:
⏭️ SKIPPING EBAY_US - Already published with listing ID: 110588679631
```

---

## Previous Implementation

### Multi-Marketplace Bootstrap (Jan 19)
- [x] Endpoint `POST /api/settings/ebay/bootstrap-marketplaces`
- [x] Creazione automatica location + policy per marketplace
- [x] Return policy: 30 giorni, seller pays, domestic only
- [x] UI Settings con pulsante Bootstrap
- [x] UI Draft Editor con selettore marketplace

### Core Features
- [x] Draft CRUD con auto-fill aspects (Vision LLM)
- [x] JWT Authentication
- [x] eBay OAuth (Sandbox + Production toggle)
- [x] Batch upload con auto-grouping

---

## Database Schema (MongoDB)

### Settings Collection
```javascript
{
  "_id": "app_settings",
  "ebay_environment": "sandbox",
  "marketplaces": {
    "EBAY_US": {
      "merchant_location_key": "warehouse_us",
      "policies": {
        "fulfillment_policy_id": "...",
        "payment_policy_id": "...",
        "return_policy_id": "..."
      }
    }
  }
}
```

### Drafts Collection
```javascript
{
  "id": "uuid",
  "sku": "OSS-WHL-000050",
  "status": "PUBLISHED",
  "listing_id": "110588679631",
  "multi_marketplace_results": {
    "EBAY_US": {
      "success": true,
      "listing_id": "110588679631",
      "offer_id": "10596030010"
    }
  }
}
```

---

## Key API Endpoints

### Multi-Marketplace Publish
- `POST /api/drafts/{id}/publish-multi`
  - Body: `{"marketplaces": ["EBAY_US", "EBAY_DE"]}`
  - Features: retry on 429/5xx, skip if already published

### Bootstrap
- `POST /api/settings/ebay/bootstrap-marketplaces`
- `GET /api/marketplaces`

---

## Retry Logic Details

```python
async def retry_with_backoff(
    http_client, method, url, headers, json_body,
    max_retries=3, base_delay=2.0, context=""
):
    for attempt in range(1, max_retries + 1):
        response = await http_client.request(...)
        
        if response.status_code == 429 or response.status_code >= 500:
            # Log retry attempt
            logger.warning(f"🔄 RETRY {attempt}/{max_retries} - Status: {status}")
            
            if attempt < max_retries:
                # Respect Retry-After for 429
                if status == 429 and "Retry-After" in headers:
                    delay = float(headers["Retry-After"])
                else:
                    delay = base_delay * (2 ** (attempt - 1))  # 2s, 4s, 8s
                
                # Add jitter ±25%
                delay += delay * 0.25 * (random.random() * 2 - 1)
                await asyncio.sleep(delay)
                continue
        
        return response, attempt
```

---

## Sandbox Limitations

| Marketplace | Status |
|-------------|--------|
| EBAY_US | ✅ READY - testato e funzionante |
| EBAY_DE/ES/AU | ⚠️ Sandbox limitation - da testare in Production |

---

## Prioritized Backlog

### P0 (Completed ✅)
- [x] Multi-marketplace bootstrap
- [x] Retry automatico safe
- [x] Duplicate prevention
- [x] Clear logging

### P1 (Next)
- [ ] Test publish su DE/ES/AU con Production credentials

### P2 (Medium Priority)
- [ ] Migrazione a Supabase (in pausa)
- [ ] Refactoring server.py

### P3 (Future)
- [ ] Visual clustering batch upload
- [ ] Background job queue

---

## Credentials for Testing
- **Password**: admin123
- **API**: https://vintage-lister.preview.emergentagent.com
- **eBay**: Sandbox

---

## Files of Reference
- `/app/backend/server.py` - Main backend (include `retry_with_backoff`)
- `/app/backend/ebay_config.py` - Marketplace configuration
- `/app/frontend/src/pages/Settings.js` - Settings page
- `/app/frontend/src/pages/DraftEditor.js` - Draft editor
