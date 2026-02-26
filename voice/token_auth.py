"""
Channels middleware that authenticates WebSocket connections
via an ``access_token`` query-string parameter.

Usage (in asgi.py):
    from voice.token_auth import TokenAuthMiddleware
    ...
    "websocket": TokenAuthMiddleware(URLRouter(...))
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser

from main.auth import get_user_from_token


@database_sync_to_async
def _get_user(token: str):
    """Resolve a JWT access token to a User (sync DB hit wrapped for async)."""
    return get_user_from_token(token) or AnonymousUser()


class TokenAuthMiddleware(BaseMiddleware):
    """
    Reads ``?access_token=<jwt>`` from the WebSocket URL and sets
    ``scope["user"]`` before the consumer runs.

    Falls back to ``AnonymousUser`` when the token is missing or invalid.
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)
        token = (params.get("access_token") or [None])[0]

        if token:
            scope["user"] = await _get_user(token)
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
