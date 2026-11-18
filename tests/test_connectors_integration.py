"""Integration tests against the real local mock server (live HTTP).

The server runs in a thread on an ephemeral port; the connector
talks to it over real HTTP with real auth, pagination and retries.
"""

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client

from connectors.config import ConnectorConfig
from connectors.mock_connector import MockConnector
from connectors.mock_server import build_dataset
from core.models import Customer, Invoice, Payment
from tests.mock_server_helper import MockServer


def _connector(server, **overrides):
    config = ConnectorConfig(
        name="mock",
        base_url=server.base_url,
        api_token="mock-test-token",
        page_size=50,
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return MockConnector(config=config)


@pytest.mark.django_db
def test_full_sync_against_mock_server():
    with MockServer() as server:
        run = _connector(server).sync(full=True)
    assert run.status == "succeeded"
    assert run.records_fetched == 200
    assert run.records_created == 200
    assert Invoice.objects.count() == 100
    assert Payment.objects.count() == 100
    assert Customer.objects.count() == 10
    # Synced rows are now ordinary ReconDesk rows the matcher can use.
    assert Invoice.objects.filter(source="mock").count() == 100
    assert Payment.objects.filter(source="mock").count() == 100


@pytest.mark.django_db
def test_mock_server_429_is_retried_end_to_end():
    with MockServer(fail_429_once=True) as server:
        run = _connector(server).sync(full=True)
    assert run.status == "succeeded"
    assert run.records_created == 200


@pytest.mark.django_db
def test_basic_auth_against_mock_server():
    with MockServer() as server:
        connector = _connector(
            server, auth_type="basic", username="mock", password="mock",
            api_token=None,
        )
        run = connector.sync(full=True)
    assert run.status == "succeeded"
    assert run.records_created == 200


@pytest.mark.django_db
def test_incremental_sync_after_dataset_change():
    dataset = build_dataset(n_invoices=5, n_payments=5)
    with MockServer(dataset=dataset) as server:
        connector = _connector(server)
        first = connector.sync(full=True)
        assert first.records_created == 10
        # A changed invoice and a brand-new payment, both newer than
        # the stored cursor.
        dataset["invoices"][0]["amount"] = "777.00"
        dataset["invoices"][0]["updated_at"] = "2026-03-01T09:00:00+00:00"
        dataset["payments"].append(
            {
                "id": "pay_99999",
                "reference": "PAY-99999",
                "invoice_number": "MOCK-00000",
                "customer_name": "Mock Customer 0",
                "customer_email": "customer0@example.test",
                "amount": "42.00",
                "paid_on": "2026-03-01",
                "updated_at": "2026-03-01T09:01:00+00:00",
            }
        )
        second = connector.sync(full=False)
    assert second.status == "succeeded"
    assert second.records_fetched == 2
    assert second.records_created == 1
    assert second.records_updated == 1
    assert Invoice.objects.get(number="MOCK-00000").amount.__str__() == "777.00"


@pytest.mark.django_db
def test_management_command_syncs():
    with MockServer() as server:
        import os

        os.environ["MOCK_CONNECTOR_BASE_URL"] = server.base_url
        os.environ["MOCK_CONNECTOR_API_TOKEN"] = "mock-test-token"
        call_command("sync_connector", "mock", "--full")
    assert Invoice.objects.count() == 100
    assert Payment.objects.count() == 100


@pytest.mark.django_db
def test_staff_api_triggers_sync_and_non_staff_is_refused():
    staff = User.objects.create_user("staff", password="pw", is_staff=True)
    plain = User.objects.create_user("plain", password="pw", is_staff=False)
    with MockServer() as server:
        import os

        os.environ["MOCK_CONNECTOR_BASE_URL"] = server.base_url
        os.environ["MOCK_CONNECTOR_API_TOKEN"] = "mock-test-token"
        client = Client()
        client.force_login(plain)
        assert client.post("/api/connectors/sync/", {}).status_code == 403
        client.force_login(staff)
        response = client.post("/api/connectors/sync/", {"full": True})
        assert response.status_code == 201
        assert response.json()["records_created"] == 200
        assert client.get("/api/connectors/runs/").status_code == 200
    assert Invoice.objects.count() == 100
