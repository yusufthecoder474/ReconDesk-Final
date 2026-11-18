"""Concrete connector against the local mock server.

The mock server (``connectors/mock_server.py``) speaks a Stripe-shaped
JSON API: ``GET /invoices`` and ``GET /payments`` with ``limit``,
``cursor`` (opaque, last-seen id) and ``updated_since`` query
parameters, returning ``{"data": [...], "next_cursor": ...}``.

This connector is deliberately thin: auth and retries live in the
injected HTTP client, mapping lives in ``connectors.mapping``. To
point it at Stripe test mode instead, change ``base_url`` + auth in
config and replace the two mapping functions — ``fetch_page``,
``sync`` and the lease logic do not change. See docs/CONNECTORS.md.
"""

from . import mapping
from .base import BaseConnector, Page
from .config import ConnectorConfig
from .errors import ConnectorError


class MockConnector(BaseConnector):
    def __init__(self, config=None, client=None):
        super().__init__(config or ConnectorConfig.from_env(), client=client)

    def fetch_page(self, resource, cursor=None, updated_since=None):
        if resource not in self.resources:
            raise ConnectorError(f"Unknown resource: {resource!r}")
        params = {"limit": self.config.page_size}
        if cursor:
            params["cursor"] = cursor
        if updated_since is not None:
            params["updated_since"] = updated_since.isoformat()
        response = self.client.get(
            f"{self.config.base_url}/{resource}", params=params
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ConnectorError(
                f"Connector returned non-JSON for {resource}"
            ) from exc
        if not isinstance(payload, dict) or not isinstance(
            payload.get("data"), list
        ):
            raise ConnectorError(
                f"Connector returned a malformed payload for {resource}"
            )
        return Page(
            records=payload["data"],
            next_cursor=payload.get("next_cursor"),
        )

    def map_to_internal(self, resource, raw):
        if resource == "invoices":
            return mapping.map_invoice(raw)
        if resource == "payments":
            return mapping.map_payment(raw)
        raise ConnectorError(f"Unknown resource: {resource!r}")
