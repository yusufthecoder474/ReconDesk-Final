"""Connector configuration. Secrets come from environment variables only.

Nothing in this module prints, logs or returns a secret value. The
``from_env`` factory is the only place environment variables are read,
so a connector can be constructed in tests with explicit values and
no environment at all (dependency injection).
"""

import os
from dataclasses import dataclass

from .errors import ConnectorAuthError

AUTH_TYPES = ("bearer", "basic", "api_key")


@dataclass
class ConnectorConfig:
    name: str = "mock"
    base_url: str = ""
    auth_type: str = "bearer"
    api_token: str | None = None
    username: str | None = None
    password: str | None = None
    page_size: int = 100
    max_retries: int = 3
    backoff_base: float = 0.5
    backoff_max: float = 30.0
    timeout: float = 10.0

    @classmethod
    def from_env(cls, prefix="MOCK_CONNECTOR_", name="mock"):
        """Build config from ``<PREFIX>BASE_URL`` etc. Missing secrets
        stay ``None``; :meth:`validate` reports them without values."""
        return cls(
            name=name,
            base_url=os.environ.get(f"{prefix}BASE_URL", "").rstrip("/"),
            auth_type=os.environ.get(f"{prefix}AUTH_TYPE", "bearer").lower(),
            api_token=os.environ.get(f"{prefix}API_TOKEN") or None,
            username=os.environ.get(f"{prefix}USERNAME") or None,
            password=os.environ.get(f"{prefix}PASSWORD") or None,
            page_size=int(os.environ.get(f"{prefix}PAGE_SIZE", "100")),
            max_retries=int(os.environ.get(f"{prefix}MAX_RETRIES", "3")),
            timeout=float(os.environ.get(f"{prefix}TIMEOUT", "10")),
        )

    def validate(self):
        if not self.base_url:
            raise ConnectorAuthError("Connector base URL is not configured")
        if self.auth_type not in AUTH_TYPES:
            raise ConnectorAuthError(
                f"Unsupported auth type: {self.auth_type!r} "
                f"(expected one of {', '.join(AUTH_TYPES)})"
            )
        if self.auth_type in ("bearer", "api_key") and not self.api_token:
            raise ConnectorAuthError(
                f"Auth type {self.auth_type!r} needs an API token "
                "(set the token environment variable)"
            )
        if self.auth_type == "basic" and not (self.username and self.password):
            raise ConnectorAuthError(
                "Auth type 'basic' needs a username and a password "
                "(set the username/password environment variables)"
            )
        if self.page_size < 1:
            raise ConnectorAuthError("page_size must be at least 1")
        if self.max_retries < 0:
            raise ConnectorAuthError("max_retries must be at least 0")
