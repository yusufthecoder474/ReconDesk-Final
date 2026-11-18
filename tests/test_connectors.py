"""Connector unit tests with mocked HTTP — no network, no mock server.

The HTTP layer is tested through a fake ``requests`` session injected
into ``RetryingHttpClient``; the sync layer is tested through a fake
session driving ``MockConnector`` against an in-memory dataset.
"""

from datetime import date
from decimal import Decimal

import pytest

from connectors.auth import auth_headers
from connectors.config import ConnectorConfig
from connectors.errors import ConnectorAuthError, ConnectorError, MappingError
from connectors.http_client import RetryingHttpClient
from connectors.mapping import map_invoice, map_payment
from connectors.mock_connector import MockConnector
from connectors.models import ConnectorSyncRun, ConnectorSyncState
from core.models import Customer, Invoice, Payment


# -- fake HTTP ---------------------------------------------------------


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeSession:
    """Serves paged records from an in-memory dataset.

    ``pages`` maps resource -> list of record dicts. Pagination is
    cursor-based (last id), ``updated_since`` filters on the ISO
    ``updated_at`` string, and ``page_size`` is honoured from the
    request params so pagination is exercised, not assumed.
    """

    def __init__(self, dataset, page_size=2):
        self.dataset = dataset
        self.page_size = page_size
        self.calls = []
        self.last_headers = None

    def get(self, url, params=None, headers=None, timeout=None):
        params = params or {}
        self.calls.append((url, dict(params)))
        self.last_headers = dict(headers or {})
        if url.endswith("/health"):
            return FakeResponse(200, {"status": "ok"})
        resource = "invoices" if url.endswith("/invoices") else "payments"
        records = list(self.dataset[resource])
        updated_since = params.get("updated_since")
        if updated_since:
            records = [r for r in records if r["updated_at"] > updated_since]
        cursor = params.get("cursor")
        if cursor:
            ids = [r["id"] for r in records]
            records = records[ids.index(cursor) + 1 :] if cursor in ids else records
        limit = int(params.get("limit", self.page_size))
        page = records[:limit]
        return FakeResponse(
            200,
            {
                "data": page,
                "next_cursor": page[-1]["id"] if len(records) > limit else None,
            },
        )


def invoice_record(i, amount="100.00", updated_at="2026-01-01T09:00:00+00:00"):
    return {
        "id": f"inv_{i:05d}",
        "number": f"MOCK-{i:05d}",
        "customer_name": f"Customer {i % 2}",
        "customer_email": f"customer{i % 2}@example.test",
        "amount": amount,
        "issued_on": "2026-01-01",
        "due_on": "2026-01-31",
        "updated_at": updated_at,
    }


def payment_record(i, updated_at="2026-01-01T09:00:00+00:00"):
    return {
        "id": f"pay_{i:05d}",
        "reference": f"PAY-{i:05d}",
        "invoice_number": "MOCK-00000",
        "customer_name": f"Customer {i % 2}",
        "customer_email": f"customer{i % 2}@example.test",
        "amount": "50.00",
        "paid_on": "2026-01-02",
        "updated_at": updated_at,
    }


@pytest.fixture
def dataset():
    return {
        "invoices": [invoice_record(i) for i in range(3)],
        "payments": [payment_record(i) for i in range(2)],
    }


@pytest.fixture
def connector(dataset):
    session = FakeSession(dataset)
    config = ConnectorConfig(
        name="mock",
        base_url="http://mock.test",
        api_token="test-token",
        page_size=2,  # force multi-page fetches in the unit tests
    )
    client = RetryingHttpClient(session=session, sleep=lambda s: None)
    return MockConnector(config=config, client=client)


# -- auth --------------------------------------------------------------


def test_bearer_auth_header():
    headers = auth_headers("bearer", api_token="tok123")
    assert headers == {"Authorization": "Bearer tok123"}


def test_api_key_auth_header():
    assert auth_headers("api_key", api_token="tok123") == {"X-API-Key": "tok123"}


def test_basic_auth_header_decodes_to_user_password():
    import base64

    headers = auth_headers("basic", username="alice", password="s3cret")
    scheme, encoded = headers["Authorization"].split(" ", 1)
    assert scheme == "Basic"
    assert base64.b64decode(encoded).decode() == "alice:s3cret"


