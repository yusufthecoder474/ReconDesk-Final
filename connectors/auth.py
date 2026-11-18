"""Authentication headers for the supported auth schemes.

The connector selects a scheme by config (``auth_type``); the secret
itself lives only in :class:`connectors.config.ConnectorConfig`, which
is built from environment variables. This module never reads the
environment and never logs a header value.

OAuth 2.0 is intentionally *not* built here: see docs/CONNECTORS.md
("How OAuth 2.0 would plug in") for where a token-exchange step and a
refreshing ``requests`` auth hook would slot into this same seam —
``auth_headers`` is the single place a new scheme is added.
"""

import base64

from .errors import ConnectorAuthError


def auth_headers(auth_type, *, api_token=None, username=None, password=None):
    """Return the Authorization headers for one request.

    ``bearer``  -> ``Authorization: Bearer <token>``
    ``api_key`` -> ``X-API-Key: <token>`` (token-style APIs that do not
                   use the Bearer scheme)
    ``basic``   -> ``Authorization: Basic base64(user:password)``
    """
    if auth_type == "bearer":
        if not api_token:
            raise ConnectorAuthError("Bearer auth needs an API token")
        return {"Authorization": f"Bearer {api_token}"}
    if auth_type == "api_key":
        if not api_token:
            raise ConnectorAuthError("API-key auth needs an API token")
        return {"X-API-Key": api_token}
    if auth_type == "basic":
        if not username or not password:
            raise ConnectorAuthError("Basic auth needs a username and password")
        raw = f"{username}:{password}".encode("utf-8")
        return {
            "Authorization": "Basic "
            + base64.b64encode(raw).decode("ascii")
        }
    raise ConnectorAuthError(f"Unsupported auth type: {auth_type!r}")


def headers_for_config(config):
    return auth_headers(
        config.auth_type,
        api_token=config.api_token,
        username=config.username,
        password=config.password,
    )
