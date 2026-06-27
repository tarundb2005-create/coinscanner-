from pycoingecko import CoinGeckoAPI
import threading
import time
import logging

logger = logging.getLogger(__name__)

class CoinGeckoService:
    """
    Handles all CoinGecko operations.

    - Logo cache with multi-page fetching and normalization
    - Global stats
    - Trending
    - Future CoinGecko features
    """

    # Alternative image CDNs as fallbacks
    FALLBACK_LOGO_URLS = {
        "BTC": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png",
        "ETH": "https://assets.coingecko.com/coins/images/279/large/ethereum.png",
        "USDT": "https://assets.coingecko.com/coins/images/325/large/Tether.png",
        "BNB": "https://assets.coingecko.com/coins/images/825/large/binance-coin-logo.png",
        "SOL": "https://assets.coingecko.com/coins/images/4128/large/solana.png",
        "XRP": "https://assets.coingecko.com/coins/images/44/large/xrp-symbol-white-128.png",
        "USDC": "https://assets.coingecko.com/coins/images/6319/large/USD_Coin_icon.png",
        "ADA": "https://assets.coingecko.com/coins/images/975/large/cardano.png",
        "AVAX": "https://assets.coingecko.com/coins/images/9072/large/avalanche-8.png",
        "DOGE": "https://assets.coingecko.com/coins/images/5/large/dogecoin.png",
        "TRX": "https://assets.coingecko.com/coins/images/1094/large/tron-logo.png",
        "DOT": "https://assets.coingecko.com/coins/images/12171/large/polkadot.png",
        "LINK": "https://assets.coingecko.com/coins/images/877/large/chainlink-new-logo.png",
        "MATIC": "https://assets.coingecko.com/coins/images/4713/large/matic-token-icon.png",
        "LTC": "https://assets.coingecko.com/coins/images/2/large/litecoin.png",
        "SHIB": "https://assets.coingecko.com/coins/images/11939/large/shiba.png",
        "UNI": "https://assets.coingecko.com/coins/images/12504/large/uniswap-uni.png",
        "ATOM": "https://assets.coingecko.com/coins/images/1481/large/cosmos_hub.png",
        "XLM": "https://assets.coingecko.com/coins/images/100/large/stellar.png",
        "ETC": "https://assets.coingecko.com/coins/images/455/large/ethereum-classic-logo.png",
        "BCH": "https://assets.coingecko.com/coins/images/780/large/bitcoin-cash-circle.png",
        "APT": "https://assets.coingecko.com/coins/images/26455/large/aptos_round.png",
        "FIL": "https://assets.coingecko.com/coins/images/12817/large/filecoin.png",
        "NEAR": "https://assets.coingecko.com/coins/images/10365/large/near_icon.png",
        "ARB": "https://assets.coingecko.com/coins/images/16547/large/arbitrum.png",
        "OP": "https://assets.coingecko.com/coins/images/25244/large/op.png",
        "INJ": "https://assets.coingecko.com/coins/images/12882/large/injective.png",
        "MKR": "https://assets.coingecko.com/coins/images/1364/large/Mark_Maker.png",
        "AAVE": "https://assets.coingecko.com/coins/images/13016/large/aave.png",
        "SUI": "https://assets.coingecko.com/coins/images/26375/large/sui-ocean-cube.png",
    }

    def __init__(self):
        self.cg = CoinGeckoAPI()

        self.logo_cache = {}
        self.logo_timestamp = 0
        self.search_cache = {}
        self.details_cache = {}

        self.lock = threading.Lock()

    # ────────────────────────────────────────────────────
    # Logo Loading — Multi-page fetch for comprehensive coverage
    # ────────────────────────────────────────────────────

    def load_logos(self):
        """
        Fetch and cache coin logos from CoinGecko.
        
        Attempts to fetch multiple pages to cover more coins.
        Caches for 24 hours. Logs all loaded logos for debugging.
        
        Logs:
        - Total logos loaded
        - Logos for major coins (BTC, ETH, SOL, etc.)
        - Any API errors encountered
        """

        with self.lock:

            if time.time() - self.logo_timestamp < 86400:
                logger.info(f"Logo cache still fresh: {len(self.logo_cache)} coins cached")
                return

            self.logo_cache.clear()
            fetched_count = 0

            try:
                # Fetch up to 10 pages (250 coins per page = 2,500 coins)
                # This should cover most trading pairs
                for page in range(1, 11):

                    try:
                        markets = self.cg.get_coins_markets(
                            vs_currency="usd",
                            per_page=250,
                            page=page,
                            timeout=10,
                            order="market_cap_desc"
                        )

                        if not markets:
                            logger.info(f"CoinGecko page {page} returned empty — stopping fetch")
                            break

                        for coin in markets:

                            symbol = coin.get("symbol", "").upper()
                            image = coin.get("image")
                            coin_id = coin.get("id")

                            # Normalize: Only cache if we have both symbol and image URL
                            if symbol and image:
                                self.logo_cache[symbol] = image
                                fetched_count += 1
                            if symbol and coin_id:
                                self.search_cache[symbol] = coin_id
                                
                                # Log first fetch of major coins
                                if symbol in ["BTC", "ETH", "SOL", "USDT", "BNB"]:
                                    logger.info(f"Cached logo for {symbol}: {image[:60]}...")

                    except Exception as e:
                        logger.warning(f"Error fetching CoinGecko page {page}: {e}")
                        if page == 1:
                            # If first page fails, abort
                            raise

                self.logo_timestamp = time.time()
                
                # Log summary
                logger.info(f"[OK] Loaded {fetched_count} CoinGecko logos in cache")
                print(f"[OK] Loaded {fetched_count} CoinGecko logos from API")

            except Exception as e:
                logger.error(f"Critical error loading CoinGecko logos: {e}")
                print(f"[ERROR] CoinGecko logo error: {e}")

    def get_logo(self, symbol):
        """
        Get logo URL for a coin symbol.
        
        Fallback chain:
        1. Check runtime cache
        2. Check hardcoded fallback URLs for major coins
        3. Return default fallback image
        
        Args:
            symbol (str): Coin symbol (BTC, ETH, etc.)
            
        Returns:
            str: Logo URL or path to default image
        """

        if not self.logo_cache:
            self.load_logos()

        # Primary: check runtime cache
        cached = self.logo_cache.get(symbol.upper())
        if cached:
            return cached

        # Secondary: check hardcoded fallback for major coins
        fallback = self.FALLBACK_LOGO_URLS.get(symbol.upper())
        if fallback:
            logger.debug(f"Using fallback logo for {symbol}: {fallback[:50]}...")
            return fallback

        # Tertiary: return default
        logger.debug(f"No logo found for {symbol} — using default")
        return "/static/images/default-coin.png"

    # ────────────────────────────────────────────────────
    # Global Stats
    # ────────────────────────────────────────────────────

    def get_global(self):

        try:
            return self.cg.get_global()

        except Exception:
            return {}

    # ----------------------------------------------------
    # Trending
    # ----------------------------------------------------

    def get_trending(self):

        try:
            return self.cg.get_search_trending()

        except Exception:
            return {}

    # ────────────────────────────────────────────────────
    # Coin Search, Details & Charts Fallbacks
    # ────────────────────────────────────────────────────

    def search_coin(self, symbol):
        """
        Search for a coin on CoinGecko by its symbol or name.
        Returns the CoinGecko ID (str) or None.
        """
        symbol_upper = symbol.upper()
        if symbol_upper in self.search_cache:
            return self.search_cache[symbol_upper]

        try:
            res = self.cg.search(query=symbol)
            coins = res.get("coins", [])
            for c in coins:
                if c.get("symbol", "").upper() == symbol_upper:
                    coin_id = c.get("id")
                    self.search_cache[symbol_upper] = coin_id
                    return coin_id
            if coins:
                coin_id = coins[0].get("id")
                self.search_cache[symbol_upper] = coin_id
                return coin_id
        except Exception as e:
            logger.warning(f"CoinGecko search error for {symbol}: {e}")
        return None

    def get_coin_details(self, coin_id):
        """
        Fetch full details for a coin from CoinGecko. Cached for 1 hour.
        """
        now = time.time()
        if coin_id in self.details_cache:
            ts, data = self.details_cache[coin_id]
            if now - ts < 3600:
                return data

        try:
            data = self.cg.get_coin_by_id(id=coin_id)
            self.details_cache[coin_id] = (now, data)
            return data
        except Exception as e:
            logger.warning(f"CoinGecko details error for {coin_id}: {e}")
            if coin_id in self.details_cache:
                return self.details_cache[coin_id][1]
            return {}

    def get_coin_chart(self, coin_id, vs_currency="inr", days=7):
        """
        Fetch historical market chart data for a coin.
        """
        try:
            return self.cg.get_coin_market_chart_by_id(id=coin_id, vs_currency=vs_currency, days=days)
        except Exception as e:
            logger.warning(f"CoinGecko market chart error for {coin_id}: {e}")
            return {}


coingecko = CoinGeckoService()