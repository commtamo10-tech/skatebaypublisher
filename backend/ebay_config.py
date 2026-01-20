# eBay Multi-Marketplace Configuration
# Structured settings per marketplace with policies, shipping, and location

from typing import Dict, Any, Optional, List

# Default handling time (days)
DEFAULT_HANDLING_TIME = 3

# Shipping rates (from Italy to destinations)
SHIPPING_RATES = {
    "EUROPE": {"value": "10.00", "currency": "USD"},      # Europe incl. UK, CH
    "USA_CANADA": {"value": "25.00", "currency": "USD"},  # USA + Canada
    "REST_OF_WORLD": {"value": "45.00", "currency": "USD"} # Rest of World
}

# Fallback shipping service codes per marketplace (used if Metadata API fails)
FALLBACK_SHIPPING_SERVICES = {
    "EBAY_US": "USPSPriority",
    "EBAY_DE": "DE_DeutschePostBrief",
    "EBAY_ES": "ES_CorreosDeEspanaPaqueteAzul",
    "EBAY_AU": "AU_StandardDelivery",
    "EBAY_IT": "IT_PosteItalianeRaccomandata",
    "EBAY_UK": "UK_RoyalMailFirstClassStandard",
}

# Default marketplace configurations
MARKETPLACE_CONFIG = {
    "EBAY_US": {
        "name": "United States",
        "site_id": "0",
        "currency": "USD",
        "country_code": "US",
        "language": "en-US",
        "price": {"value": 50.00, "currency": "USD"},
        "shipping_rate": SHIPPING_RATES["USA_CANADA"],
        "shipping_standard": {
            "cost": SHIPPING_RATES["USA_CANADA"],
            "handling_time_days": DEFAULT_HANDLING_TIME,
            "shipping_service_code": None
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
        "price": {"value": 45.00, "currency": "EUR"},
        "shipping_rate": SHIPPING_RATES["EUROPE"],
        "shipping_standard": {
            "cost": SHIPPING_RATES["EUROPE"],
            "handling_time_days": DEFAULT_HANDLING_TIME,
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
        "price": {"value": 45.00, "currency": "EUR"},
        "shipping_rate": SHIPPING_RATES["EUROPE"],
        "shipping_standard": {
            "cost": SHIPPING_RATES["EUROPE"],
            "handling_time_days": DEFAULT_HANDLING_TIME,
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
        "price": {"value": 80.00, "currency": "AUD"},
        "shipping_rate": SHIPPING_RATES["REST_OF_WORLD"],
        "shipping_standard": {
            "cost": SHIPPING_RATES["REST_OF_WORLD"],
            "handling_time_days": DEFAULT_HANDLING_TIME,
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

# Alias for backward compatibility
DEFAULT_MARKETPLACE_SETTINGS = MARKETPLACE_CONFIG

# Category mapping by item type (eBay leaf category IDs)
# Using 159043 as universal fallback (Sporting Goods > Skateboarding > Parts)
# Note: Category 36632 works for AU but not for other marketplaces
CATEGORY_BY_ITEM_TYPE = {
    "WHL": {
        "EBAY_US": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
        "EBAY_DE": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
        "EBAY_ES": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
        "EBAY_AU": "36632",   # Skateboard Wheels (works for AU)
        "EBAY_IT": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
        "EBAY_UK": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
    },
    "TRK": {
        "EBAY_US": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
        "EBAY_DE": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
        "EBAY_ES": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
        "EBAY_AU": "36631",   # Skateboard Trucks
        "EBAY_IT": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
        "EBAY_UK": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
    },
    "DCK": {
        "EBAY_US": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
        "EBAY_DE": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
        "EBAY_ES": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
        "EBAY_AU": "16263",   # Skateboard Decks
        "EBAY_IT": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
        "EBAY_UK": "159043",  # Sporting Goods > Skateboarding > Parts (universal)
    },
    "APP": {
        "EBAY_US": "159043",  # Sporting Goods > Other
        "EBAY_DE": "159043",  # Sporting Goods > Other
        "EBAY_ES": "159043",  # Sporting Goods > Other
        "EBAY_AU": "36642",   # Skateboard Clothing
        "EBAY_IT": "159043",  # Sporting Goods > Other
        "EBAY_UK": "159043",  # Sporting Goods > Other
    },
    "MISC": {
        "EBAY_US": "159043",  # Sporting Goods > Other
        "EBAY_DE": "159043",  # Sporting Goods > Other
        "EBAY_ES": "159043",  # Sporting Goods > Other
        "EBAY_AU": "159043",  # Sporting Goods > Other
        "EBAY_IT": "159043",  # Sporting Goods > Other
        "EBAY_UK": "159043",  # Sporting Goods > Other
    },
}


def get_default_marketplace_config(marketplace_id: str) -> dict:
    """Get default configuration for a marketplace"""
    return MARKETPLACE_CONFIG.get(marketplace_id, {}).copy()


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
            
            # Merge policies - flatten from nested structure
            if "policies" in mp_settings:
                config["policies"].update(mp_settings["policies"])
            
            # Also check for flat policy IDs (for backward compatibility)
            for policy_key in ["fulfillment_policy_id", "payment_policy_id", "return_policy_id"]:
                if mp_settings.get(policy_key):
                    config["policies"][policy_key] = mp_settings[policy_key]
            
            # Merge location
            if mp_settings.get("merchant_location_key"):
                config["merchant_location_key"] = mp_settings["merchant_location_key"]
    
    return config


def get_all_marketplaces() -> list:
    """Get list of all supported marketplace IDs"""
    return list(MARKETPLACE_CONFIG.keys())


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


# Alias for backward compatibility with server.py import
validate_marketplace_config = validate_marketplace_for_publish


def get_marketplace_display_info() -> list:
    """Get marketplace info for UI display"""
    result = []
    for mp_id, config in MARKETPLACE_CONFIG.items():
        result.append({
            "id": mp_id,
            "name": config["name"],
            "currency": config["currency"],
            "country_code": config["country_code"],
            "default_price": config["price"]["value"],
            "default_shipping": config["shipping_standard"]["cost"]["value"]
        })
    return result


def get_shipping_rate_for_region(region: str) -> dict:
    """Get shipping rate for a specific region"""
    return SHIPPING_RATES.get(region, SHIPPING_RATES["REST_OF_WORLD"])
