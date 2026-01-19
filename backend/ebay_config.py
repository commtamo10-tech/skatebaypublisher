# eBay Multi-Marketplace Configuration
# Each marketplace has its own policy IDs and location

MARKETPLACE_CONFIG = {
    "EBAY_US": {
        "name": "United States",
        "site_id": "0",
        "currency": "USD",
        "country_code": "US",
        "language": "en-US",
        "default_price": 25.00,
        "default_shipping_cost": 25.00,
        # Policy IDs - MUST be set per marketplace for publishing to work
        "fulfillment_policy_id": None,  # Set after creating policy via API
        "payment_policy_id": None,
        "return_policy_id": None,
        # Location
        "merchant_location_key": "location_us",
    },
    "EBAY_DE": {
        "name": "Germany",
        "site_id": "77",
        "currency": "EUR",
        "country_code": "DE",
        "language": "de-DE",
        "default_price": 12.00,
        "default_shipping_cost": 12.00,
        "fulfillment_policy_id": None,
        "payment_policy_id": None,
        "return_policy_id": None,
        "merchant_location_key": "location_de",
    },
    "EBAY_ES": {
        "name": "Spain",
        "site_id": "186",
        "currency": "EUR",
        "country_code": "ES",
        "language": "es-ES",
        "default_price": 12.00,
        "default_shipping_cost": 12.00,
        "fulfillment_policy_id": None,
        "payment_policy_id": None,
        "return_policy_id": None,
        "merchant_location_key": "location_es",
    },
    "EBAY_AU": {
        "name": "Australia",
        "site_id": "15",
        "currency": "AUD",
        "country_code": "AU",
        "language": "en-AU",
        "default_price": 100.00,
        "default_shipping_cost": 100.00,
        "fulfillment_policy_id": None,
        "payment_policy_id": None,
        "return_policy_id": None,
        "merchant_location_key": "location_au",
    },
}

# Default handling time in business days
DEFAULT_HANDLING_TIME = 3

# Shipping service codes by marketplace (fallbacks)
FALLBACK_SHIPPING_SERVICES = {
    "EBAY_US": "USPSPriority",
    "EBAY_DE": "DE_DHLPaket",
    "EBAY_ES": "ES_CorreosSpainInternationalEconomyMail",
    "EBAY_AU": "AU_StandardDelivery",
}

# Category mapping by item type
CATEGORY_BY_ITEM_TYPE = {
    "WHL": {"EBAY_US": "36632", "EBAY_DE": "36632", "EBAY_ES": "36632", "EBAY_AU": "36632"},
    "TRK": {"EBAY_US": "36631", "EBAY_DE": "36631", "EBAY_ES": "36631", "EBAY_AU": "36631"},
    "DCK": {"EBAY_US": "16263", "EBAY_DE": "16263", "EBAY_ES": "16263", "EBAY_AU": "16263"},
    "APP": {"EBAY_US": "36642", "EBAY_DE": "36642", "EBAY_ES": "36642", "EBAY_AU": "36642"},
    "MISC": {"EBAY_US": "16265", "EBAY_DE": "16265", "EBAY_ES": "16265", "EBAY_AU": "16265"},
}


def get_marketplace_config(marketplace_id: str, db_settings: dict = None) -> dict:
    """
    Get configuration for a specific marketplace.
    Merges hardcoded config with DB settings (DB takes priority).
    """
    config = MARKETPLACE_CONFIG.get(marketplace_id, {}).copy()
    
    # Override with DB settings if provided
    if db_settings:
        mp_settings = db_settings.get("marketplaces", {}).get(marketplace_id, {})
        if mp_settings:
            config["fulfillment_policy_id"] = mp_settings.get("fulfillment_policy_id") or config.get("fulfillment_policy_id")
            config["payment_policy_id"] = mp_settings.get("payment_policy_id") or config.get("payment_policy_id")
            config["return_policy_id"] = mp_settings.get("return_policy_id") or config.get("return_policy_id")
            config["merchant_location_key"] = mp_settings.get("merchant_location_key") or config.get("merchant_location_key")
            if mp_settings.get("default_price"):
                config["default_price"] = mp_settings["default_price"]
    
    return config


def get_all_marketplaces() -> list:
    """Get list of all supported marketplace IDs"""
    return list(MARKETPLACE_CONFIG.keys())


def get_category_for_item(item_type: str, marketplace_id: str) -> str:
    """Get category ID for an item type and marketplace"""
    return CATEGORY_BY_ITEM_TYPE.get(item_type, {}).get(marketplace_id, "16265")


def validate_marketplace_config(marketplace_id: str, config: dict) -> list:
    """
    Validate that a marketplace has all required fields for publishing.
    Returns list of missing fields, empty if all OK.
    """
    missing = []
    
    if not config.get("fulfillment_policy_id"):
        missing.append(f"fulfillment_policy_id for {marketplace_id}")
    if not config.get("payment_policy_id"):
        missing.append(f"payment_policy_id for {marketplace_id}")
    if not config.get("return_policy_id"):
        missing.append(f"return_policy_id for {marketplace_id}")
    if not config.get("merchant_location_key"):
        missing.append(f"merchant_location_key for {marketplace_id}")
    
    return missing
