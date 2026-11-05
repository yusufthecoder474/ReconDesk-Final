import os
import pytest
from flask_matcher.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_health(client):
    assert client.get("/health").json["status"] == "ok"


def test_unauthorized(client):
    assert client.post("/api/match", json={}).status_code == 401


def test_invalid_json(client):
    assert (
        client.post(
            "/api/match",
            headers={
                "X-Internal-Token": os.environ.get("MATCHER_SHARED_TOKEN", "dev-token")
            },
            data="broken",
        ).status_code
        == 400
    )


def test_valid_match(client):
    data = {
        "invoices": [{"id": 1, "customer_id": 1, "number": "A", "amount": "10.00"}],
        "payments": [{"id": 1, "customer_id": 1, "reference": "A", "amount": "10.00"}],
    }
    r = client.post(
        "/api/match",
        json=data,
        headers={
            "X-Internal-Token": os.environ.get("MATCHER_SHARED_TOKEN", "dev-token")
        },
    )
    assert r.status_code == 200 and r.json["suggestions"][0]["invoice_id"] == "1"
