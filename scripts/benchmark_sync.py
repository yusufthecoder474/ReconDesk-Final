"""Benchmark connector sync: per-row saves vs bulk upserts.

Runs a full sync of N records (half invoices, half payments) from
the local mock server twice on a fresh test database — once with
``use_bulk=False`` (one ``save()`` per row) and once with
``use_bulk=True`` (``bulk_create`` / ``bulk_update`` per page, with
batched customer resolution) — and prints time + DB query count for
each. Both modes share the same customer preloading, so the
difference measured is the write path alone.

Usage::

    USE_SQLITE=1 python scripts/benchmark_sync.py --records 1000 10000

The script builds its own Django test database, so it never touches
``local.sqlite3`` or production data. Numbers are single runs on
this machine; re-run to compare on yours. ``--output`` writes the
same table as JSON.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.test.runner import DiscoverRunner  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402
from django.db import connection  # noqa: E402

from connectors.config import ConnectorConfig  # noqa: E402
from connectors.mock_connector import MockConnector  # noqa: E402
from connectors.mock_server import build_dataset  # noqa: E402
from core.models import Customer, Invoice, Payment  # noqa: E402
from connectors.models import ConnectorSyncRun, ConnectorSyncState  # noqa: E402
from tests.mock_server_helper import MockServer  # noqa: E402


def _reset():
    Payment.objects.all().delete()
    Invoice.objects.all().delete()
    Customer.objects.all().delete()
    ConnectorSyncRun.objects.all().delete()
    ConnectorSyncState.objects.all().delete()


class _QueryCounter:
    """Count every DB execute via an execute wrapper.

    ``CaptureQueriesContext`` cannot be used here: Django's query log
    is a bounded deque, so a 10k-record run overflows it and the
    count wraps to a wrong (even zero) value. A wrapper counts
    reliably at any volume; ``executemany`` (bulk_create) counts as
    one execute per batch, which is the point being measured.
    """

    def __init__(self):
        self.count = 0

    def __call__(self, execute, sql, params, many, context):
        self.count += 1
        return execute(sql, params, many, context)


def _run_once(connector, *, use_bulk):
    _reset()
    counter = _QueryCounter()
    start = time.perf_counter()
    with connection.execute_wrapper(counter):
        run = connector.sync(full=True, use_bulk=use_bulk)
    elapsed = time.perf_counter() - start
    return {
        "records": run.records_fetched,
        "created": run.records_created,
        "seconds": round(elapsed, 3),
        "queries": counter.count,
        "rows_per_second": round(run.records_fetched / elapsed, 1) if elapsed else 0,
        "queries_per_record": round(counter.count / max(run.records_fetched, 1), 2),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--records",
        nargs="+",
        type=int,
        default=[1000, 10000],
        help="Total record counts to sync (split half invoices / half payments)",
    )
    parser.add_argument("--output", default=None, help="Write results as JSON")
    args = parser.parse_args()

    setup_test_environment()
    runner = DiscoverRunner(interactive=False, verbosity=0)
    old_config = runner.setup_databases()
    results = []
    try:
        for total in args.records:
            half = total // 2
            dataset = build_dataset(n_invoices=half, n_payments=half)
            with MockServer(dataset=dataset) as server:
                config = ConnectorConfig(
                    name="mock",
                    base_url=server.base_url,
                    api_token="mock-test-token",
                    page_size=500,
                )
                connector = MockConnector(config=config)
                for mode, use_bulk in (("per-row", False), ("bulk", True)):
                    row = {"mode": mode, **_run_once(connector, use_bulk=use_bulk)}
                    results.append(row)
                    print(
                        f"{total:>6} records | {mode:<7} | "
                        f"{row['seconds']:>7.3f}s | {row['queries']:>6} queries | "
                        f"{row['rows_per_second']:>7.1f} rows/s | "
                        f"{row['queries_per_record']} queries/record"
                    )
    finally:
        runner.teardown_databases(old_config)

    for total in args.records:
        per_row = next(
            r for r in results if r["records"] == total and r["mode"] == "per-row"
        )
        bulk = next(
            r for r in results if r["records"] == total and r["mode"] == "bulk"
        )
        print(
            f"{total} records: bulk is "
            f"{per_row['seconds'] / bulk['seconds']:.1f}x faster and "
            f"{per_row['queries'] / max(bulk['queries'], 1):.1f}x fewer queries "
            f"than per-row."
        )
    if args.output:
        Path(args.output).write_text(json.dumps(results, indent=2))
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
