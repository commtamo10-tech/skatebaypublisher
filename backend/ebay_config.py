# eBay Multi-Marketplace Configuration (Hardcoded for Happy Path)
# TODO: Move to database/Supabase later

MARKETPLACE_CONFIG = {
    "EBAY_US": {
        "name": "United States",
        "site_id": "0",
        "currency": "USD",
        "country_code": "US",
        "language": "en-US",
        "default_price": 25.00,
        "default_shipping_cost": 25.00,
        "api_url": "https://api.ebay.com",  # Production
        "sandbox_api_url": "https://api.sandbox.ebay.com",
        # Policy IDs - to be filled after OAuth and policy creation
        "fulfillment_policy_id": None,
        "payment_policy_id": None,
        "return_policy_id": None,
        "category_id": "36632",  # Skateboard Wheels
        "merchant_location_key": "default_location",
    },
    "EBAY_DE": {
        "name": "Germany",
        "site_id": "77",
        "currency": "EUR",
        "country_code": "DE",
        "language": "de-DE",
        "default_price": 12.00,
        "default_shipping_cost": 12.00,
        "api_url": "https://api.ebay.com",
        "sandbox_api_url": "https://api.sandbox.ebay.com",
        "fulfillment_policy_id": None,
        "payment_policy_id": None,
        "return_policy_id": None,
        "category_id": "36632",
        "merchant_location_key": "default_location",
    },
    "EBAY_ES": {
        "name": "Spain",
        "site_id": "186",
        "currency": "EUR",
        "country_code": "ES",
        "language": "es-ES",
        "default_price": 12.00,
        "default_shipping_cost": 12.00,
        "api_url": "https://api.ebay.com",
        "sandbox_api_url": "https://api.sandbox.ebay.com",
        "fulfillment_policy_id": None,
        "payment_policy_id": None,
        "return_policy_id": None,
        "category_id": "36632",
        "merchant_location_key": "default_location",
    },
    "EBAY_AU": {
        "name": "Australia",
        "site_id": "15",
        "currency": "AUD",
        "country_code": "AU",
        "language": "en-AU",
        "default_price": 100.00,
        "default_shipping_cost": 100.00,
        "api_url": "https://api.ebay.com",
        "sandbox_api_url": "https://api.sandbox.ebay.com",
        "fulfillment_policy_id": None,
        "payment_policy_id": None,
        "return_policy_id": None,
        "category_id": "36632",
        "merchant_location_key": "default_location",
    },
}

# Default handling time in business days
DEFAULT_HANDLING_TIME = 3

# Shipping service codes by marketplace (will be fetched via Metadata API)
# These are fallbacks if API call fails
FALLBACK_SHIPPING_SERVICES = {
    "EBAY_US": "USPSPriority",
    "EBAY_DE": "DE_DHLPaket",
    "EBAY_ES": "ES_CorreosSpainInternationalEconomyMail",
    "EBAY_AU": "AU_StandardDelivery",
}

# Category mapping by item type
CATEGORY_BY_ITEM_TYPE = {
    "WHL": {  # Wheels
        "EBAY_US": "36632",
        "EBAY_DE": "36632",
        "EBAY_ES": "36632",
        "EBAY_AU": "36632",
    },
    "TRK": {  # Trucks
        "EBAY_US": "36631",
        "EBAY_DE": "36631",
        "EBAY_ES": "36631",
        "EBAY_AU": "36631",
    },
    "DCK": {  # Decks
        "EBAY_US": "16263",
        "EBAY_DE": "16263",
        "EBAY_ES": "16263",
        "EBAY_AU": "16263",
    },
    "APP": {  # Apparel
        "EBAY_US": "36642",
        "EBAY_DE": "36642",
        "EBAY_ES": "36642",
        "EBAY_AU": "36642",
    },
    "MISC": {  # Miscellaneous
        "EBAY_US": "16265",
        "EBAY_DE": "16265",
        "EBAY_ES": "16265",
        "EBAY_AU": "16265",
    },
}


def get_marketplace_config(marketplace_id: str, use_sandbox: bool = True) -> dict:
    """Get configuration for a specific marketplace"""
    config = MARKETPLACE_CONFIG.get(marketplace_id, {}).copy()
    if use_sandbox:
        config["api_url"] = config.get("sandbox_api_url", config.get("api_url"))
    return config


def get_all_marketplaces() -> list:
    """Get list of all supported marketplace IDs"""
    return list(MARKETPLACE_CONFIG.keys())


def get_category_for_item(item_type: str, marketplace_id: str) -> str:
    """Get category ID for an item type and marketplace"""
    return CATEGORY_BY_ITEM_TYPE.get(item_type, {}).get(marketplace_id, "16265")
