# eBay Multi-Marketplace Configuration
# Structured settings per marketplace with policies, shipping, and location

from typing import Dict, Any, Optional

# Default marketplace configurations
DEFAULT_MARKETPLACE_SETTINGS = {
    "EBAY_US": {
        "name": "United States",
        "site_id": "0",
        "currency": "USD",
        "country_code": "US",
        "language": "en-US",
        "price": {"value": 25.00, "currency": "USD"},
        "shipping_standard": {
            "cost": {"value": 25.00, "currency": "USD"},
            "handling_time_days": 3,
            "shipping_service_code": None  # Will be fetched from Metadata API
        },
        "policies": {
            "fulfillment_policy_id": None,
            "payment_policy_id": None,
            "return_policy_id": None
        },
        "merchant_location_key": None
    },
    "EBAY_DE": {
        "name": "Germany",
        "site_id": "77",
        "currency": "EUR",
        "country_code": "DE",
        "language": "de-DE",
        "price": {"value": 12.00, "currency": "EUR"},
        "shipping_standard": {
            "cost": {"value": 12.00, "currency": "EUR"},
            "handling_time_days": 3,
            "shipping_service_code": None
        },
        "policies": {
            "fulfillment_policy_id": None,
            "payment_policy_id": None,
            "return_policy_id": None
        },
        "merchant_location_key": None
    },
    "EBAY_ES": {
        "name": "Spain",
        "site_id": "186",
        "currency": "EUR",
        "country_code": "ES",
        "language": "es-ES",
        "price": {"value": 12.00, "currency": "EUR"},
        "shipping_standard": {
            "cost": {"value": 12.00, "currency": "EUR"},
            "handling_time_days": 3,
            "shipping_service_code": None
        },
        "policies": {
            "fulfillment_policy_id": None,
            "payment_policy_id": None,
            "return_policy_id": None
        },
        "merchant_location_key": None
    },
    "EBAY_AU": {
        "name": "Australia",
        "site_id": "15",
        "currency": "AUD",
        "country_code": "AU",
        "language": "en-AU",
        "price": {"value": 100.00, "currency": "AUD"},
        "shipping_standard": {
            "cost": {"value": 100.00, "currency": "AUD"},
            "handling_time_days": 3,
            "shipping_service_code": None
        },
        "policies": {
            "fulfillment_policy_id": None,
            "payment_policy_id": None,
            "return_policy_id": None
        },
        "merchant_location_key": None
    },
}

# Category mapping by item type
CATEGORY_BY_ITEM_TYPE = {
    "WHL": {"EBAY_US": "36632", "EBAY_DE": "36632", "EBAY_ES": "36632", "EBAY_AU": "36632"},
    "TRK": {"EBAY_US": "36631", "EBAY_DE": "36631", "EBAY_ES": "36631", "EBAY_AU": "36631"},
    "DCK": {"EBAY_US": "16263", "EBAY_DE": "16263", "EBAY_ES": "16263", "EBAY_AU": "16263"},
    "APP": {"EBAY_US": "36642", "EBAY_DE": "36642", "EBAY_ES": "36642", "EBAY_AU": "36642"},
    "MISC": {"EBAY_US": "16265", "EBAY_DE": "16265", "EBAY_ES": "16265", "EBAY_AU": "16265"},
}


def get_default_marketplace_config(marketplace_id: str) -> dict:
    """Get default configuration for a marketplace"""
    return DEFAULT_MARKETPLACE_SETTINGS.get(marketplace_id, {}).copy()


def get_marketplace_config(marketplace_id: str, db_settings: dict = None) -> dict:
    """
    Get configuration for a specific marketplace.
    Merges default config with DB settings (DB takes priority).
    """
    config = get_default_marketplace_config(marketplace_id)
    if not config:
        return None
    
    # Override with DB settings if provided
    if db_settings and "marketplaces" in db_settings:
        mp_settings = db_settings.get("marketplaces", {}).get(marketplace_id, {})
        if mp_settings:
            # Merge price
            if "price" in mp_settings:
                config["price"] = mp_settings["price"]
            
            # Merge shipping
            if "shipping_standard" in mp_settings:
                config["shipping_standard"].update(mp_settings["shipping_standard"])
            
            # Merge policies
            if "policies" in mp_settings:
                config["policies"].update(mp_settings["policies"])
            
            # Merge location
            if mp_settings.get("merchant_location_key"):
                config["merchant_location_key"] = mp_settings["merchant_location_key"]
    
    return config


def get_all_marketplaces() -> list:
    """Get list of all supported marketplace IDs"""
    return list(DEFAULT_MARKETPLACE_SETTINGS.keys())


def get_category_for_item(item_type: str, marketplace_id: str) -> str:
    """Get category ID for an item type and marketplace"""
    return CATEGORY_BY_ITEM_TYPE.get(item_type, {}).get(marketplace_id, "16265")


def validate_marketplace_for_publish(marketplace_id: str, config: dict) -> list:
    """
    Validate that a marketplace has all required fields for publishing.
    Returns list of missing fields, empty if all OK.
    """
    missing = []
    
    if not config:
        return [f"Unknown marketplace: {marketplace_id}"]
    
    policies = config.get("policies", {})
    if not policies.get("fulfillment_policy_id"):
        missing.append(f"fulfillment_policy_id for {marketplace_id}")
    if not policies.get("payment_policy_id"):
        missing.append(f"payment_policy_id for {marketplace_id}")
    if not policies.get("return_policy_id"):
        missing.append(f"return_policy_id for {marketplace_id}")
    if not config.get("merchant_location_key"):
        missing.append(f"merchant_location_key for {marketplace_id}")
    
    return missing


def get_marketplace_display_info() -> list:
    """Get marketplace info for UI display"""
    result = []
    for mp_id, config in DEFAULT_MARKETPLACE_SETTINGS.items():
        result.append({
            "id": mp_id,
            "name": config["name"],
            "currency": config["currency"],
            "country_code": config["country_code"],
            "default_price": config["price"]["value"],
            "default_shipping": config["shipping_standard"]["cost"]["value"]
        })
    return result
