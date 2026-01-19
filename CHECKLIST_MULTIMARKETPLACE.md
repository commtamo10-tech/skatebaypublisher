# 📋 CHECKLIST: Multi-Marketplace eBay Publish

## Pre-requisiti

### 1. Configurazione Environment (`.env`)
Assicurati che in `/app/backend/.env` siano configurate le credenziali eBay:

**Per Sandbox:**
```
EBAY_CLIENT_ID=Pasquale-VintageS-SBX-xxx
EBAY_CLIENT_SECRET=SBX-xxx
EBAY_REDIRECT_URI=https://vintage-lister.preview.emergentagent.com/api/ebay/auth/callback
EBAY_RUNAME=Pasquale_Crispi-Pasquale-Vintag-xxx
```

**Per Production (quando pronto):**
```
EBAY_PROD_CLIENT_ID=xxx
EBAY_PROD_CLIENT_SECRET=xxx
EBAY_PROD_REDIRECT_URI=https://xxx/api/ebay/auth/callback
EBAY_PROD_RUNAME=xxx
```

---

## Step 1: Connessione eBay

1. [ ] Vai su `/settings`
2. [ ] Seleziona Environment: **Sandbox** (o Production)
3. [ ] Clicca **Connect eBay**
4. [ ] Completa OAuth su eBay
5. [ ] Verifica: Clicca **DEBUG** → deve mostrare `connected: true`

---

## Step 2: Configurazione Policy per Marketplace

⚠️ **IMPORTANTE**: Ogni marketplace richiede le proprie policy!

### Per ogni marketplace (EBAY_US, EBAY_DE, EBAY_ES, EBAY_AU):

1. [ ] Clicca **Fetch from eBay** (crea policy se non esistono)
2. [ ] Annota i policy IDs restituiti:
   - `fulfillment_policy_id`: _______________
   - `payment_policy_id`: _______________
   - `return_policy_id`: _______________
3. [ ] Salva i policy IDs nel database tramite Settings

### Configurazione DB Settings (via API o UI)

Per ogni marketplace, devi salvare in settings.marketplaces:

```json
{
  "marketplaces": {
    "EBAY_US": {
      "fulfillment_policy_id": "xxx",
      "payment_policy_id": "xxx",
      "return_policy_id": "xxx",
      "merchant_location_key": "location_us",
      "default_price": 25.00
    },
    "EBAY_DE": {
      "fulfillment_policy_id": "xxx",
      "payment_policy_id": "xxx",
      "return_policy_id": "xxx",
      "merchant_location_key": "location_de",
      "default_price": 12.00
    },
    // ... etc per ES, AU
  }
}
```

---

## Step 3: Creazione Draft

1. [ ] Vai su Dashboard → Upload Photos
2. [ ] Carica almeno 1 foto
3. [ ] Compila:
   - **Title**: (es. "Vintage Powell Peralta Wheels 1990s OG Rare")
   - **Price**: (es. 25.00)
   - **Item Type**: WHL/TRK/DCK/APP/MISC
4. [ ] Salva il draft

---

## Step 4: Pubblicazione Multi-Marketplace

1. [ ] Apri il draft editor
2. [ ] In basso, nella sezione **Select Marketplaces**:
   - [ ] Seleziona i marketplace desiderati (es. EBAY_US + EBAY_DE)
3. [ ] Clicca **PUBLISH**
4. [ ] Verifica risultati:
   - [ ] Per ogni marketplace deve mostrare:
     - ✅ Success + Listing ID + Link
     - O ❌ Error message specifico

---

## Step 5: Verifica Listing

Per ogni marketplace pubblicato:

1. [ ] Clicca il link "View on eBay"
2. [ ] Verifica che l'inserzione sia visibile
3. [ ] Verifica prezzo corretto (USD/EUR/AUD)
4. [ ] Verifica che le policy siano applicate

---

## Troubleshooting

### Errore: "Missing policy IDs for EBAY_DE"
→ Le policy per quel marketplace non sono configurate. Vai su Settings e configura.

### Errore: "eBay not connected"
→ Rifare OAuth: Settings → Connect eBay

### Errore: "Invalid or expired state"
→ Sessione OAuth scaduta. Riprova Connect eBay.

### Errore: "Inventory creation failed"
→ Controlla che titolo e immagini siano presenti.

### Errore: "Item.Country"
→ La merchant location non è stata creata. Il sistema dovrebbe crearla automaticamente.

---

## API Endpoints di Riferimento

```bash
# Login
POST /api/auth/login
{"password": "admin123"}

# Get settings
GET /api/settings

# Update settings (con marketplace config)
PATCH /api/settings
{
  "marketplaces": {
    "EBAY_US": {
      "fulfillment_policy_id": "xxx",
      "payment_policy_id": "xxx", 
      "return_policy_id": "xxx"
    }
  }
}

# Get marketplaces
GET /api/marketplaces

# Publish multi-marketplace
POST /api/drafts/{id}/publish-multi
{
  "marketplaces": ["EBAY_US", "EBAY_DE"]
}

# Debug eBay connection
GET /api/ebay/debug

# Fetch/create policies
GET /api/ebay/policies
```

---

## Note

- I prezzi di default sono definiti in `ebay_config.py`:
  - EBAY_US: 25.00 USD
  - EBAY_DE: 12.00 EUR
  - EBAY_ES: 12.00 EUR
  - EBAY_AU: 100.00 AUD

- Le location vengono create automaticamente al momento della pubblicazione

- Lo stesso SKU può essere pubblicato su più marketplace con offer separate
