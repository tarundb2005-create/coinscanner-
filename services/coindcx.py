import requests
import threading
import time


class CoinDCXService:

    BASE_URL = "https://api.coindcx.com"

    def __init__(self):

        self.price_cache = {}
        self.price_timestamp = 0

        self.lock = threading.Lock()

    def get_tickers(self):

        try:
            r = requests.get(
                f"{self.BASE_URL}/exchange/ticker",
                timeout=10,
            )

            r.raise_for_status()

            return r.json()

        except Exception:

            return []

    def get_markets(self):

        try:
            r = requests.get(
                f"{self.BASE_URL}/exchange/v1/markets_details",
                timeout=10,
            )

            r.raise_for_status()

            return r.json()

        except Exception:

            return []


coindcx = CoinDCXService()