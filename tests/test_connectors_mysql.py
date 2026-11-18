"""Real InnoDB concurrency check for connector syncs.

Two simultaneous full syncs against the same mock server must not
create duplicate rows: exactly one run is the clean winner (it
creates the 200 rows), the other is refused as ``already_running``
(or, if it starts after the winner finished, succeeds with zero
creates). Never treat SQLite as proof of this — the test is skipped
unless the database is MySQL/InnoDB.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.conf import settings
from django.db import close_old_connections

from connectors.config import ConnectorConfig
from connectors.mock_connector import MockConnector
from connectors.models import ConnectorSyncRun
from core.models import Invoice, Payment
from tests.mock_server_helper import MockServer


@pytest.mark.mysql
@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_syncs_do_not_duplicate():
    if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.mysql":
        pytest.skip("Requires MySQL/InnoDB; SQLite locking is not equivalent")
    with MockServer() as server:
        base_url = server.base_url

        def attempt():
            close_old_connections()
            try:
                config = ConnectorConfig(
                    name="mock",
                    base_url=base_url,
                    api_token="mock-test-token",
                    page_size=50,
                )
                return MockConnector(config=config).sync(full=True)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            runs = list(pool.map(lambda _: attempt(), range(2)))

    assert Invoice.objects.filter(source="mock").count() == 100
    assert Payment.objects.filter(source="mock").count() == 100
    assert Invoice.objects.filter(source="mock").values(
        "external_id"
    ).distinct().count() == 100
    assert Payment.objects.filter(source="mock").values(
        "external_id"
    ).distinct().count() == 100
    statuses = sorted(run.status for run in runs)
    assert "succeeded" in statuses
    assert set(statuses) <= {"succeeded", "already_running"}
    assert sum(run.records_created for run in runs) == 200
    assert ConnectorSyncRun.objects.filter(
        status=ConnectorSyncRun.STATUS_RUNNING
    ).count() == 0
