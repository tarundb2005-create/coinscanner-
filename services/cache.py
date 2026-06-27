import json
import threading
import time

_cache_lock = threading.Lock()

PRICE_CACHE = {"data": {}, "timestamp": 0}
META_CACHE = {"data": {}, "timestamp": 0}
GLOBAL_CACHE = {"data": {}, "timestamp": 0}
NEWS_CACHE = {"data": [], "timestamp": 0}
MARKET_CACHE = {"data": ([], [], []), "timestamp": 0}


def redis_cache_get(redis_client, app, key):
    if not redis_client:
        return None
    try:
        raw = redis_client.get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        app.logger.warning("Redis cache get failed for %s: %s", key, e)
        return None


def redis_cache_set(redis_client, app, key, value, ttl):
    if not redis_client:
        return False
    try:
        redis_client.setex(key, ttl, json.dumps(value))
        return True
    except Exception as e:
        app.logger.warning("Redis cache set failed for %s: %s", key, e)
        return False