"""Abstract connector interface (SOLID: one interface, many providers).

A connector does exactly five things, in this order:

1. ``authenticate`` — prove the configured credentials work.
2. ``fetch_page`` — fetch one page of one resource (cursor pagination).
3. ``extract`` — pull the record list out of a page payload.
4. ``map_to_internal`` — translate one external record to ReconDesk
   fields (pure mapping, see ``connectors.mapping``).
5. ``sync`` — drive 1–4 to exhaustion, persist with upserts, advance
   the incremental cursor, and return the ``ConnectorSyncRun``.

The HTTP client is injected, so a second connector is a new subclass
plus a mapping function — no changes to the retry, lease or upsert
code. Persistence lives in ``connectors.sync_service`` (imported
lazily inside :meth:`BaseConnector.sync` to avoid a circular import:
the service needs the connector type, the connector needs the
service only when a sync actually runs).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .auth import headers_for_config
from .config import ConnectorConfig
from .errors import ConnectorError
from .http_client import RetryingHttpClient


@dataclass
class Page:
    records: list
    next_cursor: str | None = None


class BaseConnector(ABC):
    #: resources this connector syncs, in order
    resources = ("invoices", "payments")

    def __init__(self, config, client=None):
        self.config = config
        self.client = client or RetryingHttpClient(
            max_retries=config.max_retries,
            backoff_base=config.backoff_base,
            backoff_max=config.backoff_max,
            timeout=config.timeout,
        )

    @property
    def name(self):
        return self.config.name

    # -- interface ---------------------------------------------------

    def authenticate(self):
        """Validate config, set auth headers, prove connectivity.

        The default probe is a GET on ``<base_url>/health``. A provider
        whose auth can only be verified by a real resource call should
        override this; the first ``fetch_page`` converts 401/403 into
        :class:`ConnectorAuthError` either way.
        """
        self.config.validate()
        self.client.set_headers(headers_for_config(self.config))
        self.client.get(f"{self.config.base_url}/health")

    @abstractmethod
    def fetch_page(self, resource, cursor=None, updated_since=None):
        """Fetch one page. Returns a :class:`Page`.

        ``cursor`` is the opaque cursor from the previous page (or
        ``None`` for the first page); ``updated_since`` is the
        incremental-sync lower bound, or ``None`` for a full load.
        """

    def extract(self, page):
        """Pull the record list out of a fetched page."""
        if not isinstance(page, Page) or not isinstance(page.records, list):
            raise ConnectorError("Connector returned a malformed page")
        return page.records

    @abstractmethod
    def map_to_internal(self, resource, raw):
        """Translate one external record to ReconDesk fields."""

    # -- orchestration ------------------------------------------------

    def sync(self, full=False, use_bulk=True):
        """Run a full or incremental sync and return the SyncRun.

        ``full=True`` ignores the stored cursor; otherwise only records
        changed since ``last_synced_at`` are fetched. Persistence,
        leasing and cursor advancement live in ``sync_service``.
        """
        from .sync_service import run_sync

        return run_sync(self, full=full, use_bulk=use_bulk)
