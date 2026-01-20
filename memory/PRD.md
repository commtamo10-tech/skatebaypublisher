# SkateBay - eBay Listing Manager for Vintage Skateboard Shop

## Original Problem Statement
Full-stack web app (React frontend + FastAPI backend + MongoDB) per creare inserzioni eBay in modo semi-automatico per un negozio di skateboard vintage.

---

## What's Been Implemented (January 2025)

### ✅ LATEST - OAuth Fix & Enhanced Logging (Jan 19, 2025)

#### Environment Variable `EBAY_ENV`
- [x] Aggiunto `EBAY_ENV=sandbox|production` in `.env`
- [x] Backend legge da env, con override da DB settings

#### OAuth URLs Corretti
```
Sandbox:
  - authorize: https://auth.sandbox.ebay.com/oauth2/authorize
  - token: https://api.sandbox.ebay.com/identity/v1/oauth2/token

Production:
  - authorize: https://auth.ebay.com/oauth2/authorize  
  - token: https://api.ebay.com/identity/v1/oauth2/token
```

#### Authorize URL Parameters (tutti obbligatori)
- `client_id` - App ID registrato su eBay Developer
- `response_type=code` - Authorization Code Grant
- `redirect_uri` - DEVE combaciare esattamente con quello registrato
- `scope` - sell.inventory + sell.account
- `state` - Random token per CSRF protection

#### Logging Dettagliato
```
🔐 EBAY OAUTH START - Environment: SANDBOX
📋 OAuth Parameters:
   auth_base_url: https://auth.sandbox.ebay.com/oauth2/authorize
   client_id: Pasquale-VintageS-SBX-...
   response_type: code
   redirect_uri: https://vintage-lister.../api/ebay/auth/callback
   scope: sell.inventory sell.account
   state: movRJZvNEewIVwfv...
🔗 FULL AUTHORIZE URL: https://auth.sandbox.ebay.com/oauth2/authorize?...
```

#### Debug Endpoint
- `GET /api/ebay/oauth/config` - Mostra configurazione OAuth completa

---

### Retry Automatico Safe (Jan 19)
- [x] Retry su HTTP 429 e 5xx (max 3 tentativi)
- [x] Backoff esponenziale con jitter
- [x] Rispetto header Retry-After
- [x] Prevenzione duplicati (skip se già pubblicato)

### Multi-Marketplace Bootstrap (Jan 19)
- [x] Bootstrap automatico policy per US, DE, ES, AU
- [x] Clear logging per publish (payload + response)

---

## Environment Variables (.env)

```bash
# eBay Environment
EBAY_ENV=sandbox  # or production

# Sandbox credentials
EBAY_CLIENT_ID=...
EBAY_CLIENT_SECRET=...
EBAY_REDIRECT_URI=https://your-domain/api/ebay/auth/callback
EBAY_RUNAME=  # optional, use redirect_uri if empty
EBAY_SCOPES=https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.account

# Production credentials
EBAY_PROD_CLIENT_ID=...
EBAY_PROD_CLIENT_SECRET=...
EBAY_PROD_REDIRECT_URI=...
EBAY_PROD_RUNAME=...
```

---

## Key API Endpoints

### OAuth
- `GET /api/ebay/oauth/config` - Debug OAuth configuration
- `GET /api/ebay/auth/start` - Start OAuth flow (returns auth_url)
- `GET /api/ebay/auth/callback` - OAuth callback handler

### Multi-Marketplace
- `POST /api/settings/ebay/bootstrap-marketplaces`
- `POST /api/drafts/{id}/publish-multi`
- `GET /api/marketplaces`

---

## Prioritized Backlog

### P0 (Completed ✅)
- [x] OAuth fix con URL corretti
- [x] Enhanced logging
- [x] Retry automatico
- [x] Multi-marketplace bootstrap

### P1 (Next)
- [ ] Test OAuth in Production con credenziali reali
- [ ] Test publish su marketplace EU (DE/ES)

### P2
- [ ] Migrazione Supabase
- [ ] Refactoring server.py

---

## Credentials for Testing
- **Password**: admin123
- **API**: https://eboard-publish.preview.emergentagent.com
- **eBay**: Sandbox (connected)

---

## Files of Reference
- `/app/backend/server.py`
- `/app/backend/.env` (EBAY_ENV, credentials)
- `/app/backend/ebay_config.py`
- `/app/frontend/src/pages/Settings.js`
