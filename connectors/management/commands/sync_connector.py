"""Sync invoices/payments from an external connector into ReconDesk.

Usage (mock server running on port 5001)::

    python -m connectors.mock_server &   # or: MOCK_SERVER_PORT=5001 ...
    python manage.py sync_connector mock --full

Subsequent runs without ``--full`` are incremental: only records
changed since the stored cursor are fetched. A second simultaneous
run exits with "already running" and writes nothing.
"""

from django.core.management.base import BaseCommand, CommandError

from connectors.config import ConnectorConfig
from connectors.errors import ConnectorError
from connectors.mock_connector import MockConnector
from connectors.models import ConnectorSyncRun
from connectors.sync_service import clear_stale_lease

CONNECTORS = {"mock": MockConnector}


class Command(BaseCommand):
    help = "Sync invoices and payments from an external connector."

    def add_arguments(self, parser):
        parser.add_argument(
            "connector", nargs="?", default="mock", choices=list(CONNECTORS)
        )
        parser.add_argument(
            "--full", action="store_true", help="Ignore the stored cursor"
        )
        parser.add_argument(
            "--no-bulk",
            action="store_true",
            help="Use per-row saves instead of bulk upserts",
        )
        parser.add_argument(
            "--base-url", default=None, help="Override the connector base URL"
        )
        parser.add_argument(
            "--auth-type",
            default=None,
            choices=["bearer", "basic", "api_key"],
            help="Override the auth scheme",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Clear a stale live-run lease before syncing",
        )

    def handle(self, *args, **options):
        config = ConnectorConfig.from_env()
        if options["base_url"]:
            config.base_url = options["base_url"].rstrip("/")
        if options["auth_type"]:
            config.auth_type = options["auth_type"]
        if options["force"]:
            cleared = clear_stale_lease(config.name, force=True)
            self.stdout.write(f"Cleared {cleared} stale lease(s).")
        connector = CONNECTORS[options["connector"]](config=config)
        try:
            run = connector.sync(full=options["full"], use_bulk=not options["no_bulk"])
        except ConnectorError as exc:
            raise CommandError(str(exc)) from exc
        if run.status == ConnectorSyncRun.STATUS_ALREADY_RUNNING:
            self.stdout.write(
                self.style.WARNING(
                    f"Sync #{run.pk} skipped: another {config.name} "
                    "sync is already running."
                )
            )
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Sync #{run.pk} {run.status}: fetched={run.records_fetched} "
                f"created={run.records_created} updated={run.records_updated} "
                f"skipped={run.records_skipped} "
                f"mapping_errors={run.mapping_errors}"
            )
        )
        if run.status == ConnectorSyncRun.STATUS_FAILED:
            raise CommandError(f"Sync failed: {run.error}")
