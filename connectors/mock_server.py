"""Local mock SaaS API (Stripe-shaped) for connector development/tests.

Run it standalone::

    MOCK_API_TOKEN=mock-test-token python -m connectors.mock_server

or import :func:`create_app` in tests and serve it in a thread.

Data is deterministic: invoice ``i`` belongs to customer ``i % 10``,
amounts and dates are arithmetic, and ``updated_at`` is strictly
increasing (one minute per record), so incremental sync with
``updated_since`` is unambiguous. The dataset is mutable in-process
(``app.config["DATASET"]``), so tests can append a changed record or
a deliberately bad one and re-run a sync against the same server.

Auth: ``Authorization: Bearer <MOCK_API_TOKEN>`` (default
``mock-test-token``) or ``X-API-Key: <token>`` or Basic
``mock:mock`` — all three exercise the connector's auth schemes.
``/health`` is unauthenticated; ``/invoices`` and ``/payments``
require auth and return 401 otherwise.

Pagination: ``?limit=&cursor=&updated_since=``. ``cursor`` is the
last-seen record id (opaque to the client); ``updated_since`` is an
ISO-8601 datetime and filters ``updated_at > updated_since``.
Response: ``{"data": [...], "next_cursor": <id>|null}``.

Failure injection (tests only): create the app with
``fail_429_once=True`` and the first ``/invoices`` call returns 429
with ``Retry-After: 1``, then succeeds — the connector's retry path
can be exercised end to end without a real rate limit.
"""

import os
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request

DEFAULT_TOKEN = "mock-test-token"
BASE_TIME = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)


def build_dataset(n_invoices=100, n_payments=100):
    invoices, payments = [], []
    for i in range(n_invoices):
        customer = i % 10
        issued = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=i % 60)
        invoices.append(
            {
                "id": f"inv_{i:05d}",
                "number": f"MOCK-{i:05d}",
                "customer_name": f"Mock Customer {customer}",
                "customer_email": f"customer{customer}@example.test",
                "amount": f"{100 + (i * 37) % 9000}.00",
                "currency": "INR",
                "issued_on": issued.date().isoformat(),
                "due_on": (issued + timedelta(days=30)).date().isoformat(),
                "status": "paid" if i % 3 == 0 else "open",
                "updated_at": (BASE_TIME + timedelta(minutes=i)).isoformat(),
            }
        )
    for i in range(n_payments):
        customer = i % 10
        paid = datetime(2026, 1, 2, tzinfo=timezone.utc) + timedelta(days=i % 60)
        payments.append(
            {
                "id": f"pay_{i:05d}",
                "reference": f"PAY-{i:05d}",
                "invoice_number": f"MOCK-{i % max(n_invoices, 1):05d}",
                "customer_name": f"Mock Customer {customer}",
                "customer_email": f"customer{customer}@example.test",
                "amount": f"{50 + (i * 23) % 4000}.00",
                "currency": "INR",
                "paid_on": paid.date().isoformat(),
                "status": "received",
                "updated_at": (
                    BASE_TIME + timedelta(minutes=n_invoices + i)
                ).isoformat(),
            }
        )
    return {"invoices": invoices, "payments": payments}


def _parse_updated_since(raw):
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def create_app(dataset=None, token=None, fail_429_once=False):
    app = Flask(__name__)
    app.config["DATASET"] = dataset if dataset is not None else build_dataset()
    app.config["TOKEN"] = token or os.environ.get("MOCK_API_TOKEN", DEFAULT_TOKEN)
    app.config["FAIL_429_ONCE"] = fail_429_once
    app.config["FAIL_429_USED"] = False

    def _authorized():
        expected = app.config["TOKEN"]
        if request.headers.get("Authorization") == f"Bearer {expected}":
            return True
        if request.headers.get("X-API-Key") == expected:
            return True
        auth = request.authorization
        return bool(auth and auth.username == "mock" and auth.password == "mock")

    def _page(resource):
        if not _authorized():
            return jsonify(error="Unauthorized"), 401
        if (
            app.config["FAIL_429_ONCE"]
            and not app.config["FAIL_429_USED"]
            and resource == "invoices"
        ):
            app.config["FAIL_429_USED"] = True
            response = jsonify(error="Rate limited (simulated)")
            response.status_code = 429
            response.headers["Retry-After"] = "1"
            return response
        try:
            limit = max(1, min(500, int(request.args.get("limit", "100"))))
        except ValueError:
            return jsonify(error="limit must be an integer"), 400
        try:
            updated_since = _parse_updated_since(request.args.get("updated_since"))
        except ValueError:
            return jsonify(error="updated_since must be ISO-8601"), 400
        records = sorted(
            app.config["DATASET"][resource],
            key=lambda r: (r["updated_at"], r["id"]),
        )
        if updated_since is not None:
            records = [
                r
                for r in records
                if datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
                > updated_since
            ]
        cursor = request.args.get("cursor")
        if cursor:
            ids = [r["id"] for r in records]
            if cursor in ids:
                records = records[ids.index(cursor) + 1 :]
        page_records = records[:limit]
        next_cursor = (
            page_records[-1]["id"] if len(records) > limit else None
        )
        return jsonify(data=page_records, next_cursor=next_cursor)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/invoices")
    def invoices():
        return _page("invoices")

    @app.get("/payments")
    def payments():
        return _page("payments")

    return app


if __name__ == "__main__":
    port = int(os.environ.get("MOCK_SERVER_PORT", "5001"))
    create_app().run(host="127.0.0.1", port=port)