def test_auth_missing_token_raises():
    with pytest.raises(ConnectorAuthError):
        auth_headers("bearer", api_token=None)
    with pytest.raises(ConnectorAuthError):
        auth_headers("basic", username="alice", password=None)


def test_config_validate_rejects_unknown_auth_type():
    config = ConnectorConfig(name="mock", base_url="http://x", auth_type="oauth")
    with pytest.raises(ConnectorAuthError):
        config.validate()


def test_config_from_env_reads_bearer_token(monkeypatch):
    monkeypatch.setenv("MOCK_CONNECTOR_BASE_URL", "http://mock.test")
    monkeypatch.setenv("MOCK_CONNECTOR_API_TOKEN", "env-token")
    config = ConnectorConfig.from_env()
    assert config.base_url == "http://mock.test"
    assert config.api_token == "env-token"
    config.validate()


# -- HTTP client: retries ----------------------------------------------


class ScriptedSession:
    """Returns a scripted sequence of FakeResponses, recording calls."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls += 1
        return self.responses.pop(0)


def test_429_with_retry_after_waits_header_value():
    delays = []
    session = ScriptedSession(
        [
            FakeResponse(429, {}, {"Retry-After": "2"}),
            FakeResponse(200, {"ok": True}),
        ]
    )
    client = RetryingHttpClient(
        session=session, sleep=delays.append, jitter=lambda a, b: 0.0
    )
    assert client.get("http://x/invoices").status_code == 200
    assert delays == [2]
    assert session.calls == 2


def test_429_without_retry_after_uses_exponential_backoff():
    delays = []
    session = ScriptedSession(
        [FakeResponse(429, {}), FakeResponse(429, {}), FakeResponse(200, {})]
    )
    # jitter returns the cap, so delays are exactly base * 2**attempt.
    client = RetryingHttpClient(
        session=session,
        backoff_base=0.5,
        sleep=delays.append,
        jitter=lambda a, b: b,
    )
    client.get("http://x/invoices")
    assert delays == [0.5, 1.0]
    assert session.calls == 3


def test_500_retried_then_max_retries_raises():
    session = ScriptedSession([FakeResponse(500, {})] * 5)
    client = RetryingHttpClient(
        session=session, max_retries=3, sleep=lambda s: None
    )
    with pytest.raises(ConnectorError):
        client.get("http://x/invoices")
    assert session.calls == 4  # 1 attempt + 3 retries


def test_401_raises_auth_error_without_retry():
    session = ScriptedSession([FakeResponse(401, {})])
    client = RetryingHttpClient(session=session, sleep=lambda s: None)
    with pytest.raises(ConnectorAuthError):
        client.get("http://x/invoices")
    assert session.calls == 1


def test_404_raises_without_retry():
    session = ScriptedSession([FakeResponse(404, {})])
    client = RetryingHttpClient(session=session, sleep=lambda s: None)
    with pytest.raises(ConnectorError):
        client.get("http://x/invoices")
    assert session.calls == 1


# -- pagination + mapping ----------------------------------------------


def test_pagination_walks_cursor_to_exhaustion(connector, dataset):
    connector.authenticate()
    records, cursor = [], None
    while True:
        page = connector.fetch_page("invoices", cursor=cursor)
        records.extend(connector.extract(page))
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    assert [r["id"] for r in records] == [r["id"] for r in dataset["invoices"]]
    # page_size=2 over 3 records means exactly two pages were fetched.
    invoice_calls = [c for c in connector.client.session.calls if "invoices" in c[0]]
    assert len(invoice_calls) == 2
    assert invoice_calls[1][1]["cursor"] == "inv_00001"


def test_auth_header_sent_on_fetch(connector):
    connector.authenticate()
    connector.fetch_page("invoices")
    assert connector.client.session.last_headers == {
        "Authorization": "Bearer test-token"
    }


def test_map_invoice_ok():
    mapped = map_invoice(invoice_record(0, amount="123.45"))
    assert mapped["number"] == "MOCK-00000"
    assert mapped["amount"] == Decimal("123.45")
    assert mapped["issued_on"] == date(2026, 1, 1)
    assert mapped["customer_email"] == "customer0@example.test"


def test_map_payment_ok():
    mapped = map_payment(payment_record(0))
    assert mapped["reference"] == "PAY-00000"
    assert mapped["invoice_hint"] == "MOCK-00000"
    assert mapped["paid_on"] == date(2026, 1, 2)


def test_map_invoice_missing_amount_is_mapping_error():
    raw = invoice_record(0)
    del raw["amount"]
    with pytest.raises(MappingError) as excinfo:
        map_invoice(raw)
    assert excinfo.value.field == "amount"


def test_map_invoice_bad_amount_is_mapping_error():
    with pytest.raises(MappingError):
        map_invoice(invoice_record(0, amount="not-a-number"))


def test_map_invoice_bad_date_is_mapping_error():
    raw = invoice_record(0)
    raw["issued_on"] = "31/01/2026"
    with pytest.raises(MappingError):
        map_invoice(raw)


# -- sync: idempotency, incremental, errors, lease ---------------------


@pytest.mark.django_db
def test_sync_full_then_rerun_is_idempotent(connector):
    first = connector.sync(full=True)
    assert first.status == "succeeded"
    assert (first.records_created, first.records_fetched) == (5, 5)
    assert Invoice.objects.count() == 3
    assert Payment.objects.count() == 2

    second = connector.sync(full=True)
    assert second.status == "succeeded"
    assert second.records_created == 0
    assert second.records_skipped == 5
    assert Invoice.objects.count() == 3
    assert Payment.objects.count() == 2


@pytest.mark.django_db
def test_sync_incremental_fetches_only_changed_records(connector, dataset):
    connector.sync(full=True)
    state = ConnectorSyncState.objects.get(connector_name="mock")
    assert state.last_synced_at is not None

    # One changed invoice (newer updated_at, new amount) + one new invoice.
    dataset["invoices"][0]["amount"] = "250.00"
    dataset["invoices"][0]["updated_at"] = "2026-02-01T09:00:00+00:00"
    dataset["invoices"].append(
        invoice_record(99, amount="10.00", updated_at="2026-02-01T09:01:00+00:00")
    )
    run = connector.sync(full=False)
    assert run.status == "succeeded"
    assert run.records_fetched == 2
    assert run.records_created == 1
    assert run.records_updated == 1
    assert Invoice.objects.get(number="MOCK-00000").amount == Decimal("250.00")
    assert Invoice.objects.count() == 4


@pytest.mark.django_db
def test_sync_logs_mapping_error_and_continues(connector, dataset):
    bad = payment_record(99)
    bad["amount"] = "not-a-number"
    dataset["payments"].append(bad)
    run = connector.sync(full=True)
    assert run.status == "succeeded"
    assert run.mapping_errors == 1
    assert run.records_created == 5  # 3 invoices + 2 good payments
    assert Payment.objects.count() == 2
    assert run.details["mapping_errors"][0]["record_id"] == "pay_00099"


@pytest.mark.django_db
def test_sync_customer_matched_by_email_not_duplicated(connector):
    Customer.objects.create(name="Existing Name", email="customer0@example.test")
    run = connector.sync(full=True)
    assert run.status == "succeeded"
    assert Customer.objects.filter(email="customer0@example.test").count() == 1
    invoice = Invoice.objects.get(number="MOCK-00000")
    assert invoice.customer.name == "Existing Name"
    # Two customers in the dataset; only one more was created.
    assert Customer.objects.count() == 2


@pytest.mark.django_db
def test_sync_skips_finalized_invoice_instead_of_changing_it(connector):
    run = connector.sync(full=True)
    assert run.status == "succeeded"
    invoice = Invoice.objects.get(number="MOCK-00000")
    invoice.finalized = True
    invoice.save(update_fields=["finalized"])
    # External amount changes; the finalized row must not move.
    connector.client.session.dataset["invoices"][0]["amount"] = "999.00"
    connector.client.session.dataset["invoices"][0]["updated_at"] = (
        "2026-03-01T09:00:00+00:00"
    )
    second = connector.sync(full=True)
    assert second.status == "succeeded"
    assert second.records_skipped >= 1
    assert Invoice.objects.get(number="MOCK-00000").amount == Decimal("100.00")


@pytest.mark.django_db
def test_second_sync_while_one_is_active_is_refused(connector):
    ConnectorSyncRun.objects.create(
        connector_name="mock",
        active_key="mock",
        status=ConnectorSyncRun.STATUS_RUNNING,
    )
    run = connector.sync(full=True)
    assert run.status == ConnectorSyncRun.STATUS_ALREADY_RUNNING
    assert Invoice.objects.count() == 0
    assert Payment.objects.count() == 0
