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

### ✅ END-TO-END TEST PASSED (Jan 19, 2025)

**Pubblicazione su EBAY_US testata con successo!**

```
📦 OFFER PAYLOAD FOR EBAY_US
{
  "sku": "OSS-WHL-000049",
  "marketplaceId": "EBAY_US",
  "format": "FIXED_PRICE",
  "price": { "value": "55.0", "currency": "USD" },
  "categoryId": "117034",
  "merchantLocationKey": "warehouse_us",
  "listingPolicies": {
    "fulfillmentPolicyId": "6214096000",
    "paymentPolicyId": "6214098000",
    "returnPolicyId": "6214097000"
  }
}

🚀 PUBLISHING OFFER 10596028010 to EBAY_US
📬 PUBLISH RESPONSE: Status 200
{ "listingId": "110588679629" }

✅ Listing URL: https://www.sandbox.ebay.com/itm/110588679629
```

### Multi-Marketplace Bootstrap (Jan 19, 2025)

#### Bootstrap Automatico Multi-Marketplace
- [x] Nuovo endpoint `POST /api/settings/ebay/bootstrap-marketplaces`
- [x] Creazione automatica inventory location per ogni marketplace
- [x] Recupero dinamico shipping services via eBay Metadata API (con fallback)
- [x] Creazione automatica policy (fulfillment, payment, return)
- [x] Return policy: 30 giorni, seller pays, domestic only
- [x] Salvataggio policy IDs nel database per-marketplace

#### API Marketplaces  
- [x] `GET /api/marketplaces` - Lista marketplace con stato configurazione
- [x] Ogni marketplace mostra: name, currency, country_code, is_configured, policies, location

#### Clear Logging
- [x] `📦 OFFER PAYLOAD` - JSON formattato con tutti i campi dell'offer
- [x] `🚀 PUBLISHING OFFER` - Indica inizio pubblicazione
- [x] `📬 PUBLISH RESPONSE` - Status code + response JSON (listingId o errors)

#### UI Settings
- [x] Pulsante "Bootstrap Marketplaces" con loading state
- [x] Griglia 4 marketplace con badge Ready/Not Configured
- [x] Visualizzazione policy IDs e location keys

#### UI Draft Editor
- [x] Marketplace configurati selezionabili (sfondo blu)
- [x] Marketplace non configurati disabilitati (sfondo grigio)
- [x] Badge verde ✓ / giallo ! per stato
- [x] Warning se marketplace non configurati

---

## Database Schema (MongoDB)

### Settings Collection
```javascript
{
  "_id": "app_settings",
  "ebay_environment": "sandbox",
  "ebay_connected": true,
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
    // DE, ES, AU: parzialmente configurati (sandbox limitation)
  }
}
```

---

## Key API Endpoints

### Multi-Marketplace
- `POST /api/settings/ebay/bootstrap-marketplaces` - Auto-configure all marketplaces
- `GET /api/marketplaces` - Get marketplace list with config status
- `POST /api/drafts/{id}/publish-multi` - Publish to multiple marketplaces

### eBay Category IDs (verified working)
- **117034**: Skateboard Wheels ✅ (testato)
- **36631**: Skateboard Trucks
- **16263**: Skateboard Decks  
- **36642**: Skateboard Clothing
- **16265**: Other Skateboarding

---

## Sandbox Limitations (DE/ES/AU)

Il Sandbox eBay ha limitazioni per i marketplace non-US:

| Marketplace | Location | Fulfillment | Payment | Return | Status |
|-------------|----------|-------------|---------|--------|--------|
| EBAY_US | ✅ | ✅ | ✅ | ✅ | **READY** |
| EBAY_DE | ✅ | ✅ | ❌ | ✅ | Partial |
| EBAY_ES | ✅ | ❌ | ❌ | ✅ | Partial |
| EBAY_AU | ✅ | ✅ | ❌ | ✅ | Partial |

**Causa**: 
- Payment policy: `PERSONAL_CHECK` non supportato (solo Production)
- Fulfillment ES: shipping service code non valido per Sandbox
- Metadata API: restituisce 404 per DE/ES/AU

**Workaround**: Testare in Production per DE/ES/AU

---

## Prioritized Backlog

### P0 (Completed ✅)
- [x] Multi-marketplace bootstrap automatico
- [x] Publish end-to-end su EBAY_US
- [x] Clear logging (payload + response)

### P1 (Next)
- [ ] Test publish su DE/ES/AU con credenziali Production

### P2 (Medium Priority)
- [ ] Migrazione a Supabase (Postgres) - in pausa
- [ ] Refactoring server.py in router separati
- [ ] Refactoring DraftEditor.js in componenti

### P3 (Future)
- [ ] Visual clustering per batch auto-grouping
- [ ] Background job queue (Celery)
- [ ] S3 storage per immagini

---

## Credentials for Testing
- **Password**: admin123
- **API**: https://vintage-lister.preview.emergentagent.com
- **eBay Environment**: Sandbox

---

## Files of Reference
- `/app/backend/server.py` - Main backend
- `/app/backend/ebay_config.py` - Marketplace configuration
- `/app/frontend/src/pages/Settings.js` - Settings page
- `/app/frontend/src/pages/DraftEditor.js` - Draft editor
