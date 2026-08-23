from rest_framework.throttling import SimpleRateThrottle


class RedisRateThrottle(SimpleRateThrottle):
    """Custom API Rate Limiter using Redis cache (100 requests/min per API Key or IP address)."""

    scope = "redis_api"

    def get_cache_key(self, request, view):
        # Prioritize X-API-Key header if present
        api_key = request.headers.get("X-API-Key") or request.META.get("HTTP_X_API_KEY")
        if api_key:
            ident = f"key_{api_key.strip()}"
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }
