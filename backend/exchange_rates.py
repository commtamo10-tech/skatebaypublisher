# Exchange Rates Module - BCE Daily Rates
# Fetches EUR exchange rates from European Central Bank and caches them

import httpx
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Cache for exchange rates
_rates_cache: Dict[str, float] = {}
_cache_timestamp: Optional[datetime] = None
_CACHE_DURATION = timedelta(hours=12)

# BCE XML feed URL
BCE_FEED_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"

# Fallback rates (in case BCE feed is unavailable)
FALLBACK_RATES = {
    "USD": 1.08,  # 1 EUR = 1.08 USD
    "AUD": 1.65,  # 1 EUR = 1.65 AUD
    "GBP": 0.85,  # 1 EUR = 0.85 GBP
}


async def fetch_bce_rates() -> Dict[str, float]:
    """Fetch latest exchange rates from BCE XML feed"""
    global _rates_cache, _cache_timestamp
    
    # Check if cache is still valid
    if _cache_timestamp and (datetime.now(timezone.utc) - _cache_timestamp) < _CACHE_DURATION:
        logger.info(f"Using cached exchange rates (age: {datetime.now(timezone.utc) - _cache_timestamp})")
        return _rates_cache
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(BCE_FEED_URL)
            
            if response.status_code == 200:
                # Parse XML
                root = ET.fromstring(response.text)
                
                # Navigate to Cube elements with rates
                # Structure: <Cube time="..."><Cube currency="USD" rate="1.08"/>...</Cube>
                ns = {"gesmes": "http://www.gesmes.org/xml/2002-08-01", 
                      "eurofxref": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
                
                rates = {"EUR": 1.0}  # Base currency
                
                # Find all Cube elements with currency attribute
                for cube in root.iter():
                    if 'currency' in cube.attrib and 'rate' in cube.attrib:
                        currency = cube.attrib['currency']
                        rate = float(cube.attrib['rate'])
                        rates[currency] = rate
                
                if len(rates) > 1:
                    _rates_cache = rates
                    _cache_timestamp = datetime.now(timezone.utc)
                    logger.info(f"Fetched {len(rates)} exchange rates from BCE. USD={rates.get('USD')}, AUD={rates.get('AUD')}")
                    return rates
                else:
                    logger.warning("BCE feed returned no rates, using fallback")
                    
    except Exception as e:
        logger.error(f"Error fetching BCE rates: {e}")
    
    # Use fallback or cached rates
    if _rates_cache:
        logger.info("Using previously cached rates")
        return _rates_cache
    
    logger.warning("Using fallback exchange rates")
    return {"EUR": 1.0, **FALLBACK_RATES}


def convert_currency(amount: float, from_currency: str, to_currency: str, rates: Dict[str, float]) -> float:
    """
    Convert amount from one currency to another using EUR as base.
    
    Args:
        amount: Amount to convert
        from_currency: Source currency code (e.g., "EUR", "USD")
        to_currency: Target currency code
        rates: Dict of currency -> EUR rate (1 EUR = X currency)
    
    Returns:
        Converted amount
    """
    if from_currency == to_currency:
        return amount
    
    # Get rates (all rates are EUR-based: 1 EUR = X currency)
    from_rate = rates.get(from_currency, 1.0)
    to_rate = rates.get(to_currency, 1.0)
    
    # Convert: amount in from_currency -> EUR -> to_currency
    # If from_currency is EUR: amount * to_rate
    # If to_currency is EUR: amount / from_rate
    # Otherwise: (amount / from_rate) * to_rate
    
    if from_currency == "EUR":
        result = amount * to_rate
    elif to_currency == "EUR":
        result = amount / from_rate
    else:
        # Cross rate
        result = (amount / from_rate) * to_rate
    
    return result


def round_price(amount: float, style: str = "clean") -> str:
    """
    Round price for display.
    
    Args:
        amount: Price amount
        style: "clean" (2 decimals) or "psychological" (.99)
    
    Returns:
        Formatted price string
    """
    if style == "psychological":
        # Round to .99
        return f"{int(amount)}.99"
    else:
        # Clean 2 decimals
        return f"{amount:.2f}"


async def get_shipping_rates_for_marketplace(marketplace_id: str) -> Dict[str, Dict]:
    """
    Get shipping rates converted to the marketplace's currency.
    
    Base rates (what seller charges):
    - Europe: 10 EUR
    - Americas: 25 USD  
    - Rest of World: 45 USD
    
    Returns dict with rates in marketplace's currency.
    """
    rates = await fetch_bce_rates()
    
    # Base rates
    europe_eur = 10.0
    americas_usd = 25.0
    rest_of_world_usd = 45.0
    
    # Marketplace currencies
    MARKETPLACE_CURRENCIES = {
        "EBAY_US": "USD",
        "EBAY_DE": "EUR",
        "EBAY_ES": "EUR",
        "EBAY_AU": "AUD",
        "EBAY_IT": "EUR",
        "EBAY_UK": "GBP",
    }
    
    currency = MARKETPLACE_CURRENCIES.get(marketplace_id, "USD")
    
    # Convert all rates to marketplace currency
    if currency == "EUR":
        europe_rate = europe_eur
        americas_rate = convert_currency(americas_usd, "USD", "EUR", rates)
        row_rate = convert_currency(rest_of_world_usd, "USD", "EUR", rates)
    elif currency == "USD":
        europe_rate = convert_currency(europe_eur, "EUR", "USD", rates)
        americas_rate = americas_usd
        row_rate = rest_of_world_usd
    elif currency == "AUD":
        europe_rate = convert_currency(europe_eur, "EUR", "AUD", rates)
        americas_rate = convert_currency(americas_usd, "USD", "AUD", rates)
        row_rate = convert_currency(rest_of_world_usd, "USD", "AUD", rates)
    elif currency == "GBP":
        europe_rate = convert_currency(europe_eur, "EUR", "GBP", rates)
        americas_rate = convert_currency(americas_usd, "USD", "GBP", rates)
        row_rate = convert_currency(rest_of_world_usd, "USD", "GBP", rates)
    else:
        # Default to USD
        europe_rate = convert_currency(europe_eur, "EUR", "USD", rates)
        americas_rate = americas_usd
        row_rate = rest_of_world_usd
        currency = "USD"
    
    return {
        "currency": currency,
        "europe": {
            "value": round_price(europe_rate),
            "currency": currency
        },
        "americas": {
            "value": round_price(americas_rate),
            "currency": currency
        },
        "rest_of_world": {
            "value": round_price(row_rate),
            "currency": currency
        },
        "rates_timestamp": _cache_timestamp.isoformat() if _cache_timestamp else None
    }
